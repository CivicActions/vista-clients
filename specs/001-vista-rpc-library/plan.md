# Implementation Plan: VistA RPC Broker Library

**Branch**: `001-vista-rpc-library` | **Date**: 2026-02-14 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-vista-rpc-library/spec.md`

## Summary

Implement a pure-Python VistA RPC Broker library that abstracts the XWB 1.1 wire protocol behind a clean Pythonic API. The library provides a four-layer architecture (Transport → Protocol → Broker → public re-exports) enabling developers to connect, authenticate, set context, and invoke RPCs against any VistA server in under 10 lines of code. Built from first principles using the VA Developer's Guide, MUMPS server source code, and the XWB protocol specification—no vendor DLLs or platform-specific dependencies.

## Technical Context

**Language/Version**: Python 3.10+  
**Primary Dependencies**: None (pure Python, stdlib only: `socket`, `logging`, `os`, `enum`, `dataclasses`)  
**Storage**: N/A  
**Testing**: pytest  
**Target Platform**: macOS, Linux, Windows (cross-platform via pure Python sockets)  
**Project Type**: single (library package)  
**Performance Goals**: N/A (correctness-first; single-threaded, no connection pooling in v1)  
**Constraints**: Pure Python only (no FFI, no compiled extensions), must run in Alpine Linux containers  
**Scale/Scope**: ~4 modules, ~800-1200 LOC library code, ~500 LOC tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Pure Python Portability | ✅ PASS | Zero compiled dependencies. Uses only `socket`, `logging`, `os`, `enum`, `dataclasses` from stdlib. XWB protocol reimplemented natively. |
| II | Container-First Standardization | ✅ PASS | Default port 9430, default credentials SM1234/SM1234!!, all smoke tests target `worldvista/vehu`. |
| III | Separation of Concerns | ✅ PASS | Library contains zero test assertions. Four-layer architecture (transport/protocol/broker/errors) with strict boundaries. |
| IV | Idempotency & State Management | ✅ PASS | Library is read-only — it invokes RPCs but does not write to VistA globals. State management deferred to test suite. |
| V | Technology Agnosticism in Specs | ✅ PASS | Spec describes intent ("authenticate", "invoke RPC"). Plan describes implementation ("XWB cipher", "S-PACK encoding"). |

**Gate Result**: ALL PASS — no violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/001-vista-rpc-library/
├── plan.md              # This file
├── research.md          # Phase 0: XWB protocol research findings
├── data-model.md        # Phase 1: Entity definitions and state machine
├── quickstart.md        # Phase 1: Usage guide and examples
├── contracts/
│   └── api.md           # Phase 1: Public API surface contracts
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/vista_clients/rpc/
├── __init__.py          # Public re-exports (VistABroker, literal, list_param, errors)
├── broker.py            # VistABroker: high-level lifecycle orchestrator
├── protocol.py          # XWB message construction, S/L-PACK, cipher, response parsing
├── transport.py         # TCP socket wrapper with chr(4) framing
└── errors.py            # VistAError exception hierarchy

tests/
├── unit/
│   ├── test_protocol.py # S-PACK, L-PACK, message building, cipher encrypt/decrypt
│   └── test_transport.py # Socket mock tests for send/receive framing
├── contract/
│   └── test_wire_format.py # Known-good byte sequences from reference implementation
└── smoke/
    └── test_lifecycle.py # Full connect→auth→RPC→disconnect against a reference VistA environment (VEHU)
```

**Structure Decision**: Single-project layout. The `src/vista_clients/rpc/` package contains the library. Tests are in a parallel `tests/` tree with three tiers: unit (no server), contract (no server, byte-level verification), and smoke (runs against a reference VistA environment (VEHU) Docker).

## Complexity Tracking

> No constitution violations — this section is empty.

## pytest-xdist Compatibility

The library architecture is compatible with `pytest-xdist` parallel test execution:

- **No shared mutable state**: Each `VistABroker` instance owns its own `Transport` (socket) and session state. No module-level globals or singletons.
- **Process isolation**: xdist spawns separate worker processes, each with independent memory. Multiple workers can connect to VEHU simultaneously on separate TCP connections.
- **No file locks**: The library does not write to disk or use file-based coordination.
- **Logging**: Python's `logging` module is process-safe; each worker gets its own logger hierarchy.
- **VEHU concurrency**: The VistA RPC Broker listener (`XWBTCPL`) accepts multiple concurrent connections via `JOB` (fork). Each connection gets its own M partition with an independent `$J` (job ID).

No special xdist fixtures or `worker_id`-based isolation are required for the library itself. Test suites that **modify** VistA state should use xdist groups or session-scoped fixtures to avoid data conflicts, but that is a test-suite concern, not a library concern.
