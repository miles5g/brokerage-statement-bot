"""Journal pass: turn a difference column into Debit/Credit plus a plug row."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from brokerage_bot.catalog import BALANCING_GL_CODE, BALANCING_GL_NAME
from brokerage_bot.ytd_map import MappedRow


LARGE_PLUG_THRESHOLD = 100_000


@dataclass(frozen=True)
class JournalLine:
    line: int
    entity: str
    gl_code: int
    gl_name: str
    debit: int
    credit: int
    memo: str
    flags: tuple[str, ...]
    is_balancing: bool = False

    def as_row(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "entity": self.entity,
            "gl_code": self.gl_code,
            "gl_name": self.gl_name,
            "debit": self.debit,
            "credit": self.credit,
            "memo": self.memo,
            "flags": "|".join(self.flags),
            "is_balancing": "yes" if self.is_balancing else "no",
        }


@dataclass
class JournalEntry:
    lines: list[JournalLine] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    total_debit: int = 0
    total_credit: int = 0
    plug_amount: int = 0

    @property
    def is_balanced(self) -> bool:
        return self.total_debit == self.total_credit

    def as_payload(self) -> dict[str, Any]:
        return {
            "balanced": self.is_balanced,
            "total_debit": self.total_debit,
            "total_credit": self.total_credit,
            "plug_amount": self.plug_amount,
            "flags": list(self.flags),
            "lines": [line.as_row() for line in self.lines],
        }


def split_debit_credit(difference: int) -> tuple[int, int]:
    """Positive difference → debit; negative difference → credit (as a positive)."""
    if difference > 0:
        return difference, 0
    if difference < 0:
        return 0, -difference
    return 0, 0


def build_journal(
    mapped_rows: Sequence[MappedRow],
    *,
    memo: str = "Month-end statement update (demo)",
) -> JournalEntry:
    """Build a debit/credit journal from mapped minus prior, then add a plug."""
    entry = JournalEntry()
    line_no = 1
    for row in mapped_rows:
        debit, credit = split_debit_credit(row.difference)
        if debit == 0 and credit == 0:
            continue
        flags = list(row.flags)
        entry.lines.append(
            JournalLine(
                line=line_no,
                entity=row.entity,
                gl_code=row.gl_code,
                gl_name=row.gl_name,
                debit=debit,
                credit=credit,
                memo=memo,
                flags=tuple(flags),
            )
        )
        line_no += 1

    debit_total = sum(line.debit for line in entry.lines)
    credit_total = sum(line.credit for line in entry.lines)
    plug = debit_total - credit_total
    if plug != 0:
        entry.flags.append("UNBALANCED_BEFORE_PLUG")
        entry.plug_amount = abs(plug)
        if abs(plug) >= LARGE_PLUG_THRESHOLD:
            entry.flags.append("LARGE_PLUG")
        if plug > 0:
            plug_debit, plug_credit = 0, plug
        else:
            plug_debit, plug_credit = -plug, 0
        entry.lines.append(
            JournalLine(
                line=line_no,
                entity="ALL",
                gl_code=BALANCING_GL_CODE,
                gl_name=BALANCING_GL_NAME,
                debit=plug_debit,
                credit=plug_credit,
                memo="Balancing row — review transfers before posting (demo plug)",
                flags=tuple(entry.flags),
                is_balancing=True,
            )
        )

    entry.total_debit = sum(line.debit for line in entry.lines)
    entry.total_credit = sum(line.credit for line in entry.lines)
    if entry.total_debit != entry.total_credit:
        raise AssertionError("journal construction failed to balance")
    return entry


JOURNAL_CSV_FIELDS = (
    "line",
    "entity",
    "gl_code",
    "gl_name",
    "debit",
    "credit",
    "memo",
    "flags",
    "is_balancing",
)
