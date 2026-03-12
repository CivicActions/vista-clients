# Tasks: VistA Terminal Library

**Input**: Design documents from `/specs/002-vista-terminal-library/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Included — smoke tests against a reference VistA environment (VEHU) are required by SC-007.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.
User Story 5 (VistA Login) is reordered before US3/US4 because authentication is a prerequisite for accessing menus that produce paginated or inspectable output during smoke testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/vista_clients/terminal/`, `tests/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency management, directory structure

- [x] T001 Create project directory structure: `src/vista_clients/terminal/`, `tests/unit/`, `tests/contract/`, `tests/smoke/` with `__init__.py` files (terminal package is new; test dirs already exist — add only missing `__init__.py`)
- [x] T002 Update `pyproject.toml` to add `paramiko` as a dependency in `[project.dependencies]`
- [x] T003 [P] Verify `pyproject.toml` tool sections for ruff and pyright are configured per constitution standards (already present from 001 — confirm no changes needed)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types, error hierarchy, internal engines (SSHTransport, ExpectChannel, VT100 stripping) that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

**Covers**: FR-005, FR-019

- [x] T004 [P] Implement exception hierarchy (`TerminalError`, `ConnectionError`, `AuthenticationError`, `SessionError`, `PromptTimeoutError`, `LoginPromptError`, `StateError`) with custom attributes per contracts/api.md in `src/vista_clients/terminal/errors.py`
- [x] T005 [P] Implement `SessionState` enum, `PromptCategory` enum, `CredentialSource` enum, and `CommandRecord` frozen dataclass in `src/vista_clients/terminal/session.py` (types scaffold only — no `VistATerminal` class yet)
- [x] T006 [P] Implement `strip_escape_sequences()` with carriage-return stripping and ANSI/VT100 regex (`\x1b\[[0-9;]*[a-zA-Z?]`) in `src/vista_clients/terminal/vt100.py`
- [x] T007 [P] Add unit tests for `strip_escape_sequences()`: cursor positioning, colour codes, device attributes, `\r` removal, nested sequences, empty input, plain text passthrough in `tests/unit/test_vt100.py`
- [x] T008 [P] Add unit tests verifying all terminal exception types are independently catchable and carry correct attributes (`level`, `partial_output`, `prompt_text`, `current_state`/`required_state`) in `tests/unit/test_errors.py`
- [x] T009 Implement `SSHTransport` class (constructor, `connect()` with `paramiko.SSHClient`, `AutoAddPolicy`, interactive shell via `invoke_shell(term='vt100')`, `channel` property, `close()`, `is_connected` property) in `src/vista_clients/terminal/transport.py`
- [x] T010 [P] Add unit tests for `SSHTransport` with mock `paramiko.SSHClient`: connect, auth failure, channel close, `is_connected` state in `tests/unit/test_transport.py`
- [x] T011 Implement `ExpectChannel` class (`__init__` with incremental UTF-8 decoder via `codecs.getincrementaldecoder`, `expect()` with settle delay and `recv_ready()` polling loop, `send()`, `sendline()`, `buffer` property, output cleaning pipeline: `\r` strip → ANSI strip → result) in `src/vista_clients/terminal/expect.py`
- [x] T012 [P] Add unit tests for `ExpectChannel` with mock channel: pattern matching, settle delay behaviour, timeout raising `PromptTimeoutError` with partial output, multi-byte UTF-8 split across `recv()` calls, `send_ready()` guard in `tests/unit/test_expect.py`
- [x] T013 Define default prompt patterns as compiled regexes grouped by `PromptCategory` (11 patterns from data-model.md: `select_option`, `select_name`, `device`, `default_value`, `access_code`, `verify_code`, `terminal_type`, `press_return`, `caret_stop`, `end_of_report`, `type_enter`) in `src/vista_clients/terminal/session.py`

**Checkpoint**: Foundation ready — all shared types, errors, transport, expect engine, VT100 stripping, and prompt patterns are in place

---

## Phase 3: User Story 1 — Session Lifecycle Management (Priority: P1) 🎯 MVP

**Goal**: Establish SSH connection to VEHU, complete OS-level login, arrive at VistA environment, and disconnect cleanly.

**Independent Test**: SSH to VEHU port 2222, verify banner is consumed and VistA ACCESS CODE prompt is detected, then disconnect.

**Covers**: FR-001, FR-002, FR-003, FR-004, FR-020, FR-021, FR-023, FR-026, FR-027, FR-028

### Implementation for User Story 1

- [x] T014 [US1] Implement `VistATerminal` constructor with parameter validation (port 1–65535, timeout > 0, prompt_timeout > 0, settle_delay ≥ 0) in `src/vista_clients/terminal/session.py`
- [x] T015 [US1] Implement SSH credential resolution (explicit args → `VISTA_SSH_USER`/`VISTA_SSH_PASSWORD` env vars → built-in demonstration defaults `vehutied`/`tied`) in `src/vista_clients/terminal/session.py`
- [x] T016 [US1] Implement `connect()` method: create `SSHTransport`, connect with resolved SSH creds, create `ExpectChannel`, consume banner text, detect `ACCESS CODE:` prompt, transition to `CONNECTED` state, return banner in `src/vista_clients/terminal/session.py`
- [x] T017 [US1] Implement `disconnect()` (close transport, transition to `DISCONNECTED`, safe to call multiple times) and context manager `__enter__`/`__exit__` in `src/vista_clients/terminal/session.py`
- [x] T018 [US1] Implement `state` property, `is_connected` property, and state enforcement helper (raise `StateError` for invalid transitions) in `src/vista_clients/terminal/session.py`
- [x] T019 [P] [US1] Add unit tests for constructor validation (`ValueError` on bad inputs), state machine transitions, SSH credential resolution order, and context manager in `tests/unit/test_session.py`
- [x] T020 [US1] Add smoke test: connect to VEHU port 2222, verify `state == CONNECTED`, verify banner contains `VEHU`, disconnect, verify `state == DISCONNECTED` in `tests/smoke/test_terminal_lifecycle.py`
- [x] T021 [US1] Add smoke test: context manager auto-close (verify disconnected after `with` block exits) in `tests/smoke/test_terminal_lifecycle.py`
- [x] T022 [US1] Add smoke test: connection to unreachable host raises `ConnectionError` in `tests/smoke/test_terminal_lifecycle.py`

**Checkpoint**: User Story 1 complete — can open/close SSH connections to VistA with automatic OS login

---

## Phase 4: User Story 2 — Prompt Recognition and Command Execution (Priority: P2)

**Goal**: Send commands to VistA and reliably wait for the next prompt before returning cleaned output.

**Independent Test**: Connect to VEHU, detect initial prompt, send a command, verify output returned between command echo and next prompt.

**Covers**: FR-006, FR-007, FR-008, FR-015, FR-022, FR-024, FR-029

### Implementation for User Story 2

- [x] T023 [US2] Implement `send()` method (raw text to channel, no prompt wait, state check) in `src/vista_clients/terminal/session.py`
- [x] T024 [US2] Implement `send_and_wait()` method: sendline, wait for prompt via `ExpectChannel.expect()`, apply output cleaning pipeline (echo strip → `\r` strip → VT100 strip), return cleaned output in `src/vista_clients/terminal/session.py`
- [x] T025 [US2] Implement `wait_for()` method (block until pattern matches, no input sent, return `(match, text_before)` tuple) in `src/vista_clients/terminal/session.py`
- [x] T026 [P] [US2] Add contract tests: each of the 11 default prompt patterns matches known VEHU output samples (captured from research.md) in `tests/contract/test_prompt_patterns.py`
- [x] T027 [US2] Add unit tests for `send_and_wait()` output cleaning: command echo removal, VT100 stripping, `\r` stripping in `tests/unit/test_session.py`
- [x] T028 [US2] Add smoke test: connect to VEHU, send a command string, verify cleaned output returned and next prompt detected in `tests/smoke/test_terminal_lifecycle.py`
- [x] T029 [US2] Add smoke test: `send_and_wait()` with custom prompt pattern (regex string) in `tests/smoke/test_terminal_lifecycle.py`
- [x] T030 [US2] Add smoke test: prompt timeout raises `PromptTimeoutError` with `partial_output` attribute populated in `tests/smoke/test_terminal_lifecycle.py`

**Checkpoint**: User Story 2 complete — can send commands and receive prompt-synchronised output

---

## Phase 5: User Story 5 — VistA Application Login (Priority: P5)

**Goal**: Authenticate with VistA using Access Code / Verify Code, navigate terminal type selection, and arrive at the main menu.

**Independent Test**: Connect to VEHU, call `login()` with defaults, verify AUTHENTICATED state and greeting text.

**Note**: Reordered before US3/US4 because authentication is prerequisite for accessing VistA menus in smoke tests.

**Covers**: FR-017, FR-018, FR-030

### Implementation for User Story 5

- [x] T031 [US5] Implement VistA credential resolution (explicit args → `VISTA_ACCESS_CODE`/`VISTA_VERIFY_CODE` env vars → built-in demonstration defaults `PRO1234`/`PRO1234!!`) in `src/vista_clients/terminal/session.py`
- [x] T032 [US5] Implement `login()` method: enter Access Code at `ACCESS CODE:` prompt, enter Verify Code at `VERIFY CODE:` prompt, accept default terminal type at `Select TERMINAL TYPE NAME:` prompt, detect main menu prompt, transition to `AUTHENTICATED` state, return greeting text in `src/vista_clients/terminal/session.py`
- [x] T033 [US5] Add `LoginPromptError` handling in `login()`: detect unrecognised intermediate prompts (any prompt that isn't `VERIFY CODE:`, `TERMINAL TYPE NAME:`, or a known menu prompt) and raise with `prompt_text` attribute in `src/vista_clients/terminal/session.py`
- [x] T034 [P] [US5] Add unit tests for VistA credential resolution order (explicit overrides env, env overrides defaults) in `tests/unit/test_session.py`
- [x] T035 [US5] Add smoke test: `connect()` then `login()` with built-in demonstration defaults, verify `state == AUTHENTICATED` and greeting contains `DOCTOR` in `tests/smoke/test_terminal_lifecycle.py`
- [x] T036 [US5] Add smoke test: `login()` with invalid credentials raises `AuthenticationError` with `level == "vista"` in `tests/smoke/test_terminal_lifecycle.py`

**Checkpoint**: User Story 5 complete — can authenticate with VistA and reach the main menu

---

## Phase 6: User Story 3 — Pagination Handling / Auto-Scroll (Priority: P3)

**Goal**: Automatically advance through paginated VistA output, capturing the full text of multi-page reports.

**Independent Test**: Navigate to a VistA menu producing paginated output, enable auto-scroll, verify complete output captured.

**Covers**: FR-009, FR-010, FR-011, FR-012

### Implementation for User Story 3

- [x] T037 [US3] Implement `auto_scroll` property (getter/setter, default `False`) and `max_pages` property (getter/setter, default `100`, must be ≥ 1) in `src/vista_clients/terminal/session.py`
- [x] T038 [US3] Implement pagination detection and auto-advance in `send_and_wait()`: when `auto_scroll` is enabled (session-level or per-call override), detect pagination prompts, send return keystroke, accumulate output, repeat until non-pagination prompt or `max_pages` reached in `src/vista_clients/terminal/session.py`
- [x] T039 [P] [US3] Add unit tests for pagination pattern matching (all 4 pagination regexes) and `max_pages` limit enforcement in `tests/unit/test_session.py`
- [x] T040 [US3] Add smoke test: enable `auto_scroll`, navigate to paginated VistA output, verify complete multi-page text captured in `tests/smoke/test_terminal_lifecycle.py`
- [x] T041 [US3] Add smoke test: `auto_scroll` disabled (default), verify pagination prompt treated as normal prompt and partial output returned in `tests/smoke/test_terminal_lifecycle.py`

**Checkpoint**: User Story 3 complete — auto-scroll captures full paginated reports

---

## Phase 7: User Story 4 — Screen Buffer Extraction (Priority: P4)

**Goal**: Expose accumulated output via properties and provide substring/regex search methods for test assertions.

**Independent Test**: Execute commands, verify `session_history` contains correct `CommandRecord` entries, search output by pattern.

**Covers**: FR-013, FR-014, FR-016

### Implementation for User Story 4

- [x] T042 [US4] Implement `last_output`, `raw_last_output`, and `full_output` properties in `src/vista_clients/terminal/session.py`
- [x] T043 [US4] Implement `session_history` tracking: append `CommandRecord` after each `send_and_wait()` call, maintain ordered list in `src/vista_clients/terminal/session.py`
- [x] T044 [US4] Implement `contains()` (substring search on cleaned last output) and `search()` (regex search on cleaned last output) methods in `src/vista_clients/terminal/session.py`
- [x] T045 [P] [US4] Add unit tests for buffer properties (`last_output`, `raw_last_output`, `full_output`, `session_history`), `contains()`, and `search()` in `tests/unit/test_session.py`
- [x] T046 [US4] Add smoke test: execute multiple commands, verify `session_history` length and `CommandRecord` fields, verify `contains()` and `search()` against known output in `tests/smoke/test_terminal_lifecycle.py`

**Checkpoint**: User Story 4 complete — output buffer is inspectable and searchable

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Public API surface, documentation, logging, final integration validation

- [x] T047 [P] Create public re-exports in `src/vista_clients/terminal/__init__.py` per contracts/api.md: `VistATerminal`, `CommandRecord`, `SessionState`, `strip_escape_sequences`, and all error types
- [x] T048 [P] Add Google-style docstrings to all public classes, methods, and functions in `src/vista_clients/terminal/session.py`, `src/vista_clients/terminal/vt100.py`, `src/vista_clients/terminal/errors.py`
- [x] T049 [P] Add Python logging throughout: create loggers in `session.py`, `transport.py`, `expect.py`; add DEBUG-level calls for raw terminal I/O in `expect.py` read loop; add INFO-level calls for lifecycle events (connect, login, disconnect) in `session.py`; add credential redaction replacing SSH password, Access Code, and Verify Code values with `***REDACTED***` at all log levels (FR-024) in `src/vista_clients/terminal/session.py`, `src/vista_clients/terminal/transport.py`, `src/vista_clients/terminal/expect.py`
- [x] T050 Add full lifecycle smoke test: connect → login → send command → auto-scroll paginated output → search buffer → disconnect (single test validating SC-002) in `tests/smoke/test_terminal_lifecycle.py`
- [x] T051 Validate quickstart.md code examples execute against a reference VistA environment (VEHU) (SC-001: under 15 lines of code for basic usage) in `tests/smoke/test_quickstart.py`
- [x] T052 [P] Run linting (`ruff check`), formatting (`ruff format`), and type checking (`pyright` basic mode) — fix all violations
- [x] T053 [P] Verify pure-Python constraint: audit all imports in `src/vista_clients/terminal/`, confirm no platform-specific or compiled extensions beyond `paramiko` and no automatic retry logic (FR-025, FR-026, FR-027)
- [x] T054 [P] Verify library runs in minimal Alpine container: update `Dockerfile.test` to include `paramiko`, run `tests/unit/` inside container (SC-008)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no other story dependencies
- **US2 (Phase 4)**: Depends on Phase 2 + US1 (needs connected session for send/wait)
- **US5 (Phase 5)**: Depends on Phase 2 + US2 (login flow uses prompt recognition)
- **US3 (Phase 6)**: Depends on Phase 2 + US2 (auto-scroll extends send_and_wait)
- **US4 (Phase 7)**: Depends on Phase 2 + US2 (buffer tracks send_and_wait output)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
    └─► Phase 2 (Foundational)
            └─► US1: Session Lifecycle (Phase 3)
                    └─► US2: Prompt Recognition (Phase 4)
                            ├─► US5: VistA Login (Phase 5)
                            ├─► US3: Auto-Scroll (Phase 6)
                            └─► US4: Buffer Extraction (Phase 7)
                                    └─► Phase 8 (Polish)
```

**Note**: US3 and US4 can run in parallel after US2. US5 is placed before them because authenticated sessions are needed for meaningful smoke testing of US3/US4, but they have no code dependency on US5.

### Within Each User Story

- Implementation tasks before smoke tests (smoke tests validate the implementation)
- Session methods are sequential within `session.py` (same file)
- Unit tests marked [P] can run in parallel with implementation (different files)
- Contract tests marked [P] can run in parallel with implementation
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 2** (Foundational):
- T004 (errors.py) ∥ T005 (session.py types) ∥ T006 (vt100.py) ∥ T007 (test_vt100.py) ∥ T008 (test_errors.py) — all different files
- T009 (transport.py) after T004 (uses error types); T010 (test_transport.py) ∥ T009
- T011 (expect.py) after T004 + T006 (uses errors + vt100); T012 (test_expect.py) ∥ T011
- T013 (prompt patterns in session.py) after T005 (same file)

**Phase 3** (US1):
- T019 (test_session.py) ∥ T014–T018 (session.py implementation) — different files

**Phase 4** (US2):
- T026 (test_prompt_patterns.py) ∥ T023–T025 (session.py methods) — different files

**Phase 5** (US5):
- T034 (test_session.py) ∥ T031–T033 (session.py methods) — different files

**Phase 6–7** (US3/US4):
- US3 and US4 can run in parallel (US3 modifies send_and_wait; US4 adds properties/methods — minimal overlap)

**Phase 8** (Polish):
- T047 (__init__.py) ∥ T048 (docstrings) ∥ T049 (logging) ∥ T052 (linting) ∥ T053 (audit) ∥ T054 (container) — all independent

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch all independent foundational tasks (different files):
Task T004: "Implement exception hierarchy in src/vista_clients/terminal/errors.py"
Task T005: "Implement enums and CommandRecord in src/vista_clients/terminal/session.py"
Task T006: "Implement strip_escape_sequences in src/vista_clients/terminal/vt100.py"
Task T007: "Unit tests for VT100 stripping in tests/unit/test_vt100.py"
Task T008: "Unit tests for error hierarchy in tests/unit/test_errors.py"

# Then transport + expect (depend on errors.py):
Task T009: "Implement SSHTransport in src/vista_clients/terminal/transport.py"
Task T010: "Unit tests for SSHTransport in tests/unit/test_transport.py"  # parallel with T009
Task T011: "Implement ExpectChannel in src/vista_clients/terminal/expect.py"
Task T012: "Unit tests for ExpectChannel in tests/unit/test_expect.py"  # parallel with T011

# Then prompt patterns (depends on session.py types):
Task T013: "Define default prompt patterns in src/vista_clients/terminal/session.py"
```

## Parallel Example: US3 ∥ US4 (after US2)

```bash
# These two stories can be worked on simultaneously by different agents:
# Agent A: US3 (pagination in send_and_wait)
Task T037-T041: Auto-scroll properties and pagination logic

# Agent B: US4 (buffer properties and search methods)
Task T042-T046: Output buffer, history, contains(), search()
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 — Session Lifecycle
4. **STOP and VALIDATE**: Test SSH connect/disconnect against a reference VistA environment (VEHU)
5. Delivers value: proof that SSH transport + OS login + VistA environment detection works

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1: Session Lifecycle → SSH connect/disconnect works (MVP!)
3. US2: Prompt Recognition → Can send commands and read output
4. US5: VistA Login → Can authenticate and access clinical menus
5. US3: Auto-Scroll → Can capture full paginated reports
6. US4: Buffer Extraction → Can inspect and search output
7. Polish → Docstrings, re-exports, linting, quickstart validation
8. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 → US2 → US5 (sequential dependency chain)
   - After US2 completes: Developer B can start US3 ∥ Developer C can start US4
3. Stories can integrate and test independently

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [US*] label maps task to specific user story for traceability
- US5 is reordered before US3/US4 for practical reasons (authenticated session needed for smoke testing)
- US3 and US4 can be parallelised after US2 — they have no code dependency on each other
- US1 → US2 → US5 is a sequential dependency chain (each builds on the previous)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- `session.py` is the largest file — tasks within the same story are sequential (same file)
