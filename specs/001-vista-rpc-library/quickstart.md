# Quickstart: VistA RPC Broker Library

**Feature**: 001-vista-rpc-library  
**Date**: 2026-02-14

---

## Prerequisites

1. **Python 3.10+** installed
2. **Docker** running with `worldvista/vehu` image:
   ```bash
   docker pull worldvista/vehu
   docker run -d --name vehu -p 9430:9430 -p 2222:22 worldvista/vehu
   ```
   Wait ~60 seconds for the VistA Broker listener to start.

3. **Install the package**:
   ```bash
   cd /path/to/vista-test
   uv sync
   ```

---

## Basic Usage

### Connect, Authenticate, and Call an RPC

```python
from vista_test.rpc import VistABroker

# Context manager handles connect and disconnect automatically
with VistABroker("localhost", 9430) as broker:
    # Authenticate (uses VEHU defaults: SM1234 / SM1234!!)
    duz = broker.authenticate()
    print(f"Logged in as DUZ: {duz}")

    # Set application context
    broker.create_context("OR CPRS GUI CHART")

    # Call an RPC with no parameters
    response = broker.call_rpc("ORWU USERINFO")
    print(response.value)
```

### Call an RPC with Parameters

```python
from vista_test.rpc import VistABroker, literal, list_param

with VistABroker("localhost", 9430) as broker:
    broker.authenticate()
    broker.create_context("OR CPRS GUI CHART")

    # Literal (string) parameter
    response = broker.call_rpc("XWB GET VARIABLE VALUE", [literal("DUZ")])
    print(f"DUZ = {response.value}")

    # Numeric values are passed as their string representation
    response = broker.call_rpc("SOME RPC", [literal("42")])

    # List (key-value) parameter
    response = broker.call_rpc("MY RPC", [
        literal("some_value"),
        list_param({"NAME": "DOE,JOHN", "SSN": "000123456"}),
    ])
    print(response.lines)
```

### Custom Credentials

```python
# Via constructor arguments
with VistABroker("my-vista-server", 9430) as broker:
    broker.authenticate(access_code="MYACCESS", verify_code="MYVERIFY1!")

# Via environment variables
# export VISTA_ACCESS_CODE=MYACCESS
# export VISTA_VERIFY_CODE=MYVERIFY1!
with VistABroker("my-vista-server", 9430) as broker:
    broker.authenticate()  # picks up env vars automatically
```

### Error Handling

```python
from vista_test.rpc import VistABroker
from vista_test.rpc.errors import (
    ConnectionError,
    AuthenticationError,
    ContextError,
    RPCError,
)

try:
    with VistABroker("localhost", 9430) as broker:
        broker.authenticate()
        broker.create_context("OR CPRS GUI CHART")
        response = broker.call_rpc("SOME RPC")
except ConnectionError as e:
    print(f"Cannot reach server: {e}")
except AuthenticationError as e:
    print(f"Bad credentials: {e}")
except ContextError as e:
    print(f"Context not available: {e}")
except RPCError as e:
    print(f"RPC failed: {e}")
```

### Keepalive

```python
import time

with VistABroker("localhost", 9430) as broker:
    broker.authenticate()
    broker.create_context("OR CPRS GUI CHART")

    # Long-running operation — send keepalive to prevent server timeout
    for batch in work_batches:
        process(batch)
        broker.ping()  # resets server's 3-minute activity timeout
```

---

## Running Tests

```bash
# Unit tests (no server needed)
uv run pytest tests/unit/

# Smoke tests (requires VEHU running on localhost:9430)
uv run pytest tests/smoke/
```

---

## Project Layout

```
src/vista_test/rpc/
├── __init__.py      # Public re-exports
├── broker.py        # VistABroker high-level API
├── protocol.py      # XWB message construction, parsing, cipher
├── transport.py     # TCP socket wrapper with framing
└── errors.py        # Exception hierarchy

tests/
├── unit/            # Protocol encoding, cipher, message format
├── contract/        # Known-good byte sequence verification
└── smoke/           # Full lifecycle against VEHU
```
