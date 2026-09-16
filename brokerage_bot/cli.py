"""One-command CLI for the three-pass demo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from brokerage_bot import __version__
from brokerage_bot.amounts import format_dollars
from brokerage_bot.pipeline import DEFAULT_FIXTURES, DEFAULT_OUTPUT, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m brokerage_bot",
        description=(
            "Synthetic brokerage statement updater (portfolio demo). "
            "Runs transfers → YTD map → journal. Does not post to a real ledger."
        ),
    )
    parser.add_argument(
        "pass_name",
        nargs="?",
        default="all",
        choices=("all", "transfers", "ytd", "journal"),
        help="Which pass to run. 'all' (default) writes every artifact.",
    )
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="Fixture directory")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output directory")
    parser.add_argument("--activity", default=None, help="Override statement activity file")
    parser.add_argument("--ledger", default=None, help="Override GL workbook/CSV")
    parser.add_argument("--statement-ytd", default=None, help="Override statement YTD file")
    parser.add_argument("--version", action="version", version=f"brokerage_bot {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_pipeline(
        fixtures_dir=args.fixtures,
        output_dir=args.output,
        activity_path=args.activity,
        ledger_path=args.ledger,
        statement_ytd_path=args.statement_ytd,
    )
    # Individual pass names still run the full pipeline so journal always
    # has a mapped difference column; we just highlight that pass in stdout.
    _print_report(args.pass_name, result)
    return 0


def _print_report(pass_name: str, result) -> None:
    print("brokerage_bot — portfolio demo — SYNTHETIC DATA ONLY")
    print("Transfers pass does not update balances.")
    if pass_name in {"all", "transfers"}:
        review = sum(1 for line in result.transfers.lines if line.record_action == "REVIEW")
        print(
            f"Transfers: {len(result.transfers.lines)} to record "
            f"({review} review flags); "
            f"{result.transfers.skipped_ordinary} ordinary lines skipped."
        )
    if pass_name in {"all", "ytd"}:
        flipped = sum(1 for row in result.ytd.rows if row.sign_flipped)
        missing = sum(1 for row in result.ytd.rows if row.missing_statement)
        print(
            f"YTD map: {len(result.ytd.rows)} rows, 1:1 paste column; "
            f"sign-flip on {flipped} income/gain rows; missing→0 on {missing}."
        )
    if pass_name in {"all", "journal"}:
        print(
            f"Journal: {len(result.journal.lines)} lines; "
            f"Dr {format_dollars(result.journal.total_debit)} = "
            f"Cr {format_dollars(result.journal.total_credit)}; "
            f"plug {format_dollars(result.journal.plug_amount)}."
        )
    print("Wrote:")
    for path in result.written:
        print(f"  {Path(path)}")


if __name__ == "__main__":
    sys.exit(main())
