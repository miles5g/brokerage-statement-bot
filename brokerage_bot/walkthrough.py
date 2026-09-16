"""Interview walkthrough banners for the three-pass demo.

Boxed stage hints only — no employer SOP text. Synthetic data reminder
prints first; then a short box before transfers, YTD map, and journal.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TextIO


@dataclass(frozen=True)
class StageBanner:
    title: str
    lines: tuple[str, ...]
    say_this: str

    def __post_init__(self) -> None:
        if not 2 <= len(self.lines) <= 4:
            raise ValueError(f"{self.title}: expected 2–4 body lines, got {len(self.lines)}")
        if not self.say_this or "\n" in self.say_this:
            raise ValueError(f"{self.title}: say_this must be a single non-empty line")


SYNTHETIC = StageBanner(
    title="SYNTHETIC DATA — INTERVIEW DEMO",
    lines=(
        "Comic-book names, masked accounts (****1234), dummy GLs.",
        "Pattern demo only — it does not post to a real ledger.",
        "Not affiliated with any employer, broker, or fund admin.",
    ),
    say_this="Everything on screen is made-up interview data.",
)

TRANSFERS = StageBanner(
    title="TRANSFERS — review list, not a posting",
    lines=(
        "Wires, contributions/distributions, security transfers, paydowns.",
        "Ordinary dividends, interest, and trades are skipped.",
        "This pass does not update balances.",
    ),
    say_this="I am isolating movements to record, not income.",
)

YTD_MAP = StageBanner(
    title="YTD MAP — 1:1 paste column",
    lines=(
        "Statement/YTD figures line up with GL row order.",
        "Missing cells become 0; 3000-series income/gain rows flip sign.",
    ),
    say_this="The paste column matches the workpaper row for row.",
)

JOURNAL = StageBanner(
    title="JOURNAL — difference to Debit/Credit",
    lines=(
        "Mapped minus prior becomes Dr/Cr lines, then a 9999 plug.",
        "Debits equal credits so the entry would balance if posted.",
    ),
    say_this="The journal is balanced before anything would post.",
)

# Shown between transfers → YTD map → journal (after the synthetic opener).
PIPELINE_STAGES: tuple[tuple[str, StageBanner], ...] = (
    ("transfers", TRANSFERS),
    ("ytd", YTD_MAP),
    ("journal", JOURNAL),
)


def render_box(banner: StageBanner) -> str:
    """Return a 2–4 line boxed banner plus a one-line say-this hint."""
    body = [banner.title, *banner.lines, "", f"Say this: {banner.say_this}"]
    width = max(len(line) for line in body)
    top = "+" + "-" * (width + 2) + "+"
    bottom = top
    rows = ["| " + line.ljust(width) + " |" for line in body]
    return "\n".join([top, *rows, bottom])


def print_banner(
    banner: StageBanner,
    *,
    pause: bool,
    file: TextIO | None = None,
    input_fn: Callable[[str], str] | None = None,
) -> None:
    out = sys.stdout if file is None else file
    print(render_box(banner), file=out, flush=True)
    if pause:
        reader = input_fn if input_fn is not None else input
        reader("Press Enter to continue...")


def emit_walkthrough(
    pass_name: str,
    summaries: dict[str, str],
    written: Sequence[str],
    *,
    pause: bool,
    file: TextIO | None = None,
    input_fn: Callable[[str], str] | None = None,
) -> None:
    """Print the synthetic reminder, then stage boxes around each pass summary."""
    print_banner(SYNTHETIC, pause=pause, file=file, input_fn=input_fn)
    out = sys.stdout if file is None else file
    for key, banner in PIPELINE_STAGES:
        if pass_name not in {"all", key}:
            continue
        print_banner(banner, pause=pause, file=file, input_fn=input_fn)
        print(summaries[key], file=out)
    print("Wrote:", file=out)
    for path in written:
        print(f"  {path}", file=out)
