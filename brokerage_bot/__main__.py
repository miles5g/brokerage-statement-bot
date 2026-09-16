"""Entry point for ``python3 -m brokerage_bot``."""

from __future__ import annotations

import sys

from brokerage_bot.cli import main

if __name__ == "__main__":
    sys.exit(main())
