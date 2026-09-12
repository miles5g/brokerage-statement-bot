"""Dummy chart of accounts and the documented 3000-series sign-flip rule.

These codes are invented for the demo. They are not a real firm's ledger.
"""

from __future__ import annotations

from dataclasses import dataclass


INCOME_GL_MIN = 3000
INCOME_GL_MAX = 3999
BALANCING_GL_CODE = 9999
BALANCING_GL_NAME = "Balancing (demo plug)"


@dataclass(frozen=True)
class DummyAccount:
    code: int
    name: str
    normal_balance: str  # "debit" or "credit"


DUMMY_GL_ACCOUNTS: dict[int, DummyAccount] = {
    1200: DummyAccount(1200, "Brokerage Cash", "debit"),
    1210: DummyAccount(1210, "Equities", "debit"),
    1220: DummyAccount(1220, "Fixed Income", "debit"),
    1230: DummyAccount(1230, "Other Investments", "debit"),
    2100: DummyAccount(2100, "Margin Loan", "credit"),
    3100: DummyAccount(3100, "Dividend Income", "credit"),
    3200: DummyAccount(3200, "Interest Income", "credit"),
    3300: DummyAccount(3300, "Realized Gain/Loss", "credit"),
    BALANCING_GL_CODE: DummyAccount(
        BALANCING_GL_CODE, BALANCING_GL_NAME, "credit"
    ),
}

ALLOWED_GL_CODES = frozenset(DUMMY_GL_ACCOUNTS)

SIGN_FLIP_RULE = """
SIGN-FLIP RULE (demo only, dummy 3000-series)
=============================================
Brokerage statements typically report dividend, interest, and realized
gain as positive "income received." This demo's workpaper uses a
debit-positive convention: income and gain accounts store credit
balances as negative numbers.

For GL codes 3000–3999 (Dividend Income 3100, Interest Income 3200,
Realized Gain/Loss 3300, and any other demo income/gain account in
that range):

    mapped_ytd = -statement_amount

All other dummy GLs keep the statement amount as-is:

    mapped_ytd = statement_amount

Missing statement values map to 0. The flip is applied after the
missing-to-zero substitution.
""".strip()


def is_income_gain_account(gl_code: int) -> bool:
    return INCOME_GL_MIN <= gl_code <= INCOME_GL_MAX


def apply_statement_sign(gl_code: int, statement_amount: int) -> int:
    """Apply the documented 3000-series sign-flip to a raw statement amount."""
    if is_income_gain_account(gl_code):
        return -statement_amount
    return statement_amount


def gl_name(gl_code: int) -> str:
    account = DUMMY_GL_ACCOUNTS.get(gl_code)
    if account:
        return account.name
    return f"Unknown dummy GL {gl_code}"
