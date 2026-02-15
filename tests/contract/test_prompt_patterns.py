"""Contract tests for default prompt patterns.

Each test verifies that a default prompt regex matches known VEHU output
samples captured from research.md.
"""

from __future__ import annotations

from vista_test.terminal.session import DEFAULT_PROMPT_PATTERNS, PromptPattern


def _find_pattern(name: str) -> PromptPattern:
    """Look up a prompt pattern by name."""
    for pp in DEFAULT_PROMPT_PATTERNS:
        if pp.name == name:
            return pp
    raise ValueError(f"No pattern named {name!r}")


class TestNavigationPatterns:
    """Verify navigation prompt patterns match VEHU output."""

    def test_select_option_systems_manager(self) -> None:
        pp = _find_pattern("select_option")
        assert pp.pattern.search("Select Systems Manager Menu Option: ")

    def test_select_option_user_management(self) -> None:
        pp = _find_pattern("select_option")
        assert pp.pattern.search("Select User Management Option: ")

    def test_select_name_generic(self) -> None:
        pp = _find_pattern("select_name")
        assert pp.pattern.search("Select PATIENT NAME: ")

    def test_select_name_trailing_space(self) -> None:
        pp = _find_pattern("select_name")
        assert pp.pattern.search("Select TERMINAL TYPE NAME: ")

    def test_device_prompt(self) -> None:
        pp = _find_pattern("device")
        assert pp.pattern.search("DEVICE: ")

    def test_default_value_prompt(self) -> None:
        pp = _find_pattern("default_value")
        assert pp.pattern.search("HOME// ")


class TestLoginPatterns:
    """Verify login prompt patterns match VEHU output."""

    def test_access_code(self) -> None:
        pp = _find_pattern("access_code")
        assert pp.pattern.search("ACCESS CODE: ")

    def test_verify_code(self) -> None:
        pp = _find_pattern("verify_code")
        assert pp.pattern.search("VERIFY CODE: ")

    def test_terminal_type(self) -> None:
        pp = _find_pattern("terminal_type")
        assert pp.pattern.search("Select TERMINAL TYPE NAME: ")


class TestPaginationPatterns:
    """Verify pagination prompt patterns match VEHU output."""

    def test_press_return(self) -> None:
        pp = _find_pattern("press_return")
        assert pp.pattern.search("Press <RETURN> to continue")

    def test_press_return_lowercase(self) -> None:
        pp = _find_pattern("press_return")
        assert pp.pattern.search("press RETURN to continue")

    def test_caret_stop(self) -> None:
        pp = _find_pattern("caret_stop")
        assert pp.pattern.search("'^' TO STOP")

    def test_end_of_report(self) -> None:
        pp = _find_pattern("end_of_report")
        assert pp.pattern.search("END OF REPORT")

    def test_type_enter(self) -> None:
        pp = _find_pattern("type_enter")
        assert pp.pattern.search("Type <Enter> to continue")


class TestPatternOrdering:
    """Verify pattern ordering prevents false matches."""

    def test_terminal_type_before_select_name(self) -> None:
        """select_option or terminal_type must match before select_name
        for 'Select TERMINAL TYPE NAME:' input."""
        text = "Select TERMINAL TYPE NAME: "
        terminal = _find_pattern("terminal_type")
        select_name = _find_pattern("select_name")

        # terminal_type should match
        assert terminal.pattern.search(text)
        # select_name would also match (it's more general)
        assert select_name.pattern.search(text)
        # In DEFAULT_PROMPT_PATTERNS, terminal_type comes before select_name
        terminal_idx = next(
            i for i, p in enumerate(DEFAULT_PROMPT_PATTERNS) if p.name == "terminal_type"
        )
        select_name_idx = next(
            i for i, p in enumerate(DEFAULT_PROMPT_PATTERNS) if p.name == "select_name"
        )
        assert terminal_idx < select_name_idx

    def test_select_option_before_select_name(self) -> None:
        """select_option must be checked before select_name."""
        option_idx = next(
            i for i, p in enumerate(DEFAULT_PROMPT_PATTERNS) if p.name == "select_option"
        )
        name_idx = next(i for i, p in enumerate(DEFAULT_PROMPT_PATTERNS) if p.name == "select_name")
        assert option_idx < name_idx
