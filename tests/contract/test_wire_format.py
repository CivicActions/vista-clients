"""Contract tests: verify wire format against known-good byte sequences.

T020: Known-good byte sequences from the XWB protocol reference.
These tests verify that our message builders produce bytes compatible
with the VistA RPC Broker server.
"""

from vista_clients.rpc.protocol import (
    build_connect_message,
    build_disconnect_message,
    build_rpc_message,
    list_param,
    literal,
)


class TestTCPConnectWireFormat:
    """Verify TCPConnect command byte structure."""

    def test_prefix_format(self):
        """Message must start with [XWB]1130."""
        msg = build_connect_message("127.0.0.1", "test-app")
        text = msg.decode("utf-8")
        assert text[:9] == "[XWB]1130"

    def test_command_token(self):
        """TCPConnect uses command token 4, not RPC token 2."""
        msg = build_connect_message("127.0.0.1", "test-app")
        text = msg.decode("utf-8")
        assert text[9] == "4"

    def test_spack_name(self):
        """RPC name 'TCPConnect' is S-PACKed: chr(10) + 'TCPConnect'."""
        msg = build_connect_message("127.0.0.1", "test-app")
        text = msg.decode("utf-8")
        idx = text.index(chr(10) + "TCPConnect")
        assert idx > 0

    def test_parameter_structure(self):
        """Parameters use '5' prefix, '0' literal type, lpack, 'f' terminator."""
        msg = build_connect_message("127.0.0.1", "test-app")
        text = msg.decode("utf-8")
        # Find param section starting with '5' after TCPConnect
        connect_idx = text.index("TCPConnect")
        param_start = text.index("5", connect_idx + 10)
        param_section = text[param_start:]
        # Must contain hostname in lpack format
        assert "127.0.0.1" in param_section
        # Must contain "f" terminators
        assert "f" in param_section

    def test_eot_terminator(self):
        """Message must end with chr(4) (EOT)."""
        msg = build_connect_message("127.0.0.1", "test-app")
        assert msg[-1] == 4  # chr(4)

    def test_hostname_lpack_encoding(self):
        """Hostname is L-PACKed with 3-digit length."""
        msg = build_connect_message("192.168.1.1", "app")
        text = msg.decode("utf-8")
        # "192.168.1.1" has length 11 → "011192.168.1.1"
        assert "011192.168.1.1" in text

    def test_appname_lpack_encoding(self):
        """App name is L-PACKed."""
        msg = build_connect_message("host", "my-fancy-app")
        text = msg.decode("utf-8")
        # "my-fancy-app" has length 12 → "012my-fancy-app"
        assert "012my-fancy-app" in text


class TestDisconnectWireFormat:
    """Verify #BYE# disconnect message structure."""

    def test_contains_bye_spack(self):
        """#BYE# is S-PACKed: chr(5) + '#BYE#'."""
        msg = build_disconnect_message()
        text = msg.decode("utf-8")
        assert chr(5) + "#BYE#" in text

    def test_uses_rpc_token(self):
        """Disconnect uses RPC token 2, not command token 4."""
        msg = build_disconnect_message()
        text = msg.decode("utf-8")
        assert text[9] == "2"

    def test_no_params(self):
        """Disconnect has empty parameter marker '54f'."""
        msg = build_disconnect_message()
        text = msg.decode("utf-8")
        assert "54f" in text


class TestRPCInvocationWireFormat:
    """Verify RPC message wire format details."""

    def test_rpc_token_format(self):
        """RPC token is '2' + chr(1) + '1'."""
        msg = build_rpc_message("TEST RPC")
        text = msg.decode("utf-8")
        token = text[9:12]
        assert token == "2" + chr(1) + "1"

    def test_literal_param_encoding(self):
        """Literal typed as '0' + lpack(value) + 'f'."""
        msg = build_rpc_message("TEST RPC", [literal("DUZ")])
        text = msg.decode("utf-8")
        # "0" (literal type) + "003" (lpack len) + "DUZ" + "f"
        assert "0003DUZf" in text

    def test_list_param_encoding(self):
        """List typed as '2' + lpack(key)lpack(value)... + 'f'."""
        msg = build_rpc_message("TEST", [list_param({"A": "B"})])
        text = msg.decode("utf-8")
        # "2" (list type) + "001A" + "001B" + "f"
        assert "2001A001Bf" in text

    def test_multiple_list_entries_use_t_separator(self):
        """Multiple entries in list use 't' separator."""
        msg = build_rpc_message("TEST", [list_param({"K1": "V1", "K2": "V2"})])
        text = msg.decode("utf-8")
        # First entry no 't', subsequent entries prefixed with 't'
        assert "t" in text

    def test_param_section_starts_with_5(self):
        """Parameter section always starts with '5'."""
        msg = build_rpc_message("MY RPC", [literal("val")])
        text = msg.decode("utf-8")
        # After the S-PACKed name, params section starts with '5'
        name_end = text.index("MY RPC") + len("MY RPC")
        assert text[name_end] == "5"

    def test_full_message_encoding(self):
        """Verify complete message can be decoded as UTF-8."""
        msg = build_rpc_message(
            "XWB GET VARIABLE VALUE",
            [literal("$P($G(^DIC(3.1,1,0)),U,1)")],
        )
        text = msg.decode("utf-8")
        assert "[XWB]1130" in text
        assert "XWB GET VARIABLE VALUE" in text
        assert "$P($G(^DIC(3.1,1,0)),U,1)" in text
