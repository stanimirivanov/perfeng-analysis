"""Exercise preparation of a wheel-ready, exact contract snapshot."""

import shutil
import tempfile
import unittest
from pathlib import Path

from perfeng_analysis.validation import CONTRACTS
from scripts.contracts_update import prepare_snapshot


class ContractUpdateTests(unittest.TestCase):
    def test_prepares_exact_snapshot_and_refuses_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projection, target = root / "projection", root / "contracts"
            shutil.copytree(CONTRACTS, projection, ignore=shutil.ignore_patterns("lock.json"))
            prepare_snapshot(projection, target)
            for member in CONTRACTS.rglob("*"):
                if member.is_file():
                    self.assertEqual(
                        (target / member.relative_to(CONTRACTS)).read_bytes(), member.read_bytes()
                    )
            with self.assertRaises(FileExistsError):
                prepare_snapshot(projection, target)

    def test_rejects_changed_bytes_before_creating_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projection, target = root / "projection", root / "contracts"
            shutil.copytree(CONTRACTS, projection, ignore=shutil.ignore_patterns("lock.json"))
            (projection / "LICENSE").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "LICENSE"):
                prepare_snapshot(projection, target)
            self.assertFalse(target.exists())
