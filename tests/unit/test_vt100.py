"""Unit tests for VT100/ANSI escape sequence stripping."""

from __future__ import annotations

from vista_clients.terminal.vt100 import strip_escape_sequences


class TestStripEscapeSequences:
    """Tests for ``strip_escape_sequences``."""

    def test_plain_text_passthrough(self) -> None:
        assert strip_escape_sequences("Hello World") == "Hello World"

    def test_empty_string(self) -> None:
        assert strip_escape_sequences("") == ""

    def test_cursor_positioning(self) -> None:
        # \x1b[H = cursor home, \x1b[5;10H = row 5 col 10
        raw = "\x1b[HHello\x1b[5;10H World"
        assert strip_escape_sequences(raw) == "Hello World"

    def test_colour_codes(self) -> None:
        raw = "\x1b[31mRed\x1b[0m Normal"
        assert strip_escape_sequences(raw) == "Red Normal"

    def test_device_attributes(self) -> None:
        # VistA emits \x1b[?1;2c after terminal type selection
        raw = "output\x1b[?1;2c more"
        assert strip_escape_sequences(raw) == "output more"

    def test_erase_display(self) -> None:
        raw = "\x1b[2Jclean screen"
        assert strip_escape_sequences(raw) == "clean screen"

    def test_cursor_visibility(self) -> None:
        raw = "\x1b[?25lhidden\x1b[?25h"
        assert strip_escape_sequences(raw) == "hidden"

    def test_carriage_return_removal(self) -> None:
        raw = "line1\r\nline2\r\n"
        assert strip_escape_sequences(raw) == "line1\nline2\n"

    def test_carriage_return_and_ansi_combined(self) -> None:
        raw = "\x1b[31mRed\r\nText\x1b[0m\r\n"
        assert strip_escape_sequences(raw) == "Red\nText\n"

    def test_nested_sequences(self) -> None:
        # Multiple sequences back-to-back
        raw = "\x1b[1m\x1b[31mBold Red\x1b[0m"
        assert strip_escape_sequences(raw) == "Bold Red"

    def test_cursor_save_restore(self) -> None:
        raw = "\x1b[sHello\x1b[u"
        assert strip_escape_sequences(raw) == "Hello"

    def test_preserves_newlines(self) -> None:
        raw = "line1\nline2\n"
        assert strip_escape_sequences(raw) == "line1\nline2\n"

    def test_mixed_real_world_output(self) -> None:
        """Simulate VistA output with escape sequences mixed in."""
        raw = (
            "\x1b[H\x1b[J"  # clear screen
            "VEHU or CPRS DEMO INSTANCE\r\n"
            "\x1b[?1;2c"  # device attributes
            "Select Systems Manager Menu Option: \r\n"
        )
        expected = "VEHU or CPRS DEMO INSTANCE\nSelect Systems Manager Menu Option: \n"
        assert strip_escape_sequences(raw) == expected
