"""Stdlib XLSX round-trip for the GL workpaper."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from brokerage_bot.io_util import load_tabular, write_xlsx_table
from brokerage_bot.xlsx_lite import read_xlsx, write_xlsx


class XlsxLiteTests(unittest.TestCase):
    def test_round_trip_headers_and_integers(self):
        rows = [
            {
                "row_order": 1,
                "entity": "Wayne Family Trust",
                "gl_code": 1200,
                "gl_name": "Brokerage Cash",
                "prior_ledger": 200000,
                "statement_ytd": 270000,
            },
            {
                "row_order": 2,
                "entity": "Wayne Family Trust",
                "gl_code": 3100,
                "gl_name": "Dividend Income",
                "prior_ledger": -8000,
                "statement_ytd": 12000,
            },
        ]
        fields = [
            "row_order",
            "entity",
            "gl_code",
            "gl_name",
            "prior_ledger",
            "statement_ytd",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gl.xlsx"
            write_xlsx_table(path, rows, fields, sheet_name="ledger")
            loaded = load_tabular(path)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0]["entity"], "Wayne Family Trust")
            self.assertEqual(int(loaded[0]["gl_code"]), 1200)
            self.assertEqual(int(loaded[1]["statement_ytd"]), 12000)

    def test_empty_cells_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sparse.xlsx"
            write_xlsx(path, [["a", "b"], ["1", ""], ["", "2"]])
            table = read_xlsx(path)
            self.assertEqual(table[0], ["a", "b"])
            self.assertEqual(table[1][1], "")


if __name__ == "__main__":
    unittest.main()
