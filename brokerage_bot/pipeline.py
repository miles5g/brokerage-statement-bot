"""Run the three demo passes and write artifacts under output/."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brokerage_bot.amounts import format_dollars
from brokerage_bot.catalog import SIGN_FLIP_RULE
from brokerage_bot.io_util import load_tabular, write_csv, write_json, write_lines
from brokerage_bot.journal import JOURNAL_CSV_FIELDS, JournalEntry, build_journal
from brokerage_bot.transfers import TRANSFER_CSV_FIELDS, TransferReport, classify_transfers
from brokerage_bot.ytd_map import YTD_CSV_FIELDS, YtdMapResult, map_ytd_column


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
DEFAULT_FIXTURES = REPO_ROOT / "fixtures"
DEFAULT_OUTPUT = REPO_ROOT / "output"


@dataclass(frozen=True)
class PipelinePaths:
    activity: Path
    ledger: Path
    statement_ytd: Path | None


@dataclass
class PipelineResult:
    transfers: TransferReport
    ytd: YtdMapResult
    journal: JournalEntry
    written: list[Path]


def resolve_fixture_paths(fixtures_dir: Path | str) -> PipelinePaths:
    root = Path(fixtures_dir)
    activity = _first_existing(
        root / "statement_activity.csv",
        root / "statement_activity.json",
    )
    ledger = _first_existing(
        root / "gl_workbook.xlsx",
        root / "gl_ledger.csv",
    )
    ytd_path = root / "statement_ytd.csv"
    statement_ytd = ytd_path if ytd_path.exists() else None
    return PipelinePaths(activity=activity, ledger=ledger, statement_ytd=statement_ytd)


def run_pipeline(
    *,
    fixtures_dir: Path | str = DEFAULT_FIXTURES,
    output_dir: Path | str = DEFAULT_OUTPUT,
    activity_path: Path | str | None = None,
    ledger_path: Path | str | None = None,
    statement_ytd_path: Path | str | None = None,
) -> PipelineResult:
    paths = resolve_fixture_paths(fixtures_dir)
    activity = Path(activity_path) if activity_path else paths.activity
    ledger = Path(ledger_path) if ledger_path else paths.ledger
    statement_src: Path | None
    if statement_ytd_path:
        statement_src = Path(statement_ytd_path)
    else:
        statement_src = paths.statement_ytd

    activities = load_tabular(activity)
    ledger_rows = load_tabular(ledger)
    statement_rows = load_tabular(statement_src) if statement_src else None
    # Prefer a dedicated statement file when the ledger already has the column
    # as well — dedicated file is the positional source of truth.
    statement_values: list[Any] | None
    if statement_rows is not None:
        statement_values = statement_rows
    else:
        statement_values = None

    transfers = classify_transfers(activities)
    ytd = map_ytd_column(ledger_rows, statement_values)
    journal = build_journal(ytd.rows)

    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    written = _write_outputs(dest, transfers, ytd, journal)
    return PipelineResult(
        transfers=transfers, ytd=ytd, journal=journal, written=written
    )


def _write_outputs(
    dest: Path,
    transfers: TransferReport,
    ytd: YtdMapResult,
    journal: JournalEntry,
) -> list[Path]:
    written: list[Path] = []
    written.append(
        write_csv(
            dest / "transfers.csv",
            [line.as_row() for line in transfers.lines],
            TRANSFER_CSV_FIELDS,
        )
    )
    written.append(write_json(dest / "transfers.json", transfers.as_payload()))
    written.append(
        write_csv(dest / "ytd_map.csv", [row.as_row() for row in ytd.rows], YTD_CSV_FIELDS)
    )
    written.append(write_json(dest / "ytd_map.json", ytd.as_payload()))
    written.append(write_lines(dest / "ytd_paste_column.txt", ytd.paste_column))
    written.append(
        write_csv(
            dest / "ytd_paste_column.csv",
            [{"statement_ytd_mapped": value} for value in ytd.paste_column],
            ["statement_ytd_mapped"],
        )
    )
    written.append(
        write_csv(
            dest / "journal.csv",
            [line.as_row() for line in journal.lines],
            JOURNAL_CSV_FIELDS,
        )
    )
    written.append(write_json(dest / "journal.json", journal.as_payload()))
    written.append(write_json(dest / "run_summary.json", _summary_payload(transfers, ytd, journal)))
    summary_md = dest / "run_summary.md"
    summary_md.write_text(_summary_markdown(transfers, ytd, journal), encoding="utf-8")
    written.append(summary_md)
    return written


def _summary_payload(
    transfers: TransferReport, ytd: YtdMapResult, journal: JournalEntry
) -> dict[str, Any]:
    return {
        "synthetic_only": True,
        "balances_updated_in_transfers_pass": False,
        "transfers_to_record": len(transfers.lines),
        "transfers_review": sum(1 for line in transfers.lines if line.record_action == "REVIEW"),
        "ordinary_activity_skipped": transfers.skipped_ordinary,
        "ytd_rows": len(ytd.rows),
        "ytd_flags": ytd.flags,
        "journal_balanced": journal.is_balanced,
        "journal_total_debit": journal.total_debit,
        "journal_total_credit": journal.total_credit,
        "journal_plug": journal.plug_amount,
        "journal_flags": journal.flags,
    }


def _summary_markdown(
    transfers: TransferReport, ytd: YtdMapResult, journal: JournalEntry
) -> str:
    transfer_lines = "\n".join(
        f"- {line.date} | {line.entity} | {line.category} | "
        f"{format_dollars(line.amount)} | {line.record_action} | "
        f"{'|'.join(line.flags) or '—'}"
        for line in transfers.lines
    )
    ytd_lines = "\n".join(
        f"- {row.row_order}. {row.entity} {row.gl_code} {row.gl_name}: "
        f"raw {format_dollars(row.statement_ytd_raw)} → mapped "
        f"{format_dollars(row.statement_ytd_mapped)}"
        f"{' (sign-flip)' if row.sign_flipped else ''}"
        f"{' [missing→0]' if row.missing_statement else ''}"
        for row in ytd.rows
    )
    journal_lines = "\n".join(
        f"- {line.line}. {line.gl_code} {line.gl_name}: "
        f"Dr {format_dollars(line.debit)} / Cr {format_dollars(line.credit)}"
        f"{'  ← balancing' if line.is_balancing else ''}"
        for line in journal.lines
    )
    return f"""# Month-end run summary (synthetic demo)

Transfers pass did **not** update balances.

## Transfers to record

{transfer_lines or '- (none)'}

Ordinary (non-transfer) activity skipped: {transfers.skipped_ordinary}

## YTD paste column (row-aligned)

{ytd_lines}

YTD flags: {', '.join(ytd.flags) if ytd.flags else 'none'}

## Sign-flip rule

{SIGN_FLIP_RULE}

## Journal

Balanced: **{journal.is_balanced}**
Debits {format_dollars(journal.total_debit)} = Credits {format_dollars(journal.total_credit)}
Plug {format_dollars(journal.plug_amount)}

{journal_lines}
"""


def _first_existing(*candidates: Path) -> Path:
    for path in candidates:
        if path.exists():
            return path
    listed = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"None of these fixture files exist: {listed}")
