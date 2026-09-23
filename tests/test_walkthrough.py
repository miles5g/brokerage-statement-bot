"""Walkthrough boxes: banners, pause control, CI --no-pause."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brokerage_bot.cli import build_parser, main
from brokerage_bot.walkthrough import (
    JOURNAL,
    PIPELINE_STAGES,
    SYNTHETIC,
    TRANSFERS,
    YTD_MAP,
    render_box,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
README = Path(__file__).resolve().parents[1] / "README.md"


class WalkthroughBannerTests(unittest.TestCase):
    def test_banners_are_two_to_four_lines_plus_stage_summary(self):
        for banner in (SYNTHETIC, TRANSFERS, YTD_MAP, JOURNAL):
            with self.subTest(title=banner.title):
                self.assertGreaterEqual(len(banner.lines), 2)
                self.assertLessEqual(len(banner.lines), 4)
                box = render_box(banner)
                self.assertTrue(box.startswith("+"))
                self.assertIn(banner.title, box)
                self.assertIn(banner.summary, box)
                self.assertEqual(box.count(banner.summary), 1)
                self.assertNotIn("Say this", box)
                self.assertNotIn("INTERVIEW", box)

    def test_pipeline_stage_order(self):
        self.assertEqual(
            [key for key, _ in PIPELINE_STAGES],
            ["transfers", "ytd", "journal"],
        )

    def test_copy_sounds_like_miles_not_a_deck(self):
        blobs = [
            " ".join((banner.title, *banner.lines, banner.summary))
            for banner in (SYNTHETIC, TRANSFERS, YTD_MAP, JOURNAL)
        ]
        text = "\n".join(blobs)
        lowered = text.lower()
        for phrase in (
            "archaeology",
            "vanity motion",
            "shapes are boring",
            "hottest work",
            "controller-style",
            "deterministic rules you can defend",
            "workpaper",
            "posting",
            "posted",
            "i keep the control file",
            "i am isolating",
            "say this",
            "interview",
            "talk track",
            "talk through",
        ):
            self.assertNotIn(phrase, lowered, phrase)
        self.assertEqual(
            SYNTHETIC.summary,
            "Fake data first. Then transfers, the YTD map, and the journal.",
        )
        self.assertIn("All fake names and dollars — nothing from a real client.", SYNTHETIC.lines)
        self.assertEqual(
            TRANSFERS.summary,
            "I flag money in and out. Dividends and trades stay off the list.",
        )
        self.assertIn("original list", text)
        self.assertIn("I don't guess", text)
        self.assertEqual(
            YTD_MAP.summary,
            "I keep statement numbers in the original row order. Blanks become 0.",
        )
        self.assertEqual(
            JOURNAL.summary,
            "I write the difference as debit or credit and plug so both sides match.",
        )
        self.assertIn("I'm", text)


class WalkthroughCliTests(unittest.TestCase):
    def test_parser_accepts_short_and_long_walkthrough_and_no_pause(self):
        args = build_parser().parse_args(["-w", "--no-pause"])
        self.assertTrue(args.walkthrough)
        self.assertTrue(args.no_pause)
        default = build_parser().parse_args([])
        self.assertFalse(default.walkthrough)
        self.assertFalse(default.no_pause)
        help_text = build_parser().format_help()
        self.assertNotIn("Interview", help_text)
        self.assertIn("explaining what it does", help_text)

    def test_walkthrough_no_pause_renders_banners_and_exits_zero(self):
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.stdout", buf):
                code = main(
                    [
                        "--walkthrough",
                        "--no-pause",
                        "--fixtures",
                        str(FIXTURES),
                        "--output",
                        str(tmp),
                    ]
                )
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("SYNTHETIC DATA — DEMO", out)
        self.assertIn("TRANSFERS", out)
        self.assertIn("YTD MAP", out)
        self.assertIn("JOURNAL", out)
        self.assertIn("Fake data first.", out)
        self.assertNotIn("Say this", out)
        self.assertNotIn("INTERVIEW", out)
        self.assertIn("Transfers:", out)
        self.assertIn("YTD map:", out)
        self.assertIn("Journal:", out)
        self.assertNotIn("Press Enter", out)
        self.assertGreaterEqual(out.count("+--"), 4)

    def test_walkthrough_short_flag_no_pause_exits_zero(self):
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.stdout", buf):
                code = main(
                    ["-w", "--no-pause", "--fixtures", str(FIXTURES), "--output", str(tmp)]
                )
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("Fake data first.", out)
        self.assertNotIn("Say this", out)

    def test_default_mode_skips_banners_and_does_not_pause(self):
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.stdout", buf):
                with patch("builtins.input", side_effect=AssertionError("paused")):
                    code = main(["--fixtures", str(FIXTURES), "--output", str(tmp)])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("SYNTHETIC DATA ONLY", out)
        self.assertNotIn("Say this", out)
        self.assertNotIn("Fake data first.", out)
        self.assertNotIn("Press Enter", out)

    def test_walkthrough_pauses_for_enter_after_each_box(self):
        prompts: list[str] = []

        def fake_input(prompt: str = "") -> str:
            prompts.append(prompt)
            return ""

        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with patch("sys.stdout", buf):
                with patch("builtins.input", fake_input):
                    code = main(
                        [
                            "--walkthrough",
                            "--fixtures",
                            str(FIXTURES),
                            "--output",
                            str(tmp),
                        ]
                    )
        self.assertEqual(code, 0)
        self.assertEqual(prompts, ["Press Enter to continue..."] * 4)
        out = buf.getvalue()
        self.assertIn("Fake data first.", out)
        self.assertNotIn("Say this", out)

    def test_readme_documents_walkthrough_command(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("python3 -m brokerage_bot --walkthrough", text)
        self.assertIn("--no-pause", text)
        self.assertIn("python3 -m brokerage_bot --walkthrough --no-pause", text)
        lowered = text.lower()
        for phrase in ("say this", "interview", "talk through", "talk track"):
            self.assertNotIn(phrase, lowered, phrase)


if __name__ == "__main__":
    unittest.main()
