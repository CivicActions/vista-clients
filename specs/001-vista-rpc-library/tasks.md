# Tasks: VistA RPC Broker Library

**Input**: Design documents from `/specs/001-vista-rpc-library/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Included — smoke tests against VEHU are required by SC-006.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/vista_test/rpc/`, `tests/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency management, directory structure

- [X] T001 Create project directory structure: `src/vista_test/rpc/`, `tests/unit/`, `tests/contract/`, `tests/smoke/` with `__init__.py` files
- [X] T002 Update `pyproject.toml` with pytest dependency, test configuration, and package metadata per plan.md
- [X] T003 [P] Configure `pyproject.toml` tool sections for ruff and pyright per constitution standards

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types, enumerations, and error hierarchy that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 [P] Implement exception hierarchy (`VistAError`, `ConnectionError`, `HandshakeError`, `AuthenticationError`, `ContextError`, `RPCError`, `StateError`) in `src/vista_test/rpc/errors.py`
- [X] T005 [P] Implement enumerations (`ParamType`, `SessionState`, `CredentialSource` [internal]) and data classes (`RPCParameter`, `RPCResponse`) with factory functions (`literal()`, `list_param()`) in `src/vista_test/rpc/protocol.py` (types-only scaffold; message building comes in US2)
- [X] T006 Implement protocol encoding primitives (`spack()`, `lpack()`) in `src/vista_test/rpc/protocol.py`. L-PACK must use 3-digit format for values ≤999 chars and 5-digit format for values >999 chars (per XWB*1.1*65)
- [X] T007 [P] Add unit tests for `spack()` and `lpack()` encoding in `tests/unit/test_protocol.py`, including L-PACK boundary tests at 999/1000 chars for dynamic width switching
- [X] T008 Configure logging with credential redaction helper in `src/vista_test/rpc/broker.py` (module-level logger setup only; class comes in US1)

**Checkpoint**: Foundation ready — all shared types, errors, and encoding primitives are in place

---

## Phase 3: User Story 1 — Connection Establishment (Priority: P1) 🎯 MVP

**Goal**: Establish TCP connections to a VistA server with configurable timeout, graceful close, and context manager support.

**Independent Test**: Open a connection to VEHU on port 9430, verify the TCP session is established, and close it cleanly.

**Covers**: FR-001, FR-002, FR-010, FR-013, FR-017

### Implementation for User Story 1

- [X] T009 [US1] Implement `Transport` class (connect, send, receive with `chr(4)` framing, close, `is_connected` property) in `src/vista_test/rpc/transport.py`
- [X] T010 [US1] Add broken-connection detection (socket errors during send/receive raise `ConnectionError`) in `src/vista_test/rpc/transport.py`
- [X] T011 [US1] Implement `VistABroker` class scaffold with constructor, `connect()` (TCP-only, no handshake yet), `disconnect()`, `is_connected`, `state` property, and context manager (`__enter__`/`__exit__`) in `src/vista_test/rpc/broker.py`
- [X] T012 [US1] Add unit tests for `Transport` using mock socket (send framing, receive until `chr(4)`, timeout, broken connection) in `tests/unit/test_transport.py`
- [X] T013 [US1] Add smoke test: TCP connect to VEHU port 9430, verify `is_connected`, disconnect, verify disconnected in `tests/smoke/test_lifecycle.py`
- [X] T053 [US1] Add unit tests for transport edge cases: TCP fragment reassembly, connection-refused vs timeout error distinction, and mid-receive connection drop in `tests/unit/test_transport.py`

**Checkpoint**: User Story 1 complete — can open/close TCP connections to VistA with timeout and context manager

---

## Phase 4: User Story 2 — Broker Handshake and Context Creation (Priority: P2)

**Goal**: Perform the XWB protocol handshake (TCPConnect command) and support setting/switching application contexts via `XWB CREATE CONTEXT`.

**Independent Test**: Connect to VEHU, perform handshake, verify server returns "accept", then create a context and verify success.

**Covers**: FR-003, FR-004 (implementation; smoke-tested in Phase 6), FR-009 (handshake/context errors), FR-014 (state enforcement)

### Implementation for User Story 2

- [X] T014 [P] [US2] Implement OSEHRA cipher table, `encrypt()` and `decrypt()` functions in `src/vista_test/rpc/protocol.py`
- [X] T015 [P] [US2] Add unit tests for cipher `encrypt()`/`decrypt()` round-trip and known test vectors in `tests/unit/test_protocol.py`
- [X] T016 [US2] Implement `build_connect_message()` (TCPConnect command with hostname and app_name) in `src/vista_test/rpc/protocol.py`
- [X] T017 [US2] Implement `build_rpc_message()` for RPC invocation (protocol prefix, S-PACK name, parameter encoding for literal and list types) in `src/vista_test/rpc/protocol.py`
- [X] T018 [US2] Implement `build_disconnect_message()` (`#BYE#` RPC) in `src/vista_test/rpc/protocol.py`
- [X] T019 [US2] Add unit tests for `build_connect_message()` and `build_disconnect_message()` verifying exact byte output in `tests/unit/test_protocol.py`
- [X] T020 [US2] Add contract tests verifying wire format against known-good byte sequences from reference implementation in `tests/contract/test_wire_format.py`
- [X] T060 [US2] Add unit test validating that `build_rpc_message()` raises `ValueError` when a list parameter is not the last parameter in `tests/unit/test_protocol.py`
- [X] T021 [US2] Update `VistABroker.connect()` to include XWB handshake: send TCPConnect, validate "accept" response, transition to HANDSHAKED state in `src/vista_test/rpc/broker.py`
- [X] T022 [US2] Implement `VistABroker.create_context()` with option name encryption and `XWB CREATE CONTEXT` RPC in `src/vista_test/rpc/broker.py`
- [X] T023 [US2] Add session state enforcement: reject operations in invalid states, raise `StateError` in `src/vista_test/rpc/broker.py`
- [X] T024 [US2] Update `VistABroker.disconnect()` to send `#BYE#` before closing socket in `src/vista_test/rpc/broker.py`
- [X] T025 [US2] Add smoke test: connect to VEHU, verify handshake succeeds (state=HANDSHAKED), disconnect cleanly in `tests/smoke/test_lifecycle.py`
- [X] T054 [US2] Add unit tests for session state enforcement: verify `StateError` raised for `call_rpc()` before context set, `authenticate()` before handshake, `create_context()` before auth in `tests/unit/test_broker.py`
- [X] T055 [US2] Add unit test for handshake failure: mock server rejection response, verify `HandshakeError` raised in `tests/unit/test_broker.py`

**Checkpoint**: User Story 2 complete — can handshake with VistA server and set application context

---

## Phase 5: User Story 3 — Authentication (Priority: P3)

**Goal**: Authenticate sessions using encrypted Access/Verify codes with configurable credential sourcing (explicit, environment, defaults).

**Independent Test**: Connect to VEHU, handshake, authenticate with VEHU defaults, verify DUZ is returned.

**Covers**: FR-005, FR-006, FR-009 (auth errors), FR-015 (credential redaction in logs)

### Implementation for User Story 3

- [X] T026 [US3] Implement credential resolution logic (explicit → env vars → VEHU defaults) in `src/vista_test/rpc/broker.py`
- [X] T027 [US3] Implement `VistABroker.authenticate()`: send `XUS SIGNON SETUP`, encrypt credentials, send `XUS AV CODE`, parse DUZ from response, transition to AUTHENTICATED state in `src/vista_test/rpc/broker.py`
- [X] T028 [US3] Add credential redaction to all logging statements (replace access/verify values with `***REDACTED***`) in `src/vista_test/rpc/broker.py`
- [X] T029 [US3] Add unit test for credential resolution order (explicit overrides env, env overrides defaults) in `tests/unit/test_broker.py`
- [X] T030 [US3] Add smoke test: authenticate with VEHU defaults, verify DUZ > 0 returned in `tests/smoke/test_lifecycle.py`
- [X] T031 [US3] Add smoke test: authenticate with invalid credentials, verify `AuthenticationError` raised in `tests/smoke/test_lifecycle.py`
- [X] T056 [US3] Add smoke test: authenticate with credentials containing special characters (`!`, `@`, spaces), verify successful login in `tests/smoke/test_lifecycle.py`

**Checkpoint**: User Story 3 complete — can authenticate with VistA and receive DUZ

---

## Phase 6: User Story 4 — RPC Invocation with Typed Parameters (Priority: P4)

**Goal**: Invoke any named RPC with literal and list parameter types, with proper state enforcement.

**Independent Test**: Authenticate to VEHU, set context, call `XWB GET VARIABLE VALUE` with a literal parameter, verify result returned.

**Covers**: FR-007, FR-009 (RPC errors), FR-014 (state enforcement), FR-016 (no retries)

### Implementation for User Story 4

- [X] T032 [US4] Implement `VistABroker.call_rpc()`: build RPC message, send via transport, receive raw response, return `RPCResponse` in `src/vista_test/rpc/broker.py`
- [X] T033 [US4] Implement `VistABroker.ping()`: send `XWB IM HERE` RPC for keepalive in `src/vista_test/rpc/broker.py`
- [X] T034 [US4] Add wire-level DEBUG logging to `call_rpc()` (bytes sent/received, with credential redaction) in `src/vista_test/rpc/broker.py`
- [X] T035 [US4] Add unit tests for RPC message building with no params, literal param, list param, and mixed params in `tests/unit/test_protocol.py`
- [X] T036 [US4] Add smoke test: authenticate, set context, call RPC with no parameters, verify response in `tests/smoke/test_lifecycle.py`
- [X] T037 [US4] Add smoke test: call RPC with literal parameter, verify server processes correctly in `tests/smoke/test_lifecycle.py`
- [X] T038 [US4] Add smoke test: call non-existent RPC, verify `RPCError` raised in `tests/smoke/test_lifecycle.py`
- [X] T057 [US4] Add smoke test: switch context by calling `create_context()` twice with different options, verify second context is active in `tests/smoke/test_lifecycle.py`
- [X] T059 [US4] Add smoke test: call an RPC outside the active context's permission set, verify `RPCError` raised with server's permission-denied message (EC-06, XWBSEC error prefix) in `tests/smoke/test_lifecycle.py`

**Checkpoint**: User Story 4 complete — can invoke RPCs with typed parameters

---

## Phase 7: User Story 5 — Response Parsing (Priority: P5)

**Goal**: Parse VistA responses (single value, array, global array) into native Python objects.

**Independent Test**: Call RPCs known to return different response types and verify Python representations.

**Covers**: FR-008

### Implementation for User Story 5

- [X] T039 [US5] Implement `parse_response()` function: extract security/error prefix packets (per XWBRW.m `SNDERR`), raise `RPCError` if non-empty, then detect single vs array response, return `RPCResponse` with `value` or `lines` populated in `src/vista_test/rpc/protocol.py`
- [X] T040 [US5] Wire `parse_response()` into `VistABroker.call_rpc()` return path in `src/vista_test/rpc/broker.py`
- [X] T041 [P] [US5] Add unit tests for `parse_response()`: single value, array (CR+LF delimited), word-processing (FR-008), empty response, security/error prefix extraction, and `RPCError` on non-empty error prefix in `tests/unit/test_protocol.py`
- [X] T042 [US5] Add smoke test: call RPC returning single value, verify `response.value` is a string in `tests/smoke/test_lifecycle.py`
- [X] T043 [US5] Add smoke test: call RPC returning array, verify `response.lines` is a list of strings in `tests/smoke/test_lifecycle.py`
- [X] T058 [US5] Add unit test for `parse_response()` with non-empty security packet: verify `RPCError` raised with server's error message extracted from length-prefixed prefix in `tests/unit/test_protocol.py`

**Checkpoint**: User Story 5 complete — full round-trip: connect → handshake → auth → context → RPC → parsed Python response → disconnect

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Public API surface, documentation, final integration validation

- [X] T044 [P] Create public re-exports in `src/vista_test/rpc/__init__.py` per contracts/api.md
- [X] T045 [P] Add Google-style docstrings to all public classes, methods, and functions in `src/vista_test/rpc/broker.py`, `src/vista_test/rpc/protocol.py`, `src/vista_test/rpc/transport.py`, `src/vista_test/rpc/errors.py`
- [X] T046 Add full lifecycle smoke test: connect → authenticate → context → call RPC → parse response → disconnect (single test validating SC-002) in `tests/smoke/test_lifecycle.py`
- [X] T047 Validate quickstart.md code examples execute against VEHU (SC-001: 10-line usage) in `tests/smoke/test_quickstart.py`
- [X] T048 [P] Run linting (`ruff check`), formatting (`ruff format`), and type checking (pyright basic) per tool config in `pyproject.toml`
- [X] T049 [P] Add unit test verifying all exception types are independently catchable (SC-004) in `tests/unit/test_errors.py`
- [X] T050 Verify pure-Python constraint: audit all imports, confirm no native extensions or platform-specific deps (FR-011, FR-012) in `tests/unit/test_stdlib_only.py`
- [X] T051 Run full `tests/smoke/` suite against VEHU and confirm 100% pass rate (SC-006). Verify FR-016 by grepping `src/vista_test/rpc/` for `retry|retries|attempt` and asserting zero matches
- [X] T052 [P] Verify library runs in minimal container: build Alpine-based Docker image, install Python, run `tests/unit/` (SC-003) via `Dockerfile.test`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no other story dependencies
- **US2 (Phase 4)**: Depends on Phase 2 + US1 (needs `Transport` for send/receive)
- **US3 (Phase 5)**: Depends on Phase 2 + US2 (needs handshake before auth)
- **US4 (Phase 6)**: Depends on Phase 2 + US3 (needs auth before RPC)
- **US5 (Phase 7)**: Depends on Phase 2 + US4 (needs RPC invocation to parse responses)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
    └─► Phase 2 (Foundational)
            └─► US1: Connection (Phase 3)
                    └─► US2: Handshake & Context (Phase 4)
                            └─► US3: Authentication (Phase 5)
                                    └─► US4: RPC Invocation (Phase 6)
                                            └─► US5: Response Parsing (Phase 7)
                                                    └─► Phase 8 (Polish)
```

### Within Each User Story

- Implementation before tests that depend on it (for smoke tests)
- Protocol functions before broker methods that use them
- Core implementation before integration with previous stories
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 2** (Foundational):
- T004 (errors.py) ∥ T005 (protocol.py) ∥ T007 (test_protocol.py) — different files; T006 follows T005 (same file)

**Phase 4** (US2):
- T014 (cipher in protocol.py) ∥ T015 (cipher tests in test_protocol.py) — different files
- T016, T017, T018 (message builders) are sequential within protocol.py but independent of cipher tests

**Phase 7** (US5):
- T041 (parse unit tests) can run in parallel with T039 (parse implementation) if TDD approach

**Phase 8** (Polish):
- T044 (__init__.py) ∥ T045 (docstrings) ∥ T048 (linting) — all independent

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch parallel foundational tasks (different files):
Task T004: "Implement exception hierarchy in src/vista_test/rpc/errors.py"
Task T005: "Implement enumerations and data classes in src/vista_test/rpc/protocol.py"
Task T007: "Add unit tests for spack/lpack in tests/unit/test_protocol.py"
# Then T006 (spack/lpack in protocol.py) after T005 — same file
```

## Parallel Example: Phase 4 (User Story 2)

```bash
# Launch cipher implementation + tests together (different files):
Task T014: "Implement cipher encrypt/decrypt in src/vista_test/rpc/protocol.py"
Task T015: "Add cipher unit tests in tests/unit/test_protocol.py"
# Then T016-T018 (message builders in protocol.py) sequentially after T014
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 — Connection Establishment
4. **STOP and VALIDATE**: Test TCP connect/disconnect against VEHU
5. Delivers value: proof that transport layer works across platforms

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1: Connection → TCP connect/disconnect works (MVP!)
3. US2: Handshake → XWB protocol negotiation works
4. US3: Authentication → Credentials accepted, DUZ returned
5. US4: RPC Invocation → Can call any RPC with parameters
6. US5: Response Parsing → Full round-trip with Python objects
7. Polish → Docstrings, linting, quickstart validation
8. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [US*] label maps task to specific user story for traceability
- This project has a LINEAR dependency chain (US1 → US2 → US3 → US4 → US5) because each story builds on the previous
- Parallelism exists WITHIN phases (e.g., multiple message builders) but NOT between user stories
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
