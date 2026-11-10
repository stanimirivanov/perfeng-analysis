"""Exercise the Analysis shadow checks without hosted release fixtures."""

import shutil
import tempfile
import unittest
from pathlib import Path

from perfeng_analysis.validation import CONTRACTS
from scripts.contracts_shadow import check_parity


class ContractDistributionTests(unittest.TestCase):
    def test_exact_projection_preserves_valid_and_invalid_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            projection = Path(directory) / "projection"
            shutil.copytree(CONTRACTS, projection)
            (projection / "lock.json").unlink()

            self.assertEqual(check_parity(projection), 13)

    def test_changed_or_missing_projected_member_is_rejected(self) -> None:
        for tamper in (True, False):
            with self.subTest(tamper=tamper), tempfile.TemporaryDirectory() as directory:
                projection = Path(directory) / "projection"
                shutil.copytree(CONTRACTS, projection)
                (projection / "lock.json").unlink()
                license_file = projection / "LICENSE"
                if tamper:
                    license_file.write_bytes(b"changed")
                else:
                    license_file.unlink()

                with self.assertRaisesRegex(ValueError, "LICENSE"):
                    check_parity(projection)

    def test_extra_projected_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            projection = Path(directory) / "projection"
            shutil.copytree(CONTRACTS, projection)
            (projection / "lock.json").unlink()
            (projection / "unreviewed.json").write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unreviewed projected member"):
                check_parity(projection)
