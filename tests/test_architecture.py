"""Keep the offline analysis package independent of process and network adapters."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src/perfeng_analysis"
ADAPTER_MODULES = frozenset({"cli", "report_cli", "_output", "__main__"})
NETWORK_PROCESS_MODULES = frozenset(
    {"socket", "subprocess", "urllib.request", "http.client", "requests", "httpx"}
)


def _imports(tree: ast.AST) -> list[tuple[int, str, bool]]:
    imports: list[tuple[int, str, bool]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(
                (node.lineno, alias.name, alias.name.startswith("perfeng_analysis."))
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.extend(
                (
                    node.lineno,
                    f"{module}.{alias.name}".strip("."),
                    node.level > 0
                    or module == "perfeng_analysis"
                    or module.startswith("perfeng_analysis."),
                )
                for alias in node.names
            )
    return imports


def _matches(name: str, boundaries: frozenset[str]) -> bool:
    return any(name == boundary or name.startswith(f"{boundary}.") for boundary in boundaries)


def import_violations(package: Path) -> list[str]:
    """Report only direct imports crossing the documented analysis boundary."""
    violations: list[str] = []
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for line, imported, local in _imports(tree):
            local_name = imported.removeprefix("perfeng_analysis.")
            if _matches(imported, NETWORK_PROCESS_MODULES):
                violations.append(f"{path.name}:{line}: runtime import {imported}")
            if local and path.stem not in ADAPTER_MODULES and _matches(local_name, ADAPTER_MODULES):
                violations.append(f"{path.name}:{line}: core imports adapter {imported}")
    return violations


class ArchitectureTests(unittest.TestCase):
    def test_runtime_import_boundary(self) -> None:
        self.assertEqual(import_violations(PACKAGE), [])

    def test_rejects_adapter_and_network_imports_without_blocking_url_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            (package / "absolute_import.py").write_text(
                "from perfeng_analysis import cli\n",
                encoding="utf-8",
            )
            (package / "distribution.py").write_text(
                "from ._output import write_text_exclusive\n",
                encoding="utf-8",
            )
            (package / "report.py").write_text(
                "from urllib import request\n",
                encoding="utf-8",
            )
            (package / "future_analysis.py").write_text(
                "from .cli import main\n",
                encoding="utf-8",
            )
            (package / "validation.py").write_text(
                "from urllib.parse import urlsplit\n",
                encoding="utf-8",
            )
            self.assertEqual(
                import_violations(package),
                [
                    "absolute_import.py:1: core imports adapter perfeng_analysis.cli",
                    "distribution.py:1: core imports adapter _output.write_text_exclusive",
                    "future_analysis.py:1: core imports adapter cli.main",
                    "report.py:1: runtime import urllib.request",
                ],
            )


if __name__ == "__main__":
    unittest.main()
