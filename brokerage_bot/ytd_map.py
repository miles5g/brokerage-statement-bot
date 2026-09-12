"""YTD map pass: produce a statement/YTD column aligned 1:1 by row order."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from brokerage_bot.amounts import parse_optional_whole_dollars, parse_whole_dollars
from brokerage_bot.catalog import (
    SIGN_FLIP_RULE,
    apply_statement_sign,
    gl_name,
    is_income_gain_account,
)
from brokerage_bot.scrub import parse_dummy_gl, scrub_record


@dataclass(frozen=True)
class MappedRow:
    row_order: int
    entity: str
    gl_code: int
    gl_name: str
    prior_ledger: int
    statement_ytd_raw: int
    statement_ytd_mapped: int
    sign_flipped: bool
    missing_statement: bool
    flags: tuple[str, ...]
    difference: int

    def as_row(self) -> dict[str, Any]:
        return {
            "row_order": self.row_order,
            "entity": self.entity,
            "gl_code": self.gl_code,
            "gl_name": self.gl_name,
            "prior_ledger": self.prior_ledger,
            "statement_ytd_raw": self.statement_ytd_raw,
            "statement_ytd_mapped": self.statement_ytd_mapped,
            "sign_flipped": "yes" if self.sign_flipped else "no",
            "missing_statement": "yes" if self.missing_statement else "no",
            "difference": self.difference,
            "flags": "|".join(self.flags),
        }


@dataclass
class YtdMapResult:
    rows: list[MappedRow] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    sign_flip_rule: str = SIGN_FLIP_RULE

    @property
    def paste_column(self) -> list[int]:
        return [row.statement_ytd_mapped for row in self.rows]

    def as_payload(self) -> dict[str, Any]:
        return {
            "sign_flip_rule": self.sign_flip_rule,
            "row_count": len(self.rows),
            "flags": list(self.flags),
            "paste_column": self.paste_column,
            "rows": [row.as_row() for row in self.rows],
        }


def map_ytd_column(
    ledger_rows: Sequence[Mapping[str, Any]],
    statement_values: Sequence[Any] | None = None,
) -> YtdMapResult:
    """Map statement YTD figures onto GL rows by positional order.

    ``statement_values`` is optional. When omitted, each ledger row may carry
    its own ``statement_ytd`` / ``statement_ytd_raw`` cell. A missing cell
    becomes 0. Extra statement values without a ledger row are flagged and
    dropped so the paste column stays 1:1 with the ledger.
    """
    result = YtdMapResult()
    raw_values = _coerce_statement_list(statement_values)
    if raw_values is not None and len(raw_values) != len(ledger_rows):
        result.flags.append(
            f"ROW_COUNT_MISMATCH:ledger={len(ledger_rows)},statement={len(raw_values)}"
        )

    for index, ledger in enumerate(ledger_rows):
        scrub_record(ledger, ("entity", "gl_name"))
        gl_code = parse_dummy_gl(ledger.get("gl_code"))
        name = str(ledger.get("gl_name") or "").strip() or gl_name(gl_code)
        prior = parse_whole_dollars(ledger.get("prior_ledger"), field="prior_ledger")
        row_order = _row_order(ledger, index)

        missing = False
        if raw_values is not None:
            if index < len(raw_values):
                parsed = parse_optional_whole_dollars(
                    raw_values[index], field="statement_ytd"
                )
            else:
                parsed = None
                missing = True
        else:
            parsed = parse_optional_whole_dollars(
                _row_statement_cell(ledger), field="statement_ytd"
            )

        if parsed is None:
            missing = True
            raw_amount = 0
        else:
            raw_amount = parsed

        mapped = apply_statement_sign(gl_code, raw_amount)
        flipped = is_income_gain_account(gl_code)
        flags: list[str] = []
        if missing:
            flags.append("MISSING_STATEMENT_VALUE")
            result.flags.append(f"MISSING_STATEMENT_VALUE:row={row_order}")
        if flipped and mapped > 0:
            flags.append("INCOME_SIGN_UNEXPECTED")
            result.flags.append(f"INCOME_SIGN_UNEXPECTED:row={row_order}")
        if flipped and prior > 0:
            flags.append("PRIOR_INCOME_NOT_CREDIT")
            result.flags.append(f"PRIOR_INCOME_NOT_CREDIT:row={row_order}")

        result.rows.append(
            MappedRow(
                row_order=row_order,
                entity=str(ledger.get("entity") or "").strip(),
                gl_code=gl_code,
                gl_name=name,
                prior_ledger=prior,
                statement_ytd_raw=raw_amount,
                statement_ytd_mapped=mapped,
                sign_flipped=flipped,
                missing_statement=missing,
                flags=tuple(flags),
                difference=mapped - prior,
            )
        )

    if raw_values is not None and len(raw_values) > len(ledger_rows):
        result.flags.append(
            f"EXTRA_STATEMENT_ROWS_DROPPED:{len(raw_values) - len(ledger_rows)}"
        )
    return result


def _row_order(ledger: Mapping[str, Any], index: int) -> int:
    raw = ledger.get("row_order")
    if raw is None or str(raw).strip() == "":
        return index + 1
    return int(str(raw).strip())


def _row_statement_cell(ledger: Mapping[str, Any]) -> Any:
    for key in ("statement_ytd", "statement_ytd_raw", "ytd", "statement"):
        if key in ledger:
            return ledger.get(key)
    return None


def _coerce_statement_list(statement_values: Sequence[Any] | None) -> list[Any] | None:
    if statement_values is None:
        return None
    values: list[Any] = []
    for item in statement_values:
        if isinstance(item, Mapping):
            values.append(_row_statement_cell(item))
        else:
            values.append(item)
    return values


YTD_CSV_FIELDS = (
    "row_order",
    "entity",
    "gl_code",
    "gl_name",
    "prior_ledger",
    "statement_ytd_raw",
    "statement_ytd_mapped",
    "sign_flipped",
    "missing_statement",
    "difference",
    "flags",
)
