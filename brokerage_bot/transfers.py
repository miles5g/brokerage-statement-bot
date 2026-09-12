"""Transfers pass: identify cash/security movements to record, not income.

This pass never updates ledger balances. It only emits a review table.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from brokerage_bot.amounts import parse_whole_dollars
from brokerage_bot.scrub import (
    ScrubError,
    assert_masked_account,
    assert_no_sensitive_text,
    collect_scrub_issues,
)


TRANSFER_TYPES = frozenset(
    {
        "wire",
        "wire_in",
        "wire_out",
        "ach",
        "ach_in",
        "ach_out",
        "contribution",
        "distribution",
        "cash_transfer",
        "security_transfer",
        "transfer",
        "margin_paydown",
        "loan_paydown",
        "paydown",
    }
)

NON_TRANSFER_TYPES = frozenset(
    {
        "dividend",
        "interest",
        "margin_interest",
        "buy",
        "sell",
        "trade",
        "market_move",
        "unrealized",
        "unrealized_gain",
        "unrealized_loss",
        "realized_gain",
        "realized_loss",
        "fee",
        "commission",
    }
)

# More specific patterns first. "journal" alone is only a possible transfer.
_KEYWORD_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(margin|loan)\s+paydown\b", re.I), "margin_paydown"),
    (re.compile(r"\bpaydown\b", re.I), "margin_paydown"),
    (re.compile(r"\bsecurity transfer\b|\bshare journal\b|\bacats\b", re.I), "security_transfer"),
    (re.compile(r"\bcash transfer\b|\bcash journal\b", re.I), "cash_transfer"),
    (re.compile(r"\bcontribution\b", re.I), "contribution"),
    (re.compile(r"\bdistribution\b", re.I), "distribution"),
    (re.compile(r"\bwire\b", re.I), "wire"),
    (re.compile(r"\bach\b", re.I), "ach"),
    (re.compile(r"\bjournal\b", re.I), "possible_transfer"),
)

LARGE_AMOUNT_THRESHOLD = 100_000
KNOWN_ENTITIES = frozenset({"Wayne Family Trust", "Parker Holdings LLC"})


@dataclass(frozen=True)
class TransferLine:
    date: str
    entity: str
    account: str
    category: str
    description: str
    amount: int
    security: str
    quantity: str
    counterparty_entity: str
    counterparty_account: str
    flags: tuple[str, ...]
    record_action: str
    source_activity_type: str
    classified_via: str
    balances_updated: bool = False

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["flags"] = "|".join(self.flags)
        row["balances_updated"] = "false"
        return row


@dataclass
class TransferReport:
    lines: list[TransferLine] = field(default_factory=list)
    skipped_ordinary: int = 0
    balances_updated: bool = False

    def as_payload(self) -> dict[str, Any]:
        return {
            "balances_updated": False,
            "note": "Transfers pass does not update ledger balances.",
            "to_record_count": len(self.lines),
            "skipped_ordinary_count": self.skipped_ordinary,
            "review_count": sum(1 for line in self.lines if line.record_action == "REVIEW"),
            "lines": [line.as_row() for line in self.lines],
        }


def classify_transfers(activities: list[Mapping[str, Any]]) -> TransferReport:
    """Return transfer / contribution / paydown lines plus review flags."""
    report = TransferReport()
    for raw in activities:
        row = {str(k): raw[k] for k in raw}
        _scrub_activity(row)
        decision = _classify_row(row)
        if decision is None:
            report.skipped_ordinary += 1
            continue
        report.lines.append(decision)
    return report


def _scrub_activity(row: Mapping[str, Any]) -> None:
    for field_name in (
        "entity",
        "description",
        "security",
        "counterparty_entity",
        "activity_type",
        "date",
    ):
        value = row.get(field_name)
        if value:
            assert_no_sensitive_text(str(value), field=field_name)
    account = str(row.get("account") or "").strip()
    if account:
        assert_masked_account(account, field="account")
    counter = str(row.get("counterparty_account") or "").strip()
    if counter:
        assert_masked_account(counter, field="counterparty_account")
    parse_whole_dollars(row.get("amount"), field="amount")


def _classify_row(row: Mapping[str, Any]) -> TransferLine | None:
    activity_type = str(row.get("activity_type") or "").strip().lower()
    description = str(row.get("description") or "").strip()
    classified_via = "activity_type"
    category = activity_type
    flags: list[str] = []

    if activity_type in NON_TRANSFER_TYPES:
        return None
    if activity_type in TRANSFER_TYPES:
        category = _normalize_category(activity_type)
    elif activity_type in {"", "unknown", "other"}:
        keyword_category = _category_from_description(description)
        if keyword_category is None:
            return None
        category = keyword_category
        classified_via = "description_keyword"
        if keyword_category == "possible_transfer":
            flags.append("AMBIGUOUS_TYPE")
    else:
        raise ScrubError(
            f"activity_type={activity_type!r} is not a known demo type"
        )

    amount = parse_whole_dollars(row.get("amount"), field="amount")
    entity = str(row.get("entity") or "").strip()
    counterparty_entity = str(row.get("counterparty_entity") or "").strip()
    counterparty_account = str(row.get("counterparty_account") or "").strip()
    security = str(row.get("security") or "").strip()
    quantity = str(row.get("quantity") or "").strip()

    if abs(amount) >= LARGE_AMOUNT_THRESHOLD:
        flags.append("LARGE_AMOUNT")
    if (
        counterparty_entity
        and entity
        and counterparty_entity != entity
        and counterparty_entity in KNOWN_ENTITIES
        and entity in KNOWN_ENTITIES
    ):
        flags.append("INTER_ENTITY")
    if category in {"wire", "wire_in", "wire_out", "ach", "contribution", "distribution"}:
        if not counterparty_entity and not counterparty_account:
            flags.append("MISSING_COUNTERPARTY")
    if category == "security_transfer" and not quantity:
        flags.append("SECURITY_WITHOUT_QTY")
    if classified_via == "description_keyword":
        flags.append("KEYWORD_CLASSIFIED")

    for extra in collect_scrub_issues(description, field="description"):
        flags.append(extra.upper())

    record_action = "REVIEW" if flags else "RECORD"
    if flags:
        flags.append("NEEDS_HUMAN_REVIEW")

    return TransferLine(
        date=str(row.get("date") or "").strip(),
        entity=entity,
        account=str(row.get("account") or "").strip(),
        category=category,
        description=description,
        amount=amount,
        security=security,
        quantity=quantity,
        counterparty_entity=counterparty_entity,
        counterparty_account=counterparty_account,
        flags=tuple(flags),
        record_action=record_action,
        source_activity_type=activity_type,
        classified_via=classified_via,
        balances_updated=False,
    )


def _normalize_category(activity_type: str) -> str:
    aliases = {
        "wire_in": "wire",
        "wire_out": "wire",
        "ach_in": "ach",
        "ach_out": "ach",
        "loan_paydown": "margin_paydown",
        "paydown": "margin_paydown",
        "transfer": "cash_transfer",
    }
    return aliases.get(activity_type, activity_type)


def _category_from_description(description: str) -> str | None:
    if not description:
        return None
    for pattern, category in _KEYWORD_RULES:
        if pattern.search(description):
            return category
    return None


TRANSFER_CSV_FIELDS = (
    "date",
    "entity",
    "account",
    "category",
    "description",
    "amount",
    "security",
    "quantity",
    "counterparty_entity",
    "counterparty_account",
    "flags",
    "record_action",
    "classified_via",
    "balances_updated",
)
