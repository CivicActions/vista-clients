"""Unit tests for protocol encoding primitives and cipher."""

import pytest

from vista_clients.rpc.errors import RPCError
from vista_clients.rpc.protocol import (
    CipherType,
    ParamType,
    RPCParameter,
    build_connect_message,
    build_disconnect_message,
    build_rpc_message,
    decrypt,
    encrypt,
    list_param,
    literal,
    lpack,
    parse_response,
    spack,
)

# ---------------------------------------------------------------------------
# spack tests
# ---------------------------------------------------------------------------


class TestSpack:
    def test_empty_string(self):
        assert spack("") == chr(0)

    def test_simple_string(self):
        result = spack("HELLO")
        assert result == chr(5) + "HELLO"

    def test_length_byte_is_character_length(self):
        s = "a" * 100
        result = spack(s)
        assert result[0] == chr(100)
        assert result[1:] == s

    def test_max_length_255(self):
        s = "x" * 255
        result = spack(s)
        assert result[0] == chr(255)
        assert len(result) == 256

    def test_exceeds_255_raises(self):
        with pytest.raises(ValueError, match="exceeds 255"):
            spack("x" * 256)

    def test_special_characters(self):
        result = spack("a;b")
        assert result == chr(3) + "a;b"


# ---------------------------------------------------------------------------
# lpack tests
# ---------------------------------------------------------------------------


class TestLpack:
    def test_empty_string(self):
        assert lpack("") == "000"

    def test_simple_string(self):
        assert lpack("HELLO") == "005HELLO"

    def test_three_digit_padding(self):
        s = "a" * 42
        result = lpack(s)
        assert result[:3] == "042"
        assert result[3:] == s

    def test_boundary_999(self):
        """Values of exactly 999 chars use 3-digit format."""
        s = "b" * 999
        result = lpack(s)
        assert result[:3] == "999"
        assert len(result) == 999 + 3

    def test_boundary_1000_switches_to_5_digit(self):
        """Values of 1000+ chars use 5-digit format per XWB*1.1*65."""
        s = "c" * 1000
        result = lpack(s)
        assert result[:5] == "01000"
        assert len(result) == 1000 + 5

    def test_large_value(self):
        s = "d" * 50000
        result = lpack(s)
        assert result[:5] == "50000"
        assert len(result) == 50000 + 5

    def test_single_character(self):
        assert lpack("X") == "001X"


# ---------------------------------------------------------------------------
# cipher tests
# ---------------------------------------------------------------------------


class TestCipher:
    """Test cipher encrypt/decrypt with both Traditional and OSEHRA tables."""

    @pytest.mark.parametrize("cipher", [CipherType.TRADITIONAL, CipherType.OSEHRA])
    def test_encrypt_decrypt_round_trip(self, cipher):
        plaintext = "SM1234;SM1234!!"
        encrypted = encrypt(plaintext, cipher)
        decrypted = decrypt(encrypted, cipher)
        assert decrypted == plaintext

    @pytest.mark.parametrize("cipher", [CipherType.TRADITIONAL, CipherType.OSEHRA])
    def test_encrypt_changes_value(self, cipher):
        plaintext = "HELLO WORLD"
        encrypted = encrypt(plaintext, cipher)
        # Encrypted should differ from plaintext (minus prefix/suffix)
        assert encrypted[1:-1] != plaintext

    @pytest.mark.parametrize("cipher", [CipherType.TRADITIONAL, CipherType.OSEHRA])
    def test_encrypt_has_row_indices(self, cipher):
        encrypted = encrypt("test", cipher)
        # First and last chars are row index characters
        ra = ord(encrypted[0]) - 32
        rb = ord(encrypted[-1]) - 32
        assert 0 <= ra <= 19
        assert 0 <= rb <= 19
        assert ra != rb

    def test_decrypt_empty_returns_empty(self):
        assert decrypt("") == ""
        assert decrypt("x") == ""

    @pytest.mark.parametrize("cipher", [CipherType.TRADITIONAL, CipherType.OSEHRA])
    def test_round_trip_special_chars(self, cipher):
        plaintext = "test!@#$%^&*()_+-=[]{}|;':\",./<>?"
        decrypted = decrypt(encrypt(plaintext, cipher), cipher)
        assert decrypted == plaintext

    @pytest.mark.parametrize("cipher", [CipherType.TRADITIONAL, CipherType.OSEHRA])
    def test_round_trip_access_verify(self, cipher):
        """Verify the exact credential format used by XUS AV CODE."""
        plaintext = "SM1234;SM1234!!"
        for _ in range(10):  # Multiple rounds since random
            assert decrypt(encrypt(plaintext, cipher), cipher) == plaintext

    def test_cross_table_mismatch(self):
        """Encrypting with one table and decrypting with the other should fail."""
        plaintext = "SM1234;SM1234!!"
        encrypted = encrypt(plaintext, CipherType.TRADITIONAL)
        decrypted = decrypt(encrypted, CipherType.OSEHRA)
        assert decrypted != plaintext

    def test_default_cipher_is_traditional(self):
        """Default encrypt/decrypt should use TRADITIONAL table."""
        plaintext = "SM1234;SM1234!!"
        encrypted = encrypt(plaintext)  # uses default
        decrypted = decrypt(encrypted, CipherType.TRADITIONAL)
        assert decrypted == plaintext


# ---------------------------------------------------------------------------
# T019: build_connect_message / build_disconnect_message
# ---------------------------------------------------------------------------


class TestBuildConnectMessage:
    """T019: Verify exact byte output of TCPConnect command."""

    def test_starts_with_prefix(self):
        msg = build_connect_message("localhost", "vista-clients")
        text = msg.decode("utf-8")
        assert text.startswith("[XWB]1130")

    def test_uses_command_token_4(self):
        msg = build_connect_message("localhost", "test-app")
        text = msg.decode("utf-8")
        # After prefix "[XWB]1130", next char is command token "4"
        assert text[9] == "4"

    def test_contains_tcpconnect_name(self):
        msg = build_connect_message("localhost", "test-app")
        text = msg.decode("utf-8")
        assert "TCPConnect" in text

    def test_contains_hostname(self):
        msg = build_connect_message("myhost.example.com", "test-app")
        text = msg.decode("utf-8")
        assert "myhost.example.com" in text

    def test_contains_app_name(self):
        msg = build_connect_message("localhost", "my-app-name")
        text = msg.decode("utf-8")
        assert "my-app-name" in text

    def test_ends_with_eot(self):
        msg = build_connect_message("localhost", "test-app")
        assert msg[-1:] == b"\x04"

    def test_returns_bytes(self):
        msg = build_connect_message("localhost", "test-app")
        assert isinstance(msg, bytes)


class TestBuildDisconnectMessage:
    """T019: Verify #BYE# disconnect message."""

    def test_contains_bye(self):
        msg = build_disconnect_message()
        text = msg.decode("utf-8")
        assert "#BYE#" in text

    def test_starts_with_prefix(self):
        msg = build_disconnect_message()
        text = msg.decode("utf-8")
        assert text.startswith("[XWB]1130")

    def test_ends_with_eot(self):
        msg = build_disconnect_message()
        assert msg[-1:] == b"\x04"


# ---------------------------------------------------------------------------
# T035: build_rpc_message
# ---------------------------------------------------------------------------


class TestBuildRpcMessage:
    """T035: RPC message building with various param types."""

    def test_no_params(self):
        msg = build_rpc_message("ORWU USERINFO")
        text = msg.decode("utf-8")
        assert "ORWU USERINFO" in text
        assert text.startswith("[XWB]1130")
        assert msg[-1:] == b"\x04"

    def test_no_params_has_empty_param_marker(self):
        msg = build_rpc_message("TEST RPC")
        text = msg.decode("utf-8")
        # "54f" = "5" (start params) + "4" (no params) + "f" (end)
        assert "54f" in text

    def test_literal_param(self):
        params = [RPCParameter(param_type=ParamType.LITERAL, value="DUZ")]
        msg = build_rpc_message("XWB GET VARIABLE VALUE", params)
        text = msg.decode("utf-8")
        assert "XWB GET VARIABLE VALUE" in text
        assert "DUZ" in text

    def test_literal_param_with_factory(self):
        msg = build_rpc_message("XWB GET VARIABLE VALUE", [literal("DUZ")])
        text = msg.decode("utf-8")
        assert "DUZ" in text

    def test_list_param(self):
        params = [list_param({"NAME": "DOE,JOHN", "SSN": "000123456"})]
        msg = build_rpc_message("MY RPC", params)
        text = msg.decode("utf-8")
        assert "MY RPC" in text
        assert "NAME" in text
        assert "DOE,JOHN" in text

    def test_mixed_literal_and_list(self):
        """Literal then list is valid (list must be last)."""
        params = [
            literal("value1"),
            list_param({"key": "val"}),
        ]
        msg = build_rpc_message("MY RPC", params)
        text = msg.decode("utf-8")
        assert "value1" in text
        assert "key" in text

    def test_uses_rpc_token_not_command_token(self):
        msg = build_rpc_message("TEST RPC")
        text = msg.decode("utf-8")
        # After prefix "[XWB]1130", RPC token is "2\x011" (not "4")
        assert text[9] == "2"

    def test_returns_bytes(self):
        msg = build_rpc_message("TEST RPC")
        assert isinstance(msg, bytes)


# ---------------------------------------------------------------------------
# T060: list param validation
# ---------------------------------------------------------------------------


class TestListParamValidation:
    """T060: List parameter must be the last parameter."""

    def test_list_not_last_raises(self):
        params = [
            list_param({"key": "val"}),
            literal("after_list"),
        ]
        with pytest.raises(ValueError, match="last parameter"):
            build_rpc_message("MY RPC", params)

    def test_list_last_is_ok(self):
        params = [
            literal("first"),
            list_param({"key": "val"}),
        ]
        # Should not raise
        msg = build_rpc_message("MY RPC", params)
        assert isinstance(msg, bytes)

    def test_single_list_is_ok(self):
        params = [list_param({"key": "val"})]
        msg = build_rpc_message("MY RPC", params)
        assert isinstance(msg, bytes)

    def test_empty_list_param_raises(self):
        with pytest.raises(ValueError, match="not be empty"):
            list_param({})


# ---------------------------------------------------------------------------
# T041: parse_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    """T041, T058: Response parsing unit tests."""

    def test_empty_response(self):
        resp = parse_response("")
        assert resp.value == ""
        assert resp.lines is None
        assert resp.raw == ""

    def test_single_value(self):
        resp = parse_response("42")
        assert resp.value == "42"
        assert resp.lines is None
        assert not resp.is_array

    def test_array_response(self):
        resp = parse_response("line1\r\nline2\r\nline3\r\n")
        assert resp.lines == ["line1", "line2", "line3"]
        assert resp.is_array

    def test_array_no_trailing_crlf(self):
        resp = parse_response("a\r\nb")
        assert resp.lines == ["a", "b"]

    def test_response_preserves_raw(self):
        raw_data = "1^PROGRAMMER,ONE^3"
        resp = parse_response(raw_data)
        assert resp.raw == raw_data

    # T058: Security error prefix
    def test_security_error_raises(self):
        """Non-printable first byte triggers error packet parsing."""
        error_msg = "Access denied"
        # Build: chr(len) + error + chr(0)
        raw = chr(len(error_msg)) + error_msg + chr(0)
        with pytest.raises(RPCError, match="Access denied"):
            parse_response(raw)

    def test_app_error_raises(self):
        """Application error in second packet."""
        app_msg = "App error occurred"
        # Build: chr(0) + chr(len) + error
        raw = chr(0) + chr(len(app_msg)) + app_msg
        with pytest.raises(RPCError, match="App error occurred"):
            parse_response(raw)

    def test_both_errors_security_takes_precedence(self):
        """If both security and app error, security raised first."""
        sec_msg = "Security!"
        app_msg = "App error"
        raw = chr(len(sec_msg)) + sec_msg + chr(len(app_msg)) + app_msg
        with pytest.raises(RPCError, match="Security!"):
            parse_response(raw)

    def test_m_error_in_data_raises(self):
        """M error returned as data (not via SNDERR) should raise RPCError."""
        raw = "M  ERROR=ECHOSTR+1^XWBEXMPL, Undefined local variable"
        with pytest.raises(RPCError, match="M  ERROR"):
            parse_response(raw)

    def test_nonexistent_rpc_error_raises(self):
        """Nonexistent RPC error in data raises RPCError."""
        raw = "ERemote Procedure 'FAKE RPC' doesn't exist on the server.\x00"
        with pytest.raises(RPCError, match="doesn't exist"):
            parse_response(raw)

    def test_normal_data_starting_with_number(self):
        """Normal RPC data starting with a digit is not an error."""
        resp = parse_response("1^PROGRAMMER,ONE^3^1^1")
        assert resp.value == "1^PROGRAMMER,ONE^3^1^1"

    def test_word_processing_multi_line(self):
        """Word-processing style response with multiple lines."""
        raw = "Line 1\r\nLine 2\r\nLine 3\r\n"
        resp = parse_response(raw)
        assert resp.lines == ["Line 1", "Line 2", "Line 3"]
        assert resp.is_array
