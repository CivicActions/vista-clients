# Quickstart: VistA Terminal Library

**Feature**: 002-vista-terminal-library  
**Date**: 2026-02-15

---

## Prerequisites

1. **Python 3.10+** installed
2. **Docker** running with `worldvista/vehu` image:
   ```bash
   docker pull worldvista/vehu
   docker run -d --name vehu -p 9430:9430 -p 2222:22 worldvista/vehu
   ```
   Wait ~60 seconds for VistA to finish loading.

3. **Install the package**:
   ```bash
   cd /path/to/vista-test
   uv sync
   ```

---

## Basic Usage

### Connect, Login, Send a Command

```python
from vista_test.terminal import VistATerminal

# Context manager handles connect, login, and disconnect
with VistATerminal("localhost", 2222) as term:
    # login() uses VEHU defaults: PRO1234 / PRO1234!!
    term.login()

    # Send a menu option and read the response
    output = term.send_and_wait("User Management")
    print(output)
```

### Explicit Connection Steps

```python
from vista_test.terminal import VistATerminal

term = VistATerminal("localhost", 2222)

# Step 1: SSH connect and arrive at VistA ACCESS CODE prompt
banner = term.connect()  # Uses SSH defaults: vehutied / tied
print(banner)

# Step 2: Authenticate with VistA
greeting = term.login(access_code="PRO1234", verify_code="PRO1234!!")
print(greeting)

# Step 3: Interact
output = term.send_and_wait("Systems Manager Menu")
print(output)

# Step 4: Quit and disconnect
term.send_and_wait("Q")
term.disconnect()
```

### Custom Credentials

```python
# Via constructor arguments
term = VistATerminal("my-vista-server", 2222)
term.connect(ssh_user="myuser", ssh_password="mypass")
term.login(access_code="MYACC", verify_code="MYVER1!")

# Via environment variables
# export VISTA_SSH_USER=myuser
# export VISTA_SSH_PASSWORD=mypass
# export VISTA_ACCESS_CODE=MYACC
# export VISTA_VERIFY_CODE=MYVER1!
with VistATerminal("my-vista-server", 2222) as term:
    term.login()  # picks up all env vars automatically
```

---

## Auto-Scroll (Pagination Handling)

VistA paginates long output with prompts like `Press RETURN to continue`
or `'^' to stop`. Auto-scroll advances through these automatically.

```python
with VistATerminal("localhost", 2222) as term:
    term.login()

    # Enable auto-scroll for the session
    term.auto_scroll = True
    term.max_pages = 50  # safety limit (default: 100)

    # All paginated output is captured in one call
    output = term.send_and_wait("Long Report Option")
    print(output)

    # Or enable auto-scroll for a single command only
    term.auto_scroll = False
    output = term.send_and_wait("Another Report", auto_scroll=True, max_pages=10)
```

---

## Output Inspection

```python
with VistATerminal("localhost", 2222) as term:
    term.login()

    output = term.send_and_wait("ORWU PARAM")

    # Check for text in the last command's cleaned output
    if term.contains("PROVIDER"):
        print("Found PROVIDER in output")

    # Regex search
    match = term.search(r"DUZ=(\d+)")
    if match:
        print(f"Logged in as DUZ: {match.group(1)}")

    # Access the full session history
    for record in term.session_history:
        print(f"[{record.timestamp:.0f}] {record.command}")
        print(f"  → {record.output[:80]}...")
```

---

## Waiting for Custom Prompts

```python
import re

with VistATerminal("localhost", 2222) as term:
    term.login()

    # Send a command that produces a non-standard prompt
    term.send("Special Menu Option\r")

    # Wait for a specific pattern
    match, text = term.wait_for(r"Enter your choice:")
    print(f"Received prompt, text before it: {text}")

    # Respond to the custom prompt
    output = term.send_and_wait("1")
```

---

## Error Handling

```python
from vista_test.terminal import VistATerminal
from vista_test.terminal.errors import (
    ConnectionError,
    AuthenticationError,
    PromptTimeoutError,
    LoginPromptError,
    StateError,
)

try:
    with VistATerminal("localhost", 2222) as term:
        term.login()
        output = term.send_and_wait("Some Menu Option")
except ConnectionError as e:
    print(f"Cannot reach server: {e}")
except AuthenticationError as e:
    print(f"Bad credentials ({e.level} level): {e}")
except LoginPromptError as e:
    print(f"Unexpected login prompt: {e.prompt_text}")
except PromptTimeoutError as e:
    print(f"Prompt never appeared. Got: {e.partial_output[:200]}")
```

---

## Running Tests

```bash
# Unit tests (no server needed)
uv run pytest tests/unit/

# Contract tests (verify wire format expectations)
uv run pytest tests/contract/

# Smoke tests (requires VEHU running on localhost:2222)
uv run pytest tests/smoke/
```

---

## Project Layout

```
src/vista_test/terminal/
├── __init__.py      # Public re-exports
├── session.py       # VistATerminal high-level API
├── expect.py        # ExpectChannel prompt matching engine
├── transport.py     # Paramiko SSH wrapper
├── vt100.py         # VT100/ANSI escape stripping
└── errors.py        # Exception hierarchy

tests/
├── unit/            # Expect engine, VT100 stripping, state machine
├── contract/        # Known-good prompt pattern matching
└── smoke/           # Full lifecycle against VEHU
```
