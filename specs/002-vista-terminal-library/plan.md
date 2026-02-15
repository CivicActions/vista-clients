# Implementation Plan: VistA Terminal Library

**Branch**: `002-vista-terminal-library` | **Date**: 2026-02-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-vista-terminal-library/spec.md`

## Summary

Implement a pure-Python VistA terminal interaction library that provides programmatic access to VistA's Roll-and-Scroll menu interface via SSH. The library wraps `paramiko` with a custom expect-style engine to handle VistA's interactive prompts, pagination, and VT100 escape sequences behind a clean Pythonic API. A three-state session machine (DISCONNECTED → CONNECTED → AUTHENTICATED) manages the SSH connection and VistA login flow. Built from empirical analysis of the VEHU Docker image's SSH login sequence, ZU.m entry-point source, and GMTSUP.m pagination patterns.

## Technical Context

**Language/Version**: Python 3.10+  
**Primary Dependencies**: `paramiko` (pure-Python SSH2 implementation; replaces constitution's `pexpect` for cross-platform SSH support — see Constitution Check)  
**Storage**: N/A  
**Testing**: pytest  
**Target Platform**: macOS, Linux, Windows (cross-platform via pure Python + paramiko)  
**Project Type**: single (library package)  
**Performance Goals**: N/A (interactive terminal I/O at human-interaction speeds; bottleneck is VistA server response, not library throughput)  
**Constraints**: Pure Python only (no FFI, no compiled extensions), must run in Alpine Linux containers, 500ms default settling delay for prompt detection  
**Scale/Scope**: ~5 modules, ~800-1200 LOC library code, ~500 LOC tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Pure Python Portability | ✅ PASS | `paramiko` is a pure-Python SSH2 library (no compiled extensions). All other code is stdlib-only. Runs identically on macOS, Linux, and Windows. |
| II | Container-First Standardization | ✅ PASS | Default SSH port 2222, default credentials vehutied/tied (SSH) + PRO1234/PRO1234!! (VistA). All smoke tests target `worldvista/vehu`. |
| III | Separation of Concerns | ✅ PASS | Library contains zero test assertions. Four-layer architecture (transport/expect/session/vt100) with strict boundaries. |
| IV | Idempotency & State Management | ✅ PASS | Library is read-only — it sends commands and reads output but does not modify VistA globals. State management deferred to test suite. |
| V | Technology Agnosticism in Specs | ✅ PASS | Spec describes intent ("connect to terminal", "recognise prompt"). Plan describes implementation ("paramiko SSH", "expect engine"). |

### Operational Standards Tension

The Constitution's Operational Standards table specifies `pexpect` for Terminal Protocol. This plan uses `paramiko` instead.

**Justification**: `pexpect` spawns a local child process and uses Unix pty for I/O control. It does not provide SSH client capability — it would require wrapping the system `ssh` command, defeating the "pure Python" goal and introducing a platform dependency (no `ssh.exe` on Windows by default). `paramiko` provides a native Python SSH2 implementation with interactive shell channels, satisfying both Principle I (pure Python portability) and the functional requirements for SSH-based terminal access.

**Proposed Constitutional Amendment**: Update the Terminal Protocol entry in the Operational Standards table from `pexpect (over telnetlib)` to `paramiko` with rationale: "Pure-Python SSH2 implementation; replaces pexpect for cross-platform SSH terminal access."

**Gate Result**: ALL PASS — operational standards tension documented and justified via Principle I precedence.

## Project Structure

### Documentation (this feature)

```text
specs/002-vista-terminal-library/
├── plan.md              # This file
├── research.md          # Phase 0: VEHU SSH research, library comparison, prompt patterns
├── data-model.md        # Phase 1: Entity definitions and state machine
├── quickstart.md        # Phase 1: Usage guide and examples
├── contracts/
│   └── api.md           # Phase 1: Public API surface contracts
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vista_test/terminal/
├── __init__.py          # Public re-exports (VistATerminal, errors, CommandRecord, etc.)
├── session.py           # VistATerminal: high-level session orchestrator, state machine
├── expect.py            # ExpectChannel: pexpect-style prompt matching over paramiko channel
├── transport.py         # SSHTransport: paramiko SSH wrapper for interactive shell
├── vt100.py             # VT100/ANSI escape sequence stripping
└── errors.py            # TerminalError exception hierarchy

tests/
├── unit/
│   ├── test_errors.py   # Exception hierarchy catchability and attributes
│   ├── test_expect.py   # ExpectChannel prompt matching, settle delay, timeout
│   ├── test_session.py  # State machine transitions, credential resolution
│   ├── test_transport.py # SSHTransport with mock paramiko.SSHClient
│   └── test_vt100.py    # Escape sequence stripping edge cases
├── contract/
│   └── test_prompt_patterns.py  # Known-good prompt regex matching against VEHU output
└── smoke/
    ├── test_terminal_lifecycle.py  # Full connect→login→command→disconnect against VEHU
    └── test_quickstart.py          # Quickstart code examples against VEHU
```

**Structure Decision**: Single-project layout matching the existing `src/vista_test/rpc/` pattern. The `src/vista_test/terminal/` package contains the library. Tests are in a parallel `tests/` tree with three tiers: unit (no server), contract (no server, pattern verification), and smoke (requires VEHU Docker on port 2222).

## pytest-xdist Compatibility

The library architecture is compatible with `pytest-xdist` parallel test execution:

- **No shared mutable state**: Each `VistATerminal` instance owns its own `SSHTransport` (paramiko channel) and session state. No module-level globals or singletons.
- **Process isolation**: xdist spawns separate worker processes, each with independent memory. Multiple workers can SSH to VEHU simultaneously on separate connections.
- **No file locks**: The library does not write to disk or use file-based coordination.
- **Logging**: Python's `logging` module is process-safe; each worker gets its own logger hierarchy.
- **VEHU SSH concurrency**: The SSH daemon on VEHU accepts multiple concurrent connections. Each SSH session gets an independent `mumps -r ZU` process with its own M partition.

No special xdist fixtures or `worker_id`-based isolation are required for the library itself.

## Complexity Tracking

> No constitution violations — operational standards tension is documented and justified above.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | — | — |
