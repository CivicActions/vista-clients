# Research: VistA RPC Broker Library

**Feature**: 001-vista-rpc-library  
**Date**: 2026-02-14  
**Sources**: VA Developer's Guide (XWB 1.1 DG), VA Systems Management Guide (XWB 1.1 SM), MUMPS routines (XWBTCPM.m, XWBTCPC.m, XWBM2MEZ.m, XQCS.m) via MCP, rpcutils-3.0 reference implementation (brokerRPC.py)

---

## 1. XWB Wire Protocol (New-Style `[XWB]`)

### Decision
Implement the **new-style** `[XWB]` protocol exclusively. The old-style `{XWB}` callback protocol and the XML-based `<?xml` M2M protocol are out of scope.

### Rationale
- The VEHU server's `XWBTCPM.m` handler reads the first 5 bytes to determine protocol variant: `[XWB]` = new style, `{XWB}` = old callback style, `<?xml` = M2M.
- The old-style protocol requires callback connections (server connects back to client), which is incompatible with containerised environments and firewalled networks.
- All modern VistA GUI applications (CPRS, etc.) use the new-style protocol.
- The rpcutils-3.0 reference implementation (VistARPCConnection) uses exclusively `[XWB]`.

### Alternatives Considered
- **Old-style `{XWB}`**: Rejected — requires callback sockets, adds complexity with zero benefit.
- **M2M XML**: Rejected — designed for server-to-server communication, not client-to-server RPC.

---

## 2. Message Frame Format

### Decision
All messages follow the format: `[XWB]1130` prefix + command/RPC body + `chr(4)` terminator.

### Protocol Token Breakdown
From `brokerRPC.py` `makeRequest()` and corroborated by `XWBTCPM.m`:

| Byte(s) | Value | Meaning |
|---------|-------|---------|
| 0-4 | `[XWB]` | Protocol identifier (new-style) |
| 5 | `1` | Protocol version = 1 |
| 6 | `1` | Message type = 1 (standard) |
| 7-9 | `30` + `\n` | Envelope size = 3 digits, followed by LF |
| 10 | `0` | XWBPRT = 0 (non-callback) |

Composite prefix string: `"[XWB]1130"` + `chr(10)` + `"0"` — but in practice the reference implementation emits `"[XWB]11302"` for RPCs where `2` is the RPC command token. So the full prefix is `[XWB]1130\n0` (11 bytes).

### Command vs RPC Messages

| Type | Command Token | Notes |
|------|--------------|-------|
| Command (TCPConnect, disconnect) | `4` | Used for session management |
| RPC invocation | `2` + `chr(1)` + `1` | `chr(1)` separator, `1` = RPC subtype |

### Name Encoding: S-PACK
- S-PACK (Short Pack): `chr(len(name)) + name`
- Maximum name length: 255 characters (single byte length)

### Parameter Encoding

**Prefix**: `5` (indicates parameter section follows)

**No parameters**: `4f`

**Literal parameter (type 0)**:
```
"0" + L-PACK(value) + "f"
```

**Reference parameter (type 1)**:
```
"1" + L-PACK(value) + "f"
```

**List parameter (type 2)**:
```
"2" + L-PACK(key) + L-PACK(value) + "t" [+ L-PACK(key) + L-PACK(value) + "t"]* + "f"
```

Where `t` delimits key-value pairs within a list, and `f` terminates the parameter.

### L-PACK Encoding
- L-PACK (Length Pack): 3-digit zero-padded length string + value
- Example: `"005HELLO"` for the string `"HELLO"`
- Patch XWB*1.1*65 widened L-PACK from 999 to 99999 characters (5 digits) but the 3-digit format remains standard for most messages

### Message Terminator
- `chr(4)` (EOT — End of Transmission)

### Complete Message Example (RPC call)
```
[XWB]1130\n0 2\x011 <S-PACK(rpcName)> 5 <params> \x04
```

### Response Format
- Server sends response data terminated by `chr(4)` (EOT)
- Response may be prefixed with `\x00\x00` (two null bytes) which must be stripped
- Data is read in chunks until `chr(4)` is encountered
- The `chr(4)` terminator itself is stripped from the result

---

## 3. Connection Handshake Sequence

### Decision
Implement the 5-step handshake: TCP Connect → TCPConnect command → XUS SIGNON SETUP → XUS AV CODE → XWB CREATE CONTEXT.

### Detailed Sequence

**Step 1: TCP Socket Connection**
- Standard TCP connection to host:port
- Configurable timeout (default 30s per spec)

**Step 2: TCPConnect Command**
- Purpose: Register client with the VistA server
- Command token: `4` (command type, not RPC)
- Parameters: `localIP` (or hostname), `0` (callback port, unused in new-style), `appName` (application name)
- Expected response: `"accept"` — any other response indicates rejection
- Wire format (from brokerRPC.py):
  ```python
  "[XWB]1130" + chr(4) + "TCPConnect50" + 
      lpack(localIP) + "f0" + lpack("0") + "f0" + lpack(appName) + "f" + chr(4)
  ```
  Note: TCPConnect uses a slightly different format — the `4` command token appears embedded, and params use `f0` delimiters.

**Step 3: XUS SIGNON SETUP (RPC)**
- Purpose: Initialize signon subsystem on the server
- RPC name: `XUS SIGNON SETUP`
- Parameters: None
- Response: Server returns signon metadata (typically ignored by client in simple implementations)

**Step 4: XUS AV CODE (RPC)**
- Purpose: Authenticate user with Access/Verify codes
- RPC name: `XUS AV CODE`
- Parameters: One literal parameter containing `encrypt(accessCode + ";" + verifyCode)`
- The Access and Verify codes are concatenated with `;` separator, then encrypted
- Response: Multi-line, semicolon-delimited. Lines include:
  - Line 0: DUZ (user's internal entry number) — `0` means auth failed
  - Line 3: Error message if authentication failed (e.g., `"Not a valid ACCESS CODE/VERIFY CODE pair."`)
- On success: DUZ > 0 and no error message
- On failure: DUZ = 0 and descriptive error in response

**Step 5: XWB CREATE CONTEXT (RPC)**
- Purpose: Establish application context for RPC authorization
- RPC name: `XWB CREATE CONTEXT`
- Parameters: One literal parameter containing `encrypt(contextOptionName)`
- The context option name is the `B`-type menu option in VistA's OPTION (#19) file
- The option name is **encrypted** before sending (same cipher as credentials)
- Response: `"1"` = success, `"0"` (with error message) = failure
- Context determines which RPCs the user is authorized to call
- Context can be switched at any time by calling this RPC again

### Disconnect Sequence
- RPC name: `#BYE#` (special disconnect command)
- Sent as a standard RPC message
- Socket is closed after sending

---

## 4. Cipher Encryption

### Decision
Implement the cipher-based encryption algorithm used by the Delphi BDK and documented in `$$ENCRYP^XUSRB1` / `$$DECRYP^XUSRB1`.

### Algorithm
The RPC Broker uses a symmetric substitution cipher with two predefined cipher tables. Each table contains 20 rows of 95-character permutation strings (covering ASCII 32-126).

**Encrypt procedure**:
1. Pick two random integers `a` and `b` (1-19), representing row indices into the cipher table
2. For each character `c` in plaintext:
   - Find position `p` of `c` in cipher row `a` (0-based index)
   - Replace with character at position `p` in cipher row `b`
   - Swap `a` and `b` for each subsequent character (alternating rows)
3. Prepend the two row-index characters: `chr(a + 32)` and `chr(b + 32)`

**Decrypt procedure**:
1. Read first two characters to recover row indices: `a = ord(char0) - 32`, `b = ord(char1) - 32`
2. For each subsequent character:
   - Find position `p` of character in cipher row `b`
   - Replace with character at position `p` in cipher row `a`
   - Swap `a` and `b`

### Cipher Table
Two variants exist in the wild:
- **CIPHER_TRADITIONAL**: Used by VA-distributed BDK
- **CIPHER_OSEHRA**: Used by OSEHRA/WorldVistA distributions

Both are 20 rows × 95 characters. The VEHU image uses the OSEHRA variant. The rpcutils-3.0 reference includes both tables. The server-side `$$ENCRYP^XUSRB1` and `$$DECRYP^XUSRB1` functions in `XUSRB1.m` use the corresponding table.

### What Gets Encrypted
- Access Code + ";" + Verify Code (for XUS AV CODE)
- Context option name (for XWB CREATE CONTEXT)
- Any other sensitive data the developer chooses to encrypt

### Rationale for Re-implementation
The encryption must match the server-side `XUSRB1.m` exactly. The cipher tables are public (embedded in the Delphi source code and reference implementations). This is not cryptographic security — it is obfuscation to prevent plaintext credential transmission.

### Alternatives Considered
- **Skip encryption**: Rejected — server expects encrypted values and will reject plaintext
- **Use a general crypto library**: Rejected — the cipher is VistA-proprietary; no standard library implements it

---

## 5. Server Response Types

### Decision
Support all five return value types documented in the Developer's Guide, mapped to Python types.

### Return Value Types (from Developer's Guide Table 13 + XWBTCPM.m)

| Server Type Code | Name | Description | Python Mapping |
|-----------------|------|-------------|----------------|
| 1 | SINGLE VALUE | Single string returned in RESULT | `str` |
| 2 | ARRAY | Array of strings in RESULT(n) | `list[str]` |
| 3 | WORD PROCESSING | Like ARRAY but with word-wrap option | `list[str]` |
| 4 | GLOBAL ARRAY | Closed global reference in ^TMP | `list[str]` |
| 5 | GLOBAL INSTANCE | Value of a specific global node | `str` |
| 6 | VARIABLE LENGTH | Variable length records (XWBTCPM.m) | `list[str]` (future) |

### Response Wire Format
The server sends responses in a 3-part structure (from `SND`/`SNDERR` in `XWBRW.m`):

**Part 1 — Security Packet** (from `XWBSEC`):
- 1 byte: `chr(len)` — length of security error message (0–255)
- N bytes: security error content (e.g., unauthorized RPC message from `CHKPRMIT^XWBSEC`)

**Part 2 — Application Error Packet** (from `XWBERROR`):
- 1 byte: `chr(len)` — length of application error message (0–255)
- N bytes: application error content

**Part 3 — Result Data**:
- Variable bytes: response payload (string or array)

**Terminator**: `chr(4)` (EOT), stripped by the transport layer.

When no errors are present, both packets are empty: `chr(0)` + `chr(0)` = `\x00\x00`. This is the "null prefix" commonly stripped in simple implementations. However, when the server rejects an RPC (e.g., RPC not in the active context's allowed list), the security packet contains the error message. `parse_response()` must detect non-empty error packets and raise `RPCError` rather than treating the error bytes as result data.

**Parsing procedure**:
1. Read byte 0 as `sec_len = ord(byte)`
2. Read next `sec_len` bytes as security message
3. Read next byte as `err_len = ord(byte)`
4. Read next `err_len` bytes as application error message
5. If either message is non-empty → raise `RPCError` with the message
6. Remaining bytes = result data:
   - For array types: records are delimited by `\r\n` (CR+LF)
   - For single value: the entire string is the value

### Initial Scope
Per the spec, we will parse: SINGLE VALUE → `str`, ARRAY → `list[str]`, GLOBAL ARRAY → `list[str]`. WORD PROCESSING maps identically to ARRAY for parsing purposes. GLOBAL INSTANCE maps to SINGLE VALUE. Type 6 (variable length) is rare and deferred.

---

## 6. Parameter Types (Client to Server)

### Decision
Support `literal` and `list` parameter types. Defer `reference`, `global`, `empty`, and `stream` types.

### Full Type Enumeration (from Developer's Guide TParamType)
```
TParamType = (literal, reference, list, global, empty, stream, undefined)
```

| Type | Wire Code | Description | In Scope |
|------|-----------|-------------|----------|
| literal | `0` | String value passed directly | ✅ |
| reference | `1` | M variable name resolved server-side | ❌ (deferred, security concerns noted in DG) |
| list | `2` | Key-value array (Mult property) | ✅ |
| global | `3` | Like list but stored in global array | ❌ (deferred) |
| empty | `4` | No parameter value | ❌ (can use literal with empty string) |
| stream | `5` | Raw data stream | ❌ (deferred) |

### Rationale
Per the spec's project assumptions: "The library targets the most common RPC parameter types used in clinical workflows (literal and list); reference-type parameters are out of scope for this initial version." The Developer's Guide also notes that `reference` type "may be deprecated" for security reasons.

---

## 7. Keepalive Mechanism

### Decision
Implement a keepalive using `XWB IM HERE` RPC, optionally callable by the user but not automatic.

### Details
- The VistA server has a BROKER ACTIVITY TIMEOUT (default ~3 minutes) after which idle connections are terminated
- The Delphi BDK sends periodic `XWB IM HERE` RPCs in the background to reset this timeout
- `XWB IM HERE` takes no parameters and returns `"1"` (meaningless acknowledgment)
- For our library: expose a `ping()` or `keepalive()` method that sends `XWB IM HERE`
- Do NOT implement automatic background polling (per spec: no automatic retries, single-threaded focus)

### Alternatives Considered
- **Automatic background keepalive**: Rejected — requires threading, contradicts single-threaded scope
- **No keepalive at all**: Rejected — users need a way to prevent timeout on long-running operations

---

## 8. Error Handling Strategy

### Decision
Map server error conditions to a typed exception hierarchy.

### Error Conditions Identified

| Condition | Source | Exception Type |
|-----------|--------|---------------|
| TCP connection refused/timeout | Socket layer | `ConnectionError` |
| TCPConnect rejected (not "accept") | Handshake step 2 | `HandshakeError` |
| XUS AV CODE returns DUZ=0 | Auth step 4 | `AuthenticationError` |
| XWB CREATE CONTEXT returns 0 | Context step 5 | `ContextError` |
| RPC returns error response | RPC execution | `RPCError` |
| Socket closed mid-operation | Transport layer | `ConnectionError` |
| RPC called before handshake | State validation | `StateError` |
| Restricted RPC called without auth | State validation | `StateError` |

### Hierarchy
```
VistAError (base)
├── ConnectionError
├── HandshakeError
├── AuthenticationError
├── ContextError
├── RPCError
└── StateError
```

---

## 9. Layered Architecture

### Decision
Four-layer architecture: Transport → Protocol → Broker → (public API re-exports).

### Layer Responsibilities

| Layer | Module | Responsibility |
|-------|--------|---------------|
| Transport | `transport.py` | TCP socket management, send/receive with framing, timeout handling |
| Protocol | `protocol.py` | XWB message construction (S-PACK, L-PACK), message parsing, cipher encryption |
| Broker | `broker.py` | High-level operations: connect, handshake, authenticate, create_context, call_rpc, disconnect |
| Errors | `errors.py` | Exception hierarchy |

### Rationale
- **Transport** isolates socket I/O so the protocol layer can be tested without a live server (mock transport)
- **Protocol** is pure functions: `build_rpc_message(name, params) → bytes`, `parse_response(data) → str/list` — highly testable
- **Broker** orchestrates the handshake sequence and maintains connection state
- This 3+1 structure satisfies Constitution Principle III (Separation of Concerns) and is standard for protocol implementations

### Alternatives Considered
- **Single monolithic class**: Rejected — violates SoC, untestable without live server
- **Separate serializer module**: Considered but folded into `protocol.py` since serialization (S-PACK/L-PACK) is intrinsic to the protocol, not a standalone concern

---

## 10. Testing Strategy

### Decision
Three test tiers: unit tests (no server), contract tests (protocol compliance), integration/smoke tests (VEHU).

### Tier Breakdown

| Tier | Directory | Requires Server | Coverage |
|------|-----------|-----------------|----------|
| Unit | `tests/unit/` | No | Protocol encoding, cipher encrypt/decrypt, message construction/parsing |
| Contract | `tests/contract/` | No | Verify message formats against known-good byte sequences captured from reference implementation |
| Smoke | `tests/smoke/` | Yes (VEHU) | Full lifecycle: connect → handshake → auth → RPC → disconnect |

### Rationale
Unit and contract tests provide fast feedback and catch regressions without requiring Docker. Smoke tests validate against the real server and fulfil SC-006.

---

## 11. Credential Management

### Decision
Environment variable sourcing with built-in VEHU defaults.

### Credential Resolution Order
1. Explicit constructor arguments (highest priority)
2. Environment variables: `VISTA_ACCESS_CODE`, `VISTA_VERIFY_CODE`
3. Built-in VEHU defaults: Access=`SM1234`, Verify=`SM1234!!`

### Logging Redaction
Per FR-015, credentials MUST be redacted in all log output. The Access Code and Verify Code values are replaced with `***REDACTED***` in any log message, regardless of log level.

---

## 12. Existing Python Implementation Analysis (rpcutils-3.0)

### Assessment
The `brokerRPC.py` reference from Caregraf (AGPL-3.0 licensed) provides a working implementation of the VistA RPC Broker protocol. Key observations:

**Strengths (patterns to learn from)**:
- Correct wire format implementation in `makeRequest()` 
- Correct handshake sequence in `connect()`
- Cipher tables (both TRADITIONAL and OSEHRA variants) are present and functional
- `readToEndMarker()` pattern for reading until `chr(4)` is reliable
- Connection pool pattern (`RPCConnectionPool`) demonstrates thread-safe reuse

**Weaknesses (things to improve)**:
- Monolithic design: transport, protocol, and broker logic mixed in one class
- No type hints or modern Python idioms
- No context manager support
- Logging is ad-hoc (custom logger interface rather than standard `logging`)
- No typed exceptions (uses generic `Exception`)
- No test suite
- AGPL license incompatible with our needs
- Python 3.3+ vintage code style
- CIA Broker logic mixed in with VistA Broker logic

### Decision
Do NOT copy or derive from rpcutils-3.0. Use it purely as a protocol reference to validate our independent implementation. Our code will be original, using the XWB protocol specification (VA Developer's Guide + MUMPS source code) as the primary source of truth.
