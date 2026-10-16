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


def _imports(tree: ast.AST, package_parts: tuple[str, ...]) -> list[tuple[int, str, str]]:
    imports: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                parent_parts = package_parts[: len(package_parts) - node.level + 1]
                resolved_module = ".".join(("perfeng_analysis", *parent_parts, module)).strip(".")
            else:
                resolved_module = module
            imports.extend(
                (
                    node.lineno,
                    f"{module}.{alias.name}".strip("."),
                    f"{resolved_module}.{alias.name}".strip("."),
                )
                for alias in node.names
            )
    return imports


def _matches(name: str, boundaries: frozenset[str]) -> bool:
    return any(name == boundary or name.startswith(f"{boundary}.") for boundary in boundaries)


def import_violations(package: Path) -> list[str]:
    """Report only direct imports crossing the documented analysis boundary."""
    violations: list[str] = []
    adapters = frozenset(f"perfeng_analysis.{module}" for module in ADAPTER_MODULES)
    for path in sorted(package.rglob("*.py")):
        relative = path.relative_to(package)
        name = relative.as_posix()
        is_adapter = len(relative.parts) == 1 and path.stem in ADAPTER_MODULES
        package_parts = relative.parts[:-1]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for line, imported, resolved in _imports(tree, package_parts):
            if _matches(resolved, NETWORK_PROCESS_MODULES):
                violations.append(f"{name}:{line}: runtime import {imported}")
            if not is_adapter and _matches(resolved, adapters):
                violations.append(f"{name}:{line}: core imports adapter {imported}")
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
            nested = package / "nested"
            nested.mkdir()
            (nested / "__init__.py").write_text("", encoding="utf-8")
            (nested / "worker.py").write_text(
                "from .. import cli\nfrom subprocess import run\n",
                encoding="utf-8",
            )
            (nested / "cli.py").write_text(
                "from .._output import write_text_exclusive\n",
                encoding="utf-8",
            )
            (nested / "local.py").write_text(
                "from . import cli\n",
                encoding="utf-8",
            )
            self.assertEqual(
                import_violations(package),
                [
                    "absolute_import.py:1: core imports adapter perfeng_analysis.cli",
                    "distribution.py:1: core imports adapter _output.write_text_exclusive",
                    "future_analysis.py:1: core imports adapter cli.main",
                    "nested/cli.py:1: core imports adapter _output.write_text_exclusive",
                    "nested/worker.py:1: core imports adapter cli",
                    "nested/worker.py:2: runtime import subprocess.run",
                    "report.py:1: runtime import urllib.request",
                ],
            )


if __name__ == "__main__":
    unittest.main()
