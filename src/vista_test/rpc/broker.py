"""VistABroker: high-level RPC Broker lifecycle orchestrator.

Provides connect, handshake, authenticate, context creation,
RPC invocation, keepalive, and disconnect operations with a
clean context-manager API.
"""

from __future__ import annotations

import logging
import os
import re

from vista_test.rpc.errors import (
    AuthenticationError,
    ConnectionError,
    ContextError,
    HandshakeError,
    StateError,
)
from vista_test.rpc.protocol import (
    DEFAULT_CIPHER,
    CipherType,
    CredentialSource,
    RPCParameter,
    RPCResponse,
    SessionState,
    build_connect_message,
    build_disconnect_message,
    build_rpc_message,
    encrypt,
    parse_response,
)
from vista_test.rpc.transport import Transport

logger = logging.getLogger(__name__)

# Pattern to redact access/verify codes in log messages
_REDACT_RE = re.compile(
    r"(access[_ ]?code|verify[_ ]?code|AV[_ ]?CODE|credentials?)"
    r"[=: ]+\S+",
    re.IGNORECASE,
)

# VEHU default credentials (PROGRAMMER,ONE)
_DEFAULT_ACCESS = "PRO1234"
_DEFAULT_VERIFY = "PRO1234!!"


def _redact(msg: str) -> str:
    """Replace credential values with ***REDACTED*** in log messages."""
    return _REDACT_RE.sub(r"\1=***REDACTED***", msg)


class VistABroker:
    """High-level VistA RPC Broker client.

    Args:
        host: IP address or hostname of the VistA server.
        port: TCP port of the RPC Broker listener.
        timeout: Connection and read timeout in seconds.
        app_name: Application name sent during TCPConnect handshake.
        cipher: Cipher table variant to use for encryption.
            Use ``CipherType.TRADITIONAL`` (default) for standard
            VA VistA / WorldVistA VEHU, or ``CipherType.OSEHRA``
            for OSEHRA-derived systems with modified cipher tables.

    Raises:
        ValueError: If port or timeout is out of valid range.
    """

    def __init__(
        self,
        host: str,
        port: int = 9430,
        *,
        timeout: float = 30.0,
        app_name: str = "vista-test",
        cipher: CipherType = DEFAULT_CIPHER,
    ) -> None:
        if not 1 <= port <= 65535:
            raise ValueError(f"port must be 1-65535, got {port}")
        if timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {timeout}")

        self._host = host
        self._port = port
        self._timeout = timeout
        self._app_name = app_name
        self._cipher = cipher
        self._transport: Transport | None = None
        self._state = SessionState.DISCONNECTED
        self._duz: str | None = None
        self._context: str | None = None

    # -- Properties ----------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Whether the broker has an active connection."""
        return self._transport is not None and self._transport.is_connected

    @property
    def duz(self) -> str | None:
        """DUZ of the authenticated user, or None if not authenticated."""
        return self._duz

    @property
    def state(self) -> SessionState:
        """Current session state."""
        return self._state

    # -- Lifecycle -----------------------------------------------------------

    def connect(self) -> None:
        """Establish TCP connection and perform XWB handshake.

        Executes the full sequence: TCP connect -> TCPConnect command ->
        server ack. After this call, the session is in HANDSHAKED state.

        Raises:
            ConnectionError: If TCP connection fails or times out.
            HandshakeError: If the server rejects the TCPConnect command.
            StateError: If already connected.
        """
        if self._state != SessionState.DISCONNECTED:
            raise StateError("Already connected")

        self._transport = Transport(self._host, self._port, self._timeout)
        try:
            self._transport.connect()
        except Exception as exc:
            self._transport = None
            raise ConnectionError(str(exc)) from exc

        self._state = SessionState.CONNECTED
        logger.debug("TCP connected to %s:%d", self._host, self._port)

        # XWB handshake: TCPConnect command
        import socket as _socket

        try:
            local_hostname = _socket.gethostbyname(_socket.gethostname())
        except Exception:
            local_hostname = "127.0.0.1"

        msg = build_connect_message(local_hostname, self._app_name)
        try:
            logger.debug("Handshake >> %d bytes", len(msg))
            self._transport.send(msg)
            reply = self._transport.receive()
            logger.debug("Handshake << %d bytes", len(reply))
        except Exception as exc:
            self.disconnect()
            raise HandshakeError(f"Handshake failed: {exc}") from exc

        if not reply.startswith("accept"):
            self.disconnect()
            raise HandshakeError(f"Server rejected handshake: {reply}")

        self._state = SessionState.HANDSHAKED
        logger.info("XWB handshake complete with %s:%d", self._host, self._port)

    def authenticate(
        self,
        access_code: str | None = None,
        verify_code: str | None = None,
    ) -> str:
        """Authenticate with VistA using Access/Verify codes.

        Credential resolution order:
        1. Explicit arguments (if both provided)
        2. Environment variables VISTA_ACCESS_CODE / VISTA_VERIFY_CODE
        3. Built-in VEHU defaults (PRO1234 / PRO1234!!)

        Args:
            access_code: VistA Access Code (optional).
            verify_code: VistA Verify Code (optional).

        Returns:
            The authenticated user's DUZ (str).

        Raises:
            AuthenticationError: If credentials are rejected.
            StateError: If not handshaked.
        """
        if self._state != SessionState.HANDSHAKED:
            raise StateError(
                f"Cannot authenticate in state {self._state.value}; must be HANDSHAKED"
            )

        ac, vc, source = self._resolve_credentials(access_code, verify_code)
        logger.debug("Credential source: %s", source.value)

        assert self._transport is not None

        # Step 1: XUS SIGNON SETUP
        msg = build_rpc_message("XUS SIGNON SETUP")
        logger.debug("Auth signon >> %d bytes", len(msg))
        self._transport.send(msg)
        self._transport.receive()  # response ignored

        # Step 2: XUS AV CODE
        av_encrypted = encrypt(ac + ";" + vc, self._cipher)
        msg = build_rpc_message(
            "XUS AV CODE",
            [
                RPCParameter(
                    param_type=__import__(
                        "vista_test.rpc.protocol", fromlist=["ParamType"]
                    ).ParamType.LITERAL,
                    value=av_encrypted,
                )
            ],
        )
        logger.debug("Auth AV CODE >> %d bytes", len(msg))
        self._transport.send(msg)
        reply = self._transport.receive()
        logger.debug("Auth AV CODE << %d bytes", len(reply))

        # Parse response: line 0 = DUZ, line 3 = error message
        lines = reply.split("\r\n")
        duz = lines[0].strip() if lines else "0"

        if duz == "0" or not duz:
            err_msg = lines[3].strip() if len(lines) > 3 else "Authentication failed"
            raise AuthenticationError(err_msg)

        self._duz = duz
        self._state = SessionState.AUTHENTICATED
        logger.info("Authenticated as DUZ=%s", self._duz)
        return self._duz

    def create_context(self, option_name: str) -> None:
        """Set the application context for RPC authorization.

        The option_name is automatically encrypted before transmission.

        Args:
            option_name: Name of the B-type option in VistA OPTION file.

        Raises:
            ContextError: If the context cannot be established.
            StateError: If not authenticated.
        """
        if self._state not in (
            SessionState.AUTHENTICATED,
            SessionState.CONTEXT_SET,
        ):
            raise StateError(
                f"Cannot set context in state {self._state.value}; "
                "must be AUTHENTICATED or CONTEXT_SET"
            )

        assert self._transport is not None

        from vista_test.rpc.protocol import ParamType

        encrypted_context = encrypt(option_name, self._cipher)
        msg = build_rpc_message(
            "XWB CREATE CONTEXT",
            [RPCParameter(param_type=ParamType.LITERAL, value=encrypted_context)],
        )
        logger.debug("Context >> %d bytes", len(msg))
        self._transport.send(msg)
        reply = self._transport.receive()
        logger.debug("Context << %d bytes", len(reply))

        if reply.strip() != "1":
            raise ContextError(f"Context '{option_name}' rejected: {reply.strip()}")

        self._context = option_name
        self._state = SessionState.CONTEXT_SET
        logger.info("Context set: %s", option_name)

    def call_rpc(
        self,
        rpc_name: str,
        params: list[RPCParameter] | None = None,
    ) -> RPCResponse:
        """Invoke a remote procedure call on the VistA server.

        Args:
            rpc_name: Name of the RPC to invoke.
            params: Ordered list of typed parameters (default: no parameters).

        Returns:
            RPCResponse containing the parsed server response.

        Raises:
            RPCError: If the server returns an error.
            ConnectionError: If the connection is broken mid-call.
            StateError: If context has not been set.
        """
        if self._state != SessionState.CONTEXT_SET:
            raise StateError(f"Cannot call RPC in state {self._state.value}; must be CONTEXT_SET")

        assert self._transport is not None

        msg = build_rpc_message(rpc_name, params)
        logger.debug("RPC request: %s (params=%s)", rpc_name, bool(params))

        try:
            logger.debug("RPC >> %d bytes", len(msg))
            self._transport.send(msg)
            raw = self._transport.receive()
            logger.debug("RPC << %d bytes", len(raw))
        except Exception as exc:
            raise ConnectionError(f"Connection broken during RPC '{rpc_name}': {exc}") from exc

        logger.debug("RPC response length: %d", len(raw))
        return parse_response(raw)

    def ping(self) -> None:
        """Send XWB IM HERE keepalive to reset server timeout.

        Raises:
            ConnectionError: If the connection is broken.
            StateError: If not connected.
        """
        if self._state == SessionState.DISCONNECTED:
            raise StateError("Not connected")

        assert self._transport is not None

        msg = build_rpc_message("XWB IM HERE")
        try:
            self._transport.send(msg)
            self._transport.receive()
        except Exception as exc:
            raise ConnectionError(f"Ping failed: {exc}") from exc

    def disconnect(self) -> None:
        """Send disconnect command and close the TCP connection.

        Safe to call multiple times. No-op if already disconnected.
        """
        if self._state == SessionState.DISCONNECTED:
            return

        if self._transport is not None and self._transport.is_connected:
            try:
                msg = build_disconnect_message()
                self._transport.send(msg)
            except Exception:
                pass  # Best-effort disconnect
            try:
                self._transport.close()
            except Exception:
                pass

        self._transport = None
        self._state = SessionState.DISCONNECTED
        self._duz = None
        self._context = None
        logger.info("Disconnected from %s:%d", self._host, self._port)

    # -- Context manager -----------------------------------------------------

    def __enter__(self) -> VistABroker:
        """Enter context manager. Calls connect() if not already connected."""
        if self._state == SessionState.DISCONNECTED:
            self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        """Exit context manager. Calls disconnect()."""
        self.disconnect()

    # -- Private helpers -----------------------------------------------------

    def _resolve_credentials(
        self,
        access_code: str | None,
        verify_code: str | None,
    ) -> tuple[str, str, CredentialSource]:
        """Resolve credentials from explicit, env, or defaults."""
        if access_code and verify_code:
            return access_code, verify_code, CredentialSource.EXPLICIT

        env_ac = os.environ.get("VISTA_ACCESS_CODE")
        env_vc = os.environ.get("VISTA_VERIFY_CODE")
        if env_ac and env_vc:
            return env_ac, env_vc, CredentialSource.ENVIRONMENT

        return _DEFAULT_ACCESS, _DEFAULT_VERIFY, CredentialSource.DEFAULT
