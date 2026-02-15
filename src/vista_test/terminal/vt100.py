"""VT100/ANSI escape sequence stripping utilities.

Provides ``strip_escape_sequences`` for cleaning raw terminal output
into human-readable plain text.
"""

from __future__ import annotations

import re

# Matches VT100/ANSI escape sequences including:
#   - Cursor positioning  (\x1b[H, \x1b[<n>;<m>H)
#   - Colour codes        (\x1b[31m, \x1b[0m)
#   - Device attributes   (\x1b[?1;2c)
#   - Erase display       (\x1b[J, \x1b[2J)
#   - Cursor visibility   (\x1b[?25l, \x1b[?25h)
#   - Cursor save/restore (\x1b[s, \x1b[u)
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[\??[0-9;]*[a-zA-Z]")


def strip_escape_sequences(text: str) -> str:
    """Remove VT100/ANSI escape sequences from text.

    Strips cursor positioning, color codes, device attribute
    responses, and other control sequences, returning clean
    human-readable plain text.  Carriage returns (``\\r``) are
    also removed since paramiko pty channels deliver ``\\r\\n``
    line endings.

    Args:
        text: Raw terminal output containing escape sequences.

    Returns:
        Cleaned text with all escape sequences and carriage
        returns removed.
    """
    # Strip \r first (pty line endings), then ANSI sequences
    return _ANSI_ESCAPE_RE.sub("", text.replace("\r", ""))
