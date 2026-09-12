"""Scrub guards: synthetic-only accounts, emails, dollars, and dummy GLs."""

from __future__ import annotations

import unittest
from pathlib import Path

from brokerage_bot.amounts import AmountError, parse_whole_dollars
from brokerage_bot.io_util import load_tabular
from brokerage_bot.scrub import (
    ScrubError,
    assert_dummy_gl,
    assert_masked_account,
    assert_no_sensitive_text,
    parse_dummy_gl,
)
from brokerage_bot.transfers import classify_transfers
from brokerage_bot.ytd_map import map_ytd_column

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
TEXT_FIELDS = (
    "entity",
    "description",
    "security",
    "counterparty_entity",
    "activity_type",
    "gl_name",
)


class ScrubGuardTests(unittest.TestCase):
    def test_masked_account_ok_unmasked_rejected(self):
        self.assertEqual(assert_masked_account("****1234"), "****1234")
        self.assertEqual(assert_masked_account("**5678"), "**5678")
        with self.assertRaises(ScrubError):
            assert_masked_account("123456789")
        with self.assertRaises(ScrubError):
            assert_masked_account("1234")
        with self.assertRaises(ScrubError):
            assert_no_sensitive_text("send to account 991234567890", field="memo")

    def test_rejects_non_demo_email_allows_example_test(self):
        with self.assertRaises(ScrubError):
            assert_no_sensitive_text("write bruce@wayneenterprises.com", field="note")
        with self.assertRaises(ScrubError):
            assert_no_sensitive_text("peter.parker@gmail.com", field="note")
        assert_no_sensitive_text("review nobody@example.test", field="note")
        assert_no_sensitive_text("no email here", field="note")

    def test_rejects_taxpayer_id_pattern(self):
        with self.assertRaises(ScrubError):
            assert_no_sensitive_text("ssn 123-45-6789", field="note")

    def test_whole_dollars_only(self):
        self.assertEqual(parse_whole_dollars("$1,000"), 1000)
        self.assertEqual(parse_whole_dollars("(2000)"), -2000)
        self.assertEqual(parse_whole_dollars(100000), 100000)
        self.assertEqual(parse_whole_dollars("1000.0"), 1000)
        with self.assertRaises(AmountError):
            parse_whole_dollars("1000.50")
        with self.assertRaises(AmountError):
            parse_whole_dollars(10.25)

    def test_dummy_gl_allowlist(self):
        self.assertEqual(parse_dummy_gl("1200"), 1200)
        self.assertEqual(assert_dummy_gl(3100), 3100)
        with self.assertRaises(ScrubError):
            parse_dummy_gl("4510")
        with self.assertRaises(ScrubError):
            parse_dummy_gl("1001")

    def test_classify_transfers_rejects_unmasked_account_and_email(self):
        with self.assertRaises(ScrubError):
            classify_transfers(
                [
                    {
                        "date": "2026-08-01",
                        "entity": "Wayne Family Trust",
                        "account": "991234567890",
                        "activity_type": "wire_in",
                        "description": "Incoming wire",
                        "amount": "1000",
                    }
                ]
            )
        with self.assertRaises(ScrubError):
            classify_transfers(
                [
                    {
                        "date": "2026-08-01",
                        "entity": "Wayne Family Trust",
                        "account": "****1234",
                        "activity_type": "wire_in",
                        "description": "Email bruce@wayneenterprises.com",
                        "amount": "1000",
                    }
                ]
            )

    def test_map_rejects_non_dummy_gl(self):
        with self.assertRaises(ScrubError):
            map_ytd_column(
                [
                    {
                        "row_order": "1",
                        "entity": "Wayne Family Trust",
                        "gl_code": "5500",
                        "gl_name": "Not a demo account",
                        "prior_ledger": "0",
                    }
                ],
                [0],
            )

    def test_shipped_fixtures_pass_scrub(self):
        activities = load_tabular(FIXTURES / "statement_activity.csv")
        json_rows = load_tabular(FIXTURES / "statement_activity.json")
        ledger = load_tabular(FIXTURES / "gl_ledger.csv")
        for row in activities + json_rows:
            assert_masked_account(str(row["account"]))
            if str(row.get("counterparty_account") or "").strip():
                assert_masked_account(str(row["counterparty_account"]))
            parse_whole_dollars(row["amount"])
            for field in TEXT_FIELDS:
                if row.get(field):
                    assert_no_sensitive_text(str(row[field]), field=field)
        for row in ledger:
            parse_dummy_gl(row["gl_code"])
            parse_whole_dollars(row["prior_ledger"], field="prior_ledger")
            assert_no_sensitive_text(str(row["entity"]), field="entity")
            assert_no_sensitive_text(str(row["gl_name"]), field="gl_name")


if __name__ == "__main__":
    unittest.main()
