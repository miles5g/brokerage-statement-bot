"""Browser pipeline files match the Python CLI on the shipped fixtures."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from brokerage_bot.io_util import load_tabular
from brokerage_bot.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
DOCS_FIXTURES = ROOT / "docs" / "fixtures"
RUNNER = ROOT / "tests" / "browser_parity.js"

OUTPUT_NAMES = (
    "transfers.csv",
    "transfers.json",
    "ytd_map.csv",
    "ytd_map.json",
    "ytd_paste_column.txt",
    "ytd_paste_column.csv",
    "journal.csv",
    "journal.json",
    "run_summary.json",
    "run_summary.md",
)


def _snippet(expected: bytes, actual: bytes) -> str:
    limit = min(len(expected), len(actual))
    for index in range(limit):
        if expected[index] != actual[index]:
            start = max(0, index - 40)
            return (
                f"first mismatch at byte {index}\n"
                f"python: {expected[start:index + 40]!r}\n"
                f"js:     {actual[start:index + 40]!r}"
            )
    return f"length python={len(expected)} js={len(actual)}"


class BrowserParityTests(unittest.TestCase):
    def test_docs_sample_matches_repo_fixtures(self):
        for name in ("statement_activity.csv", "gl_ledger.csv", "statement_ytd.csv"):
            self.assertEqual(
                (DOCS_FIXTURES / name).read_bytes(),
                (FIXTURES / name).read_bytes(),
                name,
            )

    def test_workbook_ledger_matches_csv_ledger(self):
        """The CLI reads the workbook. The page reads the CSV copy of it."""
        self.assertEqual(
            load_tabular(FIXTURES / "gl_workbook.xlsx"),
            load_tabular(FIXTURES / "gl_ledger.csv"),
        )

    def test_js_output_matches_python_cli(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python_dir = root / "python"
            js_dir = root / "js"
            run_pipeline(fixtures_dir=FIXTURES, output_dir=python_dir)
            completed = subprocess.run(
                [
                    node,
                    str(RUNNER),
                    str(FIXTURES / "statement_activity.csv"),
                    str(FIXTURES / "gl_ledger.csv"),
                    str(FIXTURES / "statement_ytd.csv"),
                    str(js_dir),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr or completed.stdout,
            )
            for name in OUTPUT_NAMES:
                expected = (python_dir / name).read_bytes()
                actual = (js_dir / name).read_bytes()
                self.assertEqual(expected, actual, f"{name}\n{_snippet(expected, actual)}")


if __name__ == "__main__":
    unittest.main()
