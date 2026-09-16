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
            "python3 -m brokerage_bot",
            "python3 -m unittest discover -s tests -v",
        ])
        self.assertNotRegex(text, r"(?m)^python -m ")


if __name__ == "__main__":
    unittest.main()
