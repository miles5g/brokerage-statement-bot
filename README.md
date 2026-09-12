# Brokerage Statement Bot

**30-second demo**

```bash
python -m brokerage_bot
python -m unittest discover -s tests -v
```

Writes transfer review, YTD paste column, and a balanced journal into `output/`. Stdlib Python only.

---

**Portfolio demo** — three-pass month-end pattern: transfers → YTD map → journal.

**Not** production software and **not** affiliated with any employer, broker, or fund admin. Pattern only — no firm SOP text.

## What it does

1. **Transfers pass** — flag wires, contributions/distributions, security transfers, margin paydowns (not ordinary dividends/interest/market moves)
2. **YTD map pass** — map statement/YTD values 1:1 to GL row order; missing → 0; demo 3000-series sign-flip
3. **Journal pass** — difference → Debit/Credit with balancing plug

## Synthetic-data rules

- People/entities: Bruce Wayne, Peter Parker, Wayne Family Trust, Parker Holdings LLC
- Accounts: masked `****1234` style
- Amounts: whole dollars only
- GLs: dummy catalog (`1200` Cash, `1210` Equities, `3100`/`3200`/`3300` income, `9999` plug)

## Quickstart

```bash
git clone https://github.com/miles5g/brokerage-statement-bot.git
cd brokerage-statement-bot
python -m brokerage_bot
```

Artifacts: `output/transfers.csv`, `ytd_paste_column.txt`, `journal.csv`, `run_summary.md`.

## Status

Runnable. Tests cover transfer detection, row-order mapping, journal balance, and scrub guards.

## Author

Miles Johnson — [@miles5g](https://github.com/miles5g)
