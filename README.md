# Brokerage Statement Bot

Updates the books from a month-end brokerage statement: finds the money that moved in and out, lines up new balances with the ledger, and writes a balanced journal.

This is a rebuild of a month-end workflow I run at work, on fake data so it can be public. At work an LLM reads the PDF statements. This demo starts from the extracted numbers so it runs offline.

## Run it (30 seconds)

```bash
git clone https://github.com/miles5g/brokerage-statement-bot.git
cd brokerage-statement-bot
python3 -m brokerage_bot
```

Python 3.10+. Nothing to install. On Windows use `py -m brokerage_bot`.

Want each step explained as it runs? `python3 -m brokerage_bot --walkthrough` (press Enter between steps, or use `python3 -m brokerage_bot --walkthrough --no-pause`).

## What happens

1. **Transfers.** Lists wires, contributions, distributions, and transfers between entities. Anything large, ambiguous, or missing a counterparty gets flagged for review. Dividends and trades are not transfers, so they are skipped.
2. **Balance map.** Lines up each statement balance with the matching ledger account, in ledger order, so the column can be pasted straight in. Blank balances become 0. Income accounts flip sign to match how the books store them.
3. **Journal.** New balance minus old balance becomes a debit or credit. Each entity balances on its own. Any change the statement does not explain goes to a Suspense line for that entity, which the reviewer clears against the transfers list.

## What you get

```
Transfers: 10 to record (5 review flags); 10 ordinary lines skipped.
YTD map: 13 rows, 1:1 paste column; sign-flip on 5 income/gain rows; missing->0 on 1.
Journal: 11 lines; Dr $165,000 = Cr $165,000; in suspense $151,000.
```

Files land in `output/`: `transfers.csv`, `ytd_paste_column.txt`, `journal.csv`, `run_summary.md`.

## Tests

```bash
python3 -m unittest discover -s tests
```

Covers transfer detection, row order, sign flips, per-entity balance, and a check that no real names are in the repo.

## Data

All fake: comic book names, masked account numbers, round dollar amounts, a made-up chart of accounts.
