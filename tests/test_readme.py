"""README one-liner must be copy-pasteable (python3, not bare python)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


class ReadmeDemoTests(unittest.TestCase):
    def test_thirty_second_demo_uses_python3(self):
        text = README.read_text(encoding="utf-8")
        match = re.search(r"```bash\n(.*?)```", text, flags=re.DOTALL)
        self.assertIsNotNone(match, "README needs a bash demo fence")
        block = match.group(1)
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        self.assertEqual(lines, [
            "git clone https://github.com/miles5g/brokerage-statement-bot.git",
            "cd brokerage-statement-bot",
            "python3 -m brokerage_bot",
        ])
        self.assertNotRegex(text, r"(?m)^python -m ")
        lowered = text.lower()
        self.assertIn("public rebuild of the workflow pattern", lowered)
        self.assertIn("not deployed or used at any employer", lowered)
        self.assertNotIn("llm", lowered)
        self.assertNotIn("at work", lowered)
        self.assertIn("a person approves or edits", lowered)

    def test_demo_link_is_the_first_line(self):
        text = README.read_text(encoding="utf-8")
        self.assertEqual(
            text.splitlines()[0],
            "**[Open the demo](https://miles5g.github.io/brokerage-statement-bot/)**",
        )


if __name__ == "__main__":
    unittest.main()
