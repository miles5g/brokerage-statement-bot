"""Row-aligned YTD mapping, 3000-series sign-flip, and missing→0."""

from __future__ import annotations

import unittest

from brokerage_bot.catalog import apply_statement_sign
from brokerage_bot.ytd_map import map_ytd_column


class YtdMapTests(unittest.TestCase):
    def test_maps_by_row_order_not_gl_code(self):
        ledger = [
            {
                "row_order": "1",
                "entity": "Wayne Family Trust",
                "gl_code": "1210",
                "gl_name": "Equities",
                "prior_ledger": "500000",
            },
            {
                "row_order": "2",
                "entity": "Wayne Family Trust",
                "gl_code": "3100",
                "gl_name": "Dividend Income",
                "prior_ledger": "-8000",
            },
            {
                "row_order": "3",
                "entity": "Wayne Family Trust",
                "gl_code": "1200",
                "gl_name": "Brokerage Cash",
                "prior_ledger": "200000",
            },
        ]
        # Deliberately not sorted by GL code: first raw value belongs to 1210.
        statement = [1000, 2000, 3000]
        result = map_ytd_column(ledger, statement)
        self.assertEqual(result.paste_column, [1000, -2000, 3000])
        self.assertEqual(result.rows[0].gl_code, 1210)
        self.assertEqual(result.rows[1].gl_code, 3100)
        self.assertTrue(result.rows[1].sign_flipped)
        self.assertFalse(result.rows[0].sign_flipped)

    def test_sign_flip_only_on_3000_series(self):
        self.assertEqual(apply_statement_sign(1200, 5000), 5000)
        self.assertEqual(apply_statement_sign(2100, -40000), -40000)
        self.assertEqual(apply_statement_sign(3100, 12000), -12000)
        self.assertEqual(apply_statement_sign(3200, 1000), -1000)
        self.assertEqual(apply_statement_sign(3300, 8000), -8000)

    def test_missing_statement_becomes_zero_and_is_flagged(self):
        ledger = [
            {
                "row_order": "1",
                "entity": "Wayne Family Trust",
                "gl_code": "1230",
                "gl_name": "Other Investments",
                "prior_ledger": "0",
                "statement_ytd": "",
            },
            {
                "row_order": "2",
                "entity": "Wayne Family Trust",
                "gl_code": "1200",
                "gl_name": "Brokerage Cash",
                "prior_ledger": "1000",
                "statement_ytd": "2000",
            },
        ]
        result = map_ytd_column(ledger)
        self.assertEqual(result.paste_column, [0, 2000])
        self.assertTrue(result.rows[0].missing_statement)
        self.assertIn("MISSING_STATEMENT_VALUE", result.rows[0].flags)
        self.assertFalse(result.rows[1].missing_statement)

    def test_row_count_mismatch_pads_and_flags(self):
        ledger = [
            {
                "row_order": "1",
                "entity": "Parker Holdings LLC",
                "gl_code": "1200",
                "gl_name": "Brokerage Cash",
                "prior_ledger": "80000",
            },
            {
                "row_order": "2",
                "entity": "Parker Holdings LLC",
                "gl_code": "1210",
                "gl_name": "Equities",
                "prior_ledger": "200000",
            },
        ]
        short = map_ytd_column(ledger, [115000])
        self.assertEqual(short.paste_column, [115000, 0])
        self.assertTrue(any("ROW_COUNT_MISMATCH" in flag for flag in short.flags))
        self.assertTrue(short.rows[1].missing_statement)

        long = map_ytd_column(ledger, [115000, 200000, 999])
        self.assertEqual(long.paste_column, [115000, 200000])
        self.assertTrue(any("EXTRA_STATEMENT_ROWS_DROPPED" in flag for flag in long.flags))

    def test_income_unexpected_positive_after_flip_is_flagged(self):
        ledger = [
            {
                "row_order": "1",
                "entity": "Wayne Family Trust",
                "gl_code": "3100",
                "gl_name": "Dividend Income",
                "prior_ledger": "1000",
            }
        ]
        result = map_ytd_column(ledger, [-4000])
        self.assertEqual(result.paste_column, [4000])
        self.assertIn("INCOME_SIGN_UNEXPECTED", result.rows[0].flags)
        self.assertIn("PRIOR_INCOME_NOT_CREDIT", result.rows[0].flags)


if __name__ == "__main__":
    unittest.main()
