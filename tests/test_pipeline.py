"""End-to-end: one command produces transfer report, paste column, balanced journal."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from brokerage_bot.cli import main
from brokerage_bot.io_util import load_tabular
from brokerage_bot.pipeline import run_pipeline

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class PipelineTests(unittest.TestCase):
    def test_fixture_run_writes_three_pass_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            result = run_pipeline(fixtures_dir=FIXTURES, output_dir=dest)

            self.assertTrue((dest / "transfers.csv").exists())
            self.assertTrue((dest / "ytd_paste_column.csv").exists())
            self.assertTrue((dest / "ytd_paste_column.txt").exists())
            self.assertTrue((dest / "journal.csv").exists())
            self.assertTrue((dest / "run_summary.md").exists())

            self.assertGreaterEqual(len(result.transfers.lines), 8)
            self.assertFalse(result.transfers.balances_updated)
            self.assertTrue(
                all(line.balances_updated is False for line in result.transfers.lines)
            )
            ordinary = {line.category for line in result.transfers.lines}
            self.assertNotIn("dividend", ordinary)
            self.assertNotIn("interest", ordinary)
            self.assertNotIn("buy", ordinary)

            ledger = load_tabular(FIXTURES / "gl_ledger.csv")
            self.assertEqual(len(result.ytd.paste_column), len(ledger))
            self.assertEqual(result.ytd.rows[3].statement_ytd_mapped, 0)
            self.assertTrue(result.ytd.rows[3].missing_statement)
            self.assertEqual(result.ytd.rows[5].statement_ytd_mapped, -12000)
            self.assertEqual(result.ytd.rows[5].gl_code, 3100)

            paste = (dest / "ytd_paste_column.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(paste), len(ledger))
            self.assertEqual([int(v) for v in paste], result.ytd.paste_column)

            self.assertTrue(result.journal.is_balanced)
            self.assertEqual(result.journal.total_debit, result.journal.total_credit)
            self.assertGreater(result.journal.plug_amount, 0)
            self.assertTrue(result.journal.lines[-1].is_balancing)

    def test_cli_all_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["--fixtures", str(FIXTURES), "--output", str(tmp)])
            self.assertEqual(code, 0)
            self.assertTrue((Path(tmp) / "journal.json").exists())


if __name__ == "__main__":
    unittest.main()
