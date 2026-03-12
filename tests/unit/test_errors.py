"""T049: Verify all exception types are independently catchable (SC-004).

Each exception in the hierarchy should be catchable by its specific
type AND by its parent type (VistAError).
"""

import pytest

from vista_clients.rpc.errors import (
    AuthenticationError,
    BrokerConnectionError,
    ContextError,
    HandshakeError,
    RPCError,
    StateError,
    VistAError,
)


class TestExceptionHierarchy:
    """All exception types are independently catchable."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            BrokerConnectionError,
            HandshakeError,
            AuthenticationError,
            ContextError,
            RPCError,
            StateError,
        ],
    )
    def test_catchable_by_specific_type(self, exc_class):
        """Each error can be caught by its own type."""
        with pytest.raises(exc_class):
            raise exc_class("test error")

    @pytest.mark.parametrize(
        "exc_class",
        [
            BrokerConnectionError,
            HandshakeError,
            AuthenticationError,
            ContextError,
            RPCError,
            StateError,
        ],
    )
    def test_catchable_by_base_type(self, exc_class):
        """Each error can be caught by VistAError."""
        with pytest.raises(VistAError):
            raise exc_class("test error")

    def test_all_are_exceptions(self):
        """All error types are subclasses of Exception."""
        for exc_class in (
            VistAError,
            BrokerConnectionError,
            HandshakeError,
            AuthenticationError,
            ContextError,
            RPCError,
            StateError,
        ):
            assert issubclass(exc_class, Exception)

    def test_distinct_types(self):
        """Each exception type is distinct (not aliases)."""
        types = {
            BrokerConnectionError,
            HandshakeError,
            AuthenticationError,
            ContextError,
            RPCError,
            StateError,
        }
        assert len(types) == 6

    def test_message_preserved(self):
        """Error message is accessible via str()."""
        for exc_class in (
            BrokerConnectionError,
            HandshakeError,
            AuthenticationError,
            ContextError,
            RPCError,
            StateError,
        ):
            err = exc_class("detailed message")
            assert "detailed message" in str(err)

    def test_connection_does_not_catch_auth(self):
        """Specific types don't accidentally catch unrelated errors."""
        with pytest.raises(AuthenticationError):
            try:
                raise AuthenticationError("auth fail")
            except BrokerConnectionError:
                pytest.fail("BrokerConnectionError should not catch AuthenticationError")
