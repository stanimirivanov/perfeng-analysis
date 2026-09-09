import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from perfeng_analysis._output import write_text_exclusive


class ExclusiveOutputTests(unittest.TestCase):
    def test_final_name_appears_only_after_complete_bytes_are_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "normalized-result.json"
            content = "complete normalized result\n"
            real_link = os.link

            def inspect_then_link(source: str | Path, destination: str | Path) -> None:
                self.assertFalse(output.exists())
                self.assertEqual(Path(source).read_text(encoding="utf-8"), content)
                real_link(source, destination)

            with patch("perfeng_analysis._output.os.link", side_effect=inspect_then_link):
                write_text_exclusive(output, content)

            self.assertEqual(output.read_text(encoding="utf-8"), content)
            self.assertEqual(list(output.parent.glob(".*.tmp")), [])

    def test_existing_output_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis-result.json"
            output.write_text("existing\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                write_text_exclusive(output, "replacement\n")

            self.assertEqual(output.read_text(encoding="utf-8"), "existing\n")
            self.assertEqual(list(output.parent.glob(".*.tmp")), [])

    def test_failed_publication_removes_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "normalized-result.json"

            with patch("perfeng_analysis._output.os.link", side_effect=OSError("link failed")):
                with self.assertRaisesRegex(OSError, "link failed"):
                    write_text_exclusive(output, "result\n")

            self.assertFalse(output.exists())
            self.assertEqual(list(output.parent.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
