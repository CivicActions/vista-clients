# Feature Specification: VistA RPC Broker Library

**Feature Branch**: `001-vista-rpc-library`  
**Created**: 2026-02-14  
**Status**: Draft  
**Input**: User description: "Create a VistA RPC Broker library module that serves as a seamless bridge between Python code and the VistA RPC Broker, abstracting the XWB wire protocol with a clean Pythonic API for invoking remote procedures"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connection Establishment (Priority: P1)

As a test developer, I want to initiate a connection to a VistA
server by specifying an IP address and port, so that I can
establish a TCP session reserved for RPC communication. The
connection must support a configurable timeout to handle network
latency typical in VistA environments.

**Why this priority**: Without a working connection, no other
library functionality is possible. This is the foundational
prerequisite for every downstream operation.

**Independent Test**: Can be fully tested by opening a connection
to the VEHU container on port 9430, verifying the session is
established, and closing it cleanly. Delivers value as proof that
the transport layer works across platforms.

**Acceptance Scenarios**:

1. **Given** a running VistA server on a known host and port,
   **When** the caller requests a connection with default
   settings, **Then** a session is established within the default
   timeout and the connection object reports itself as connected.
2. **Given** a running VistA server, **When** the caller provides
   a custom timeout value, **Then** that timeout is honoured for
   the connection attempt.
3. **Given** no server is reachable at the specified address,
   **When** the caller requests a connection, **Then** a clear
   connection error is raised before the timeout expires.
4. **Given** an established connection, **When** the caller
   closes it, **Then** the session is terminated gracefully and
   the connection object reports itself as disconnected.
5. **Given** a connection used within a context manager (`with`
   block), **When** the block exits (normally or via exception),
   **Then** the connection is automatically closed and the
   disconnect sequence is sent to the server.

---

### User Story 2 - Broker Handshake and Context Creation (Priority: P2)

As a library user, I want the library to automatically handle the
proprietary XWB handshake (connecting, disconnecting, and creating
context), so that I do not have to manually construct byte-level
handshake packets. The system must support switching between
application contexts (e.g., from the signon context to a clinical
application context).

**Why this priority**: The handshake negotiates the protocol
version and initialises the server-side session. Without it, no
RPCs can be invoked—but it depends on a working connection
(US 1).

**Independent Test**: Can be tested by connecting to VEHU,
performing the handshake, requesting a context switch, and
verifying the server acknowledges success.

**Acceptance Scenarios**:

1. **Given** an established TCP connection to a VistA server,
   **When** the handshake is initiated, **Then** the library
   negotiates the protocol version and the server accepts the
   session.
2. **Given** a successfully handshaked session, **When** the
   caller requests a specific application context, **Then** the
   server confirms the context is active.
3. **Given** a successfully handshaked session, **When** the
   caller requests an invalid or non-existent context, **Then**
   a clear error is raised indicating the context was rejected.

---

### User Story 3 - Authentication (Priority: P3)

As a test developer, I want to authenticate using standard VistA
Access and Verify codes, so that my session is authorised to
execute restricted RPCs. Authentication credentials must be
configurable (e.g., via environment variables) and must default
to known VEHU demonstration values when no overrides are provided.

**Why this priority**: Most RPCs require an authenticated session,
making this the gateway to the full API surface. It depends on
both connection (US 1) and handshake (US 2).

**Independent Test**: Can be tested by connecting to VEHU,
completing the handshake, logging in with known credentials, and
verifying that the session reports a valid DUZ.

**Acceptance Scenarios**:

1. **Given** a handshaked session and valid Access/Verify codes,
   **When** the caller authenticates, **Then** the server returns
   a DUZ confirming successful login.
2. **Given** a handshaked session and invalid Access/Verify codes,
   **When** the caller attempts to authenticate, **Then** a clear
   authentication error is raised with a human-readable message.
3. **Given** no credentials are explicitly provided, **When** the
   caller authenticates, **Then** the library uses default VEHU
   demonstration credentials sourced from environment variables
   or built-in defaults.

---

### User Story 4 - RPC Invocation with Typed Parameters (Priority: P4)

As a developer, I want to call a VistA RPC by name and pass
arguments of various types (strings, numbers, lists/arrays), so
that I can exercise the full range of VistA's API surface. The
library must correctly translate Python data structures into the
parameter formats expected by the Broker.

**Why this priority**: This is the core value proposition of the
library—actually calling RPCs. It depends on authentication
(US 3) for most practical use, though some RPCs are callable on
an unauthenticated session.

**Independent Test**: Can be tested by logging in to VEHU and
calling a well-known RPC (e.g., one that returns a server
variable) with each supported parameter type, verifying the
server processes each correctly.

**Acceptance Scenarios**:

1. **Given** an authenticated session, **When** the caller
   invokes an RPC with no parameters, **Then** the server
   executes the procedure and the library returns the result.
2. **Given** an authenticated session, **When** the caller
   invokes an RPC with a string parameter, **Then** the parameter
   is delivered to the server correctly.
3. **Given** an authenticated session, **When** the caller
   invokes an RPC with a list/dictionary parameter, **Then** the
   parameter is marshalled into the expected multidimensional
   array format and the server processes it correctly.
4. **Given** an authenticated session, **When** the caller
   invokes an RPC that does not exist or is not registered,
   **Then** a clear RPC error is raised.

---

### User Story 5 - Response Parsing (Priority: P5)

As a developer, I want the library to interpret VistA responses
(whether a simple string, an array of values, or a word-processing
field) and return them as native Python objects, so that I can
easily work with the data in my calling code.

**Why this priority**: Parsing completes the round-trip—callers
need usable Python objects, not raw byte streams. It builds on
RPC invocation (US 4).

**Independent Test**: Can be tested by calling several RPCs known
to return different response types (single value, array, global
array) and verifying the Python representations are correct and
idiomatic.

**Acceptance Scenarios**:

1. **Given** an RPC that returns a single string value, **When**
   the call completes, **Then** the library returns a Python
   string.
2. **Given** an RPC that returns an array of values, **When** the
   call completes, **Then** the library returns a Python list of
   strings.
3. **Given** an RPC that returns a global array, **When** the
   call completes, **Then** the library returns a Python list of
   strings.
4. **Given** an RPC that returns a word-processing field,
   **When** the call completes, **Then** the library returns a
   Python list of strings (identical to array parsing).
5. **Given** an RPC that returns an error or failure indicator,
   **When** the call completes, **Then** the library raises a
   specific error with the server-provided message.

---

### Edge Cases

- What happens when the server closes the connection mid-RPC
  (e.g., due to an M partition crash)? The library must detect
  the broken connection and raise a connection error rather than
  hanging indefinitely.
- What happens when a response exceeds an expected size or
  arrives in fragmented TCP segments? The library must reassemble
  the full response before parsing.
- What happens when the server is reachable but the Broker
  service is not running on the specified port? The library must
  distinguish "connection refused" from "connection timed out"
  with distinct error types.
- What happens when credentials contain special characters
  (e.g., `!`, `@`, spaces)? The library must transmit them
  without corruption.
- What happens when the caller attempts to invoke an RPC before
  completing the handshake? The library must raise a state error
  rather than sending malformed packets.
- What happens when the caller attempts to invoke a restricted
  RPC without authentication? The library must surface the
  server's permission-denied response as a clear error.

## Clarifications

### Session 2026-02-14

- Q: What should the default connection timeout be? → A: 30 seconds
- Q: Should the library emit log output, and how should credentials be handled? → A: Standard logging with credential redaction (DEBUG for wire detail, INFO for lifecycle events, credentials always masked)
- Q: Should the library automatically retry on connection failure? → A: No automatic retries; fail immediately and let callers implement retry logic
- Q: Should the library support Python's context manager protocol for automatic resource cleanup? → A: Yes, support context manager (`with` statement) for automatic cleanup
- Q: What is the canonical term for the authenticated user's identifier? → A: DUZ (the internal entry number in the VistA NEW PERSON file returned upon successful authentication)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST establish TCP connections to a
  VistA RPC Broker given a host address and port number.
- **FR-002**: The library MUST support a configurable connection
  timeout, defaulting to 30 seconds.
- **FR-003**: The library MUST perform the XWB protocol handshake
  automatically when a connection is initiated.
- **FR-004**: The library MUST support switching application
  contexts via the standard context-creation mechanism.
- **FR-005**: The library MUST authenticate sessions using
  Access Code and Verify Code pairs.
- **FR-006**: The library MUST source default credentials from
  environment variables (`VISTA_ACCESS_CODE`,
  `VISTA_VERIFY_CODE`) and fall back to built-in built-in demonstration defaults
  when no overrides are provided.
- **FR-007**: The library MUST invoke any named RPC and deliver
  parameters of the following types: literal string (numeric
  values are represented as their string form), and list
  (multidimensional key-value array).
- **FR-008**: The library MUST parse single-value, array,
  word-processing, and global-array response types into native
  Python objects (strings and lists). Word-processing responses
  are parsed identically to arrays (split on line boundaries).
- **FR-009**: The library MUST raise distinct, typed errors for
  connection failures, handshake failures, authentication
  failures, and RPC execution failures.
- **FR-010**: The library MUST gracefully close connections,
  sending the appropriate disconnect sequence to the server.
- **FR-011**: The library MUST operate without any binary or
  platform-specific dependencies—pure Python only.
- **FR-012**: The library MUST run identically on macOS, Linux,
  and Windows without conditional platform logic.
- **FR-013**: The library MUST detect and report broken
  connections (e.g., server crash) rather than blocking
  indefinitely.
- **FR-014**: The library MUST enforce call-order safety:
  general RPCs cannot be invoked before an application context
  is set, and context creation cannot be invoked before
  authentication. Operations attempted in an invalid session
  state MUST raise a distinct state error.
- **FR-015**: The library MUST emit log output using Python's
  standard logging module: DEBUG level for wire-level detail
  (bytes sent/received, packet framing), INFO level for
  lifecycle events (connect, handshake, login, disconnect).
  Credential values (Access Code, Verify Code) MUST be redacted
  in all log output regardless of level.
- **FR-016**: The library MUST NOT implement automatic retry
  logic for connection or RPC failures. Each operation MUST
  fail immediately on error, allowing callers to implement
  their own retry policies.
- **FR-017**: The library MUST support Python's context manager
  protocol (`with` statement) to guarantee that connections are
  closed and the disconnect sequence is sent to the server when
  the context exits, whether normally or via an exception.
- **FR-018**: The library MUST provide a keepalive method that
  sends the `XWB IM HERE` RPC to reset the server's activity
  timeout. The keepalive MUST NOT run automatically; it is
  invoked explicitly by the caller.

### Key Entities

- **Connection**: Represents a TCP session to a VistA server.
  Key attributes: host, port, timeout, connected status.
- **Session**: Represents the state after a successful handshake.
  Key attributes: active context, authentication status, DUZ
  (authenticated user's internal entry number in the NEW PERSON
  file).
- **RPC Request**: Represents a single remote procedure call.
  Key attributes: RPC name, ordered list of typed parameters.
- **RPC Response**: Represents the server's reply. Key
  attributes: response type (single value, array, global
  array), parsed data, error indicator.
- **Credentials**: Represents an Access Code / Verify Code pair.
  Key attributes: access code, verify code, source (environment
  variable, explicit, or default).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can connect to a VEHU container,
  authenticate, and invoke an RPC in under 10 lines of Python
  code.
- **SC-002**: The library successfully completes the full
  lifecycle (connect → handshake → authenticate → call RPC →
  parse response → disconnect) against the `worldvista/vehu`
  container on port 9430 with zero platform-specific
  dependencies.
- **SC-003**: The library runs identically inside a minimal
  Linux container (e.g., Alpine-based) with only Python
  installed—no Wine, no compiled extensions.
- **SC-004**: Connection failures, authentication failures, and
  RPC errors each produce distinct error types that a caller can
  catch individually.
- **SC-005**: The library handles all four VistA response
  formats (single value, array, word-processing, global array)
  and returns idiomatic Python objects for each.
- **SC-006**: 100% of smoke tests pass against a fresh VEHU
  container, covering connection, authentication, RPC
  invocation, and disconnection.

## Assumptions

### Terminology

- **DUZ**: The internal entry number (IEN) in the VistA NEW
  PERSON file (#200), returned upon successful authentication.
  This is the canonical identifier for an authenticated user
  throughout this specification. The informal term "user
  identity" may appear in narrative context but MUST NOT be used
  in requirements or acceptance criteria.
- **Access Code**: The first half of a VistA credential pair,
  analogous to a username.
- **Verify Code**: The second half of a VistA credential pair,
  analogous to a password.
- **XWB**: The proprietary wire protocol used by the VistA RPC
  Broker (version 1.1).
- **VEHU**: VistA for Education, Hacking, and Underground — the
  WorldVistA Docker image used as the reference environment.

### Project Assumptions

### Project Assumptions

- The WorldVistA VEHU Docker image exposes the RPC Broker on
  port 9430 and SSH on port 2222 by default.
- The VEHU image ships with pre-configured demonstration
  credentials (Access Code: `SM1234`, Verify Code: `SM1234!!`)
  that are sufficient for smoke testing.
- The VEHU RPC Broker speaks the XWB 1.1 protocol variant.
- The library targets the most common RPC parameter types used
  in clinical workflows (literal and list); reference-type
  parameters (global references passed by name) are out of scope
  for this initial version.
- Performance tuning (connection pooling, async I/O) is out of
  scope for this specification; the library targets correctness
  and single-threaded usage first.
- The library is a driver/SDK, not a testing tool—it contains
  no test assertions or test-framework dependencies in its
  public API.
