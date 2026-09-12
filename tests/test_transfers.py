"""Transfer detection: movements to record vs ordinary income/market activity."""

from __future__ import annotations

import unittest
from pathlib import Path

from brokerage_bot.io_util import load_tabular
from brokerage_bot.transfers import classify_transfers

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _row(**overrides):
    base = {
        "date": "2026-08-15",
        "entity": "Wayne Family Trust",
        "account": "****1234",
        "activity_type": "dividend",
        "description": "Gotham Utilities dividend",
        "amount": "1000",
        "security": "",
        "quantity": "",
        "counterparty_entity": "",
        "counterparty_account": "",
    }
    base.update(overrides)
    return base


class TransferDetectionTests(unittest.TestCase):
    def test_detects_wires_contributions_distributions_transfers_paydowns(self):
        cases = [
            ("wire_in", "Incoming wire", 10000),
            ("wire_out", "Outgoing wire", -2000),
            ("contribution", "ACH contribution", 50000),
            ("distribution", "Owner distribution", -5000),
            ("cash_transfer", "Cash journal", 15000),
            ("security_transfer", "Share journal", 25000),
            ("margin_paydown", "Margin loan paydown", 10000),
            ("loan_paydown", "Loan paydown", 4000),
        ]
        for activity_type, description, amount in cases:
            with self.subTest(activity_type=activity_type):
                extra = {}
                if "wire" in activity_type or activity_type in {
                    "contribution",
                    "distribution",
                }:
                    extra = {
                        "counterparty_entity": "Bruce Wayne",
                        "counterparty_account": "****4321",
                    }
                if activity_type == "security_transfer":
                    extra = {"security": "Metropolis REIT", "quantity": "50"}
                report = classify_transfers(
                    [
                        _row(
                            activity_type=activity_type,
                            description=description,
                            amount=amount,
                            **extra,
                        )
                    ]
                )
                self.assertEqual(len(report.lines), 1)
                self.assertEqual(report.skipped_ordinary, 0)
                self.assertFalse(report.balances_updated)
                self.assertFalse(report.lines[0].balances_updated)

    def test_excludes_ordinary_dividends_interest_and_market_moves(self):
        ordinary = [
            ("dividend", "Gotham Utilities dividend", 1000),
            ("interest", "Sweep interest", 2000),
            ("margin_interest", "Margin interest charge", -1000),
            ("buy", "Buy Gotham Steel", -50000),
            ("sell", "Sell Daily Planet lot", 40000),
            ("market_move", "Unrealized mark", 15000),
            ("realized_gain", "Realized gain on lot", 8000),
            ("fee", "Account fee", -1000),
        ]
        report = classify_transfers(
            [
                _row(activity_type=kind, description=desc, amount=amount)
                for kind, desc, amount in ordinary
            ]
        )
        self.assertEqual(report.lines, [])
        self.assertEqual(report.skipped_ordinary, len(ordinary))

    def test_keyword_fallback_flags_ambiguous_journal(self):
        report = classify_transfers(
            [_row(activity_type="unknown", description="Advisor journal unspecified")]
        )
        self.assertEqual(len(report.lines), 1)
        self.assertEqual(report.lines[0].category, "possible_transfer")
        self.assertIn("AMBIGUOUS_TYPE", report.lines[0].flags)
        self.assertEqual(report.lines[0].record_action, "REVIEW")
        self.assertEqual(report.lines[0].classified_via, "description_keyword")

    def test_large_amount_and_inter_entity_and_missing_counterparty_flags(self):
        large = classify_transfers(
            [
                _row(
                    activity_type="wire_in",
                    description="Incoming wire contribution",
                    amount=100000,
                    counterparty_entity="Wayne Family Trust",
                    counterparty_account="****4321",
                )
            ]
        )
        self.assertIn("LARGE_AMOUNT", large.lines[0].flags)

        inter = classify_transfers(
            [
                _row(
                    entity="Parker Holdings LLC",
                    account="****5678",
                    activity_type="cash_transfer",
                    description="Cash journal to Wayne Family Trust",
                    amount=-15000,
                    counterparty_entity="Wayne Family Trust",
                    counterparty_account="****1234",
                )
            ]
        )
        self.assertIn("INTER_ENTITY", inter.lines[0].flags)

        missing = classify_transfers(
            [
                _row(
                    activity_type="wire_out",
                    description="Outgoing wire to external counterparty not listed",
                    amount=-1000,
                )
            ]
        )
        self.assertIn("MISSING_COUNTERPARTY", missing.lines[0].flags)

    def test_fixture_csv_and_json_agree_and_skip_ordinary(self):
        csv_report = classify_transfers(load_tabular(FIXTURES / "statement_activity.csv"))
        json_report = classify_transfers(load_tabular(FIXTURES / "statement_activity.json"))
        self.assertEqual(len(csv_report.lines), len(json_report.lines))
        self.assertEqual(
            [line.category for line in csv_report.lines],
            [line.category for line in json_report.lines],
        )
        categories = {line.category for line in csv_report.lines}
        self.assertTrue(
            categories
            >= {
                "wire",
                "contribution",
                "distribution",
                "cash_transfer",
                "security_transfer",
                "margin_paydown",
                "possible_transfer",
            }
        )
        self.assertNotIn("dividend", categories)
        self.assertNotIn("interest", categories)
        self.assertFalse(csv_report.balances_updated)
        self.assertGreaterEqual(csv_report.skipped_ordinary, 8)


if __name__ == "__main__":
    unittest.main()
