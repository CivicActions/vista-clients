"""T050: Verify pure-Python constraint (FR-011, FR-012).

Audit all imports in the vista_test.rpc package to confirm no
native extensions or platform-specific dependencies are used.
Only Python standard library modules are allowed.
"""

import ast
import sys
from pathlib import Path

import pytest

# Standard library modules that are acceptable
_STDLIB_MODULES = set(sys.stdlib_module_names)

# Path to our package source
_SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "vista_test" / "rpc"


def _get_all_imports(filepath: Path) -> set[str]:
    """Extract all top-level imported module names from a Python file."""
    source = filepath.read_text()
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                modules.add(top)
    return modules


class TestPurePython:
    """FR-011/FR-012: No native extensions or third-party dependencies."""

    def test_no_third_party_imports(self):
        """All imports in src/ are either stdlib or internal."""
        py_files = list(_SRC_DIR.glob("*.py"))
        assert len(py_files) > 0, "No Python files found in src/vista_test/rpc/"

        for filepath in py_files:
            imports = _get_all_imports(filepath)
            for mod in imports:
                is_stdlib = mod in _STDLIB_MODULES
                is_internal = mod == "vista_test"
                assert is_stdlib or is_internal, f"{filepath.name} imports non-stdlib module: {mod}"

    def test_no_ctypes_usage(self):
        """No ctypes or cffi (native extension loaders)."""
        for filepath in _SRC_DIR.glob("*.py"):
            source = filepath.read_text()
            assert "ctypes" not in source, f"{filepath.name} uses ctypes"
            assert "cffi" not in source, f"{filepath.name} uses cffi"

    def test_no_platform_specific_modules(self):
        """No platform-specific modules like winreg, msvcrt, etc."""
        platform_modules = {"winreg", "msvcrt", "_winapi", "msilib", "winsound"}
        for filepath in _SRC_DIR.glob("*.py"):
            imports = _get_all_imports(filepath)
            for mod in imports:
                assert mod not in platform_modules, (
                    f"{filepath.name} imports platform-specific: {mod}"
                )

    def test_source_files_exist(self):
        """Expected source files are present."""
        expected = {"__init__.py", "broker.py", "protocol.py", "transport.py", "errors.py"}
        actual = {f.name for f in _SRC_DIR.glob("*.py")}
        assert expected.issubset(actual), f"Missing files: {expected - actual}"

    def test_no_retry_logic(self):
        """FR-016: No retry/re-attempt logic in source code."""
        import re

        # Patterns that indicate retry logic
        retry_re = re.compile(
            r"\b(retry|retries|retry_count|max_retries|num_retries)\b",
            re.IGNORECASE,
        )
        for filepath in _SRC_DIR.glob("*.py"):
            source = filepath.read_text()
            for i, line in enumerate(source.split("\n"), 1):
                stripped = line.strip()
                if (
                    stripped.startswith("#")
                    or stripped.startswith('"""')
                    or stripped.startswith("'''")
                ):
                    continue
                if retry_re.search(line):
                    pytest.fail(f"{filepath.name}:{i} contains retry logic: {stripped}")
