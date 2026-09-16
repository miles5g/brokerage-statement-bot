"""Interview walkthrough boxes for the three-pass demo.

Fake-data reminder first. Then a short box before transfers, YTD map,
and journal. Talk-out-loud hints only — no firm SOP dump.
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
        "All fake names and dollars — nothing from a real client.",
        "Bruce Wayne, masked accounts, dummy GLs.",
        "Just a demo. I'm not touching real books.",
    ),
    say_this="All fake names and dollars — nothing from a real client.",
)

TRANSFERS = StageBanner(
    title="TRANSFERS — money in/out",
    lines=(
        "Wires, contributions, distributions, security transfers, paydowns.",
        "Dividends, interest, and trades stay off this list.",
        "I'm not changing balances. This is just the original list.",
    ),
    say_this="Money in/out separate from dividends.",
)

YTD_MAP = StageBanner(
    title="YTD MAP — same order as the original list",
    lines=(
        "Statement numbers line up with the original list, row for row.",
        "Blank cell? That's a 0. I don't guess.",
        "Income/gain rows (the 3000s) flip sign so they match the books.",
    ),
    say_this="Same order as the original list. I don't guess.",
)

JOURNAL = StageBanner(
    title="JOURNAL — this part balances",
    lines=(
        "New number minus old number. That's the debit or credit.",
        "Then a 9999 plug so both sides match.",
        "Debits equal credits. That's it.",
    ),
    say_this="This part balances.",
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
    print(file=out)


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
        print(file=out)
    print("Wrote:", file=out)
    for path in written:
        print(f"  {path}", file=out)
