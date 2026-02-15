<!--
  Sync Impact Report
  ==================
  Version change: 0.0.0 (template) → 1.0.0
  Modified principles: N/A (initial ratification)
  Added sections:
    - Core Principles (5 principles defined)
    - Operational Standards (tooling table)
    - Development Workflow (coding standards enforcement)
    - Governance (amendment procedure)
  Removed sections: None
  Templates requiring updates:
    - .specify/templates/plan-template.md ✅ no changes needed
      (Constitution Check section is a per-feature placeholder)
    - .specify/templates/spec-template.md ✅ no changes needed
      (technology-agnostic by design, aligns with Principle V)
    - .specify/templates/tasks-template.md ✅ no changes needed
      (phase structure compatible with library/test separation)
    - .specify/templates/commands/ ✅ no command files present
  Follow-up TODOs: None
-->

# VistA Test Constitution

## Core Principles

### I. Pure Python Portability (The "No-DLL" Mandate)

- All software deliverables MUST be written in pure Python
  (version 3.10 or higher).
- The use of Foreign Function Interfaces (FFI) to wrap
  Windows-specific binaries (such as `TRPCBroker.dll` or COM
  objects) is strictly prohibited.
- Developers MUST implement the **XWB** protocol and
  **Telnet/SSH** handling using Python standard libraries
  (e.g., `socket`) or pure-Python dependencies (e.g.,
  `pexpect`).
- The suite MUST run identically on macOS, Linux, and Windows.

**Rationale**: VistA's legacy reliance on Windows-based client
software (CPRS) has historically hindered automated testing in
Linux-based cloud environments. To enable true CI/CD, the test
suite MUST be capable of running inside standard Linux containers
(e.g., Debian, Alpine). This requires reimplementing the VistA
RPC wire protocol in native Python rather than relying on the
vendor-supplied Delphi DLLs.

### II. Container-First Standardization

- The **WorldVistA VEHU** Docker image (`worldvista/vehu`) is
  the authoritative reference environment for all development
  and testing.
- "Works on my machine" is NOT a valid success criterion; code
  MUST work against this specific container image.
- All default configuration values (e.g., RPC Port `9430`,
  SSH Port `2222`) MUST align with the exposed ports of the
  VEHU image.

**Rationale**: VistA environments are notoriously divergent,
with varying local patches, port configurations, and package
versions. The WorldVistA VEHU image provides a stable, known
configuration (YottaDB, standard port mappings) that serves as
a "Gold Standard" for baseline functionality. This
standardization eliminates environmental variables that plague
VistA testing.

### III. Separation of Concerns: Library vs. Test

- There MUST be a strict architectural boundary between the
  *interaction libraries* and the *test logic*.
- **Interaction Libraries**: Responsible for mechanics—
  connecting, sending data, parsing responses, and handling
  protocol errors. They MUST NOT contain test assertions
  (e.g., `assert patient_name == 'Smith'`).
- **Test Suite**: Responsible for business logic verification
  using the libraries.

**Rationale**: Mixing test assertions into the communication
library reduces reusability. The RPC library MUST be usable for
data migration or system administration tasks, not just testing.
This principle enforces a layered architecture where the "SDK"
layer is distinct from the "QA" layer.

### IV. Idempotency and State Management

- All operations interacting with the VistA database (MUMPS
  globals) MUST strive for idempotency.
- Where state modification is unavoidable (e.g., creating a new
  patient), mechanisms for data cleanup or isolation MUST be
  defined.
- The architecture MUST account for the cleanup phase or the
  use of ephemeral Docker containers that are reset after each
  run.

**Rationale**: VistA is a stateful system. A test suite that
pollutes the database with thousands of test patients will
eventually degrade system performance and cause test flakiness.

### V. Technology Agnosticism in Specifications

- Specifications MUST describe *intent* and *observable
  behavior*, not implementation details.
- A Spec defines *what* happens (e.g., "Authenticate user");
  the Plan defines *how* (e.g., "Send XWB Connect packet").

**Rationale**: This allows the underlying technology to change
(e.g., swapping `telnetlib` for `pexpect`) without invalidating
the high-level requirements. It also forces clear thinking about
the business value of the test before writing code.

## Operational Standards

The following table defines the pre-approved tools and formats
that govern all project work.

| Component | Standard | Rationale |
| --- | --- | --- |
| **Primary Language** | Python 3.10+ | Modern typing and async support. |
| **Package/Environment** | UV | Universal and fast package management. |
| **Reference Image** | `worldvista/vehu` (Docker Hub) | Consistent YottaDB/MUMPS testing surface. |
| **RPC Protocol** | Native Socket Implementation | Bypasses `TRPCBroker.dll` for Linux compatibility. |
| **Terminal Protocol** | `pexpect` (over `telnetlib`) | Handles pty interactions for VistA menu systems. |
| **Testing Framework** | `pytest` | Industry standard; supports fixtures for VistA setup/teardown. |
| **Docstrings** | Google Style | Readability and auto-documentation capability. |
| **Linting/Formatting** | `ruff` | Unified linter and formatter replacing black, isort, pylint. |
| **Typing** | Pyright | Balanced linter with IDE integration. |

## Development Workflow

- All Python code MUST be formatted with `ruff format` and pass
  `ruff check` before commit.
- All Python code MUST pass `pyright` type checking in basic
  mode at minimum.
- All public APIs MUST include Google-style docstrings.
- All tests MUST use `pytest` and its fixture system for VistA
  environment setup and teardown.
- Dependencies MUST be managed via `uv` and declared in
  `pyproject.toml`.

## Governance

- This Constitution supersedes all other development practices
  and conventions for the VistA Test project.
- All pull requests and code reviews MUST verify compliance
  with the principles defined herein.
- Amendments to this Constitution require:
  1. A written proposal describing the change and its rationale.
  2. Documentation of the impact on existing code and templates.
  3. A migration plan for any breaking changes.
- The Constitution follows semantic versioning:
  - **MAJOR**: Backward-incompatible principle removals or
    redefinitions.
  - **MINOR**: New principle or section added, or materially
    expanded guidance.
  - **PATCH**: Clarifications, wording, or non-semantic
    refinements.
- Compliance review MUST occur during each plan's Constitution
  Check gate (see plan template).

**Version**: 1.0.0 | **Ratified**: 2026-02-14 | **Last Amended**: 2026-02-14
