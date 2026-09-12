"""Journal debit/credit split and post-plug balance."""

from __future__ import annotations

import unittest

from brokerage_bot.catalog import BALANCING_GL_CODE
from brokerage_bot.journal import build_journal, split_debit_credit
from brokerage_bot.ytd_map import MappedRow


def _mapped(*, gl_code=1200, name="Brokerage Cash", prior=0, mapped=0, entity="Wayne Family Trust"):
    return MappedRow(
        row_order=1,
        entity=entity,
        gl_code=gl_code,
        gl_name=name,
        prior_ledger=prior,
        statement_ytd_raw=mapped if gl_code < 3000 else -mapped,
        statement_ytd_mapped=mapped,
        sign_flipped=3000 <= gl_code <= 3999,
        missing_statement=False,
        flags=(),
        difference=mapped - prior,
    )


class JournalTests(unittest.TestCase):
    def test_negatives_flip_to_credit_side_as_positive(self):
        self.assertEqual(split_debit_credit(70000), (70000, 0))
        self.assertEqual(split_debit_credit(-4000), (0, 4000))
        self.assertEqual(split_debit_credit(0), (0, 0))

    def test_zero_differences_are_omitted(self):
        entry = build_journal(
            [
                _mapped(gl_code=1220, name="Fixed Income", prior=100000, mapped=100000),
                _mapped(gl_code=1200, prior=200000, mapped=270000),
            ]
        )
        codes = [line.gl_code for line in entry.lines if not line.is_balancing]
        self.assertEqual(codes, [1200])

    def test_entry_balances_after_plug(self):
        entry = build_journal(
            [
                _mapped(gl_code=1200, prior=200000, mapped=270000),
                _mapped(gl_code=3100, name="Dividend Income", prior=-8000, mapped=-12000),
            ]
        )
        self.assertTrue(entry.is_balanced)
        self.assertEqual(entry.total_debit, entry.total_credit)
        self.assertGreater(entry.plug_amount, 0)
        plug = entry.lines[-1]
        self.assertTrue(plug.is_balancing)
        self.assertEqual(plug.gl_code, BALANCING_GL_CODE)
        self.assertIn("UNBALANCED_BEFORE_PLUG", entry.flags)
        # 70000 debit vs 4000 credit → 66000 credit plug
        self.assertEqual(plug.credit, 66000)
        self.assertEqual(plug.debit, 0)

    def test_already_balanced_has_no_plug(self):
        entry = build_journal(
            [
                _mapped(gl_code=1200, prior=0, mapped=4000),
                _mapped(gl_code=3100, name="Dividend Income", prior=0, mapped=-4000),
            ]
        )
        self.assertTrue(entry.is_balanced)
        self.assertEqual(entry.plug_amount, 0)
        self.assertFalse(any(line.is_balancing for line in entry.lines))
        self.assertEqual(sum(line.debit for line in entry.lines), 4000)
        self.assertEqual(sum(line.credit for line in entry.lines), 4000)

    def test_plug_can_land_on_debit_side(self):
        entry = build_journal(
            [_mapped(gl_code=3100, name="Dividend Income", prior=0, mapped=-5000)]
        )
        plug = entry.lines[-1]
        self.assertEqual(plug.debit, 5000)
        self.assertEqual(plug.credit, 0)
        self.assertTrue(entry.is_balanced)


if __name__ == "__main__":
    unittest.main()
