# Brokerage Statement Bot

Portfolio demo of a **three-pass month-end pattern**: review transfers, paste a statement/YTD column onto dummy GL rows, then format a balanced debit/credit journal.

This is **not production software** and is **not affiliated with any employer, broker, or fund administrator**. It implements the *pattern* only. No firm SOP text is included. All names, entities, accounts, and GL codes are invented.

## What it demonstrates

Month-end books often need three separate motions that people mash together:

1. **Transfers pass** — pull cash/security movements (wires, contributions, distributions, loan/margin paydowns) onto a review list. Do **not** roll these into balances here.
2. **YTD map pass** — given GL rows in a fixed order, return a statement/YTD column mapped **1:1 by row order** (not by fuzzy name match). Missing cells become 0. Income/gain accounts in the demo 3000 series get a documented sign flip.
3. **Journal pass** — take `mapped − prior` and split Debit/Credit. Negatives move to the credit side as a positive amount. A balancing row plugs residual (usually transfer-related) so the entry foots.

One command runs all three against synthetic fixtures.

## Quickstart

Python 3.10+ standard library only. No `pip install`.

```bash
python -m brokerage_bot
python -m unittest discover -s tests -v
```

Artifacts land in `output/`:

| File | Pass |
| --- | --- |
| `transfers.csv` / `transfers.json` | Transfers to record + review flags |
| `ytd_map.csv` / `ytd_paste_column.txt` | Row-aligned statement/YTD paste column |
| `journal.csv` / `journal.json` | Debit/Credit journal with balancing row |
| `run_summary.md` | Human-readable recap |

Optional flags: `--fixtures`, `--output`, `--activity`, `--ledger`, `--statement-ytd`. The optional first argument (`all` / `transfers` / `ytd` / `journal`) only changes what is printed; `all` is the default and always writes every artifact.

## Synthetic-data rules (enforced in code)

- **People:** Bruce Wayne, Peter Parker. **Entities:** Wayne Family Trust, Parker Holdings LLC.
- **Amounts:** round whole dollars only (`$1,000` / `$100,000` / `$1,000,000` style integers). Cents are rejected.
- **Accounts:** masked `****1234` style only. Unmasked digit runs fail the scrub.
- **Emails:** omitted. Only `@example.test` / `@example.com` would be allowed; anything else fails the scrub.
- **GLs:** dummy catalog only (below). Unknown codes are rejected.

## Dummy chart of accounts

| Code | Name | Role in the demo |
| --- | --- | --- |
| 1200 | Brokerage Cash | Asset |
| 1210 | Equities | Asset |
| 1220 | Fixed Income | Asset |
| 1230 | Other Investments | Asset (fixture row is missing statement YTD → 0) |
| 2100 | Margin Loan | Liability |
| 3100 | Dividend Income | 3000-series income (sign-flip) |
| 3200 | Interest Income | 3000-series income (sign-flip) |
| 3300 | Realized Gain/Loss | 3000-series gain (sign-flip) |
| 9999 | Balancing (demo plug) | Journal plug only |

## Sign-flip rule (demo 3000-series)

Brokerage statements typically report dividend, interest, and realized gain as positive “income received.” This demo workpaper uses a **debit-positive** convention: income/gain accounts store credit balances as negative numbers.

For GL codes **3000–3999**:

```
mapped_ytd = -statement_amount
```

Every other dummy GL keeps the statement amount. The substitution **missing → 0** happens first, then the flip.

## Pipeline details

### 1. Transfers pass

Reads `fixtures/statement_activity.csv` (JSON equivalent shipped too).

**Recorded:** wires, ACH, cash transfers, security transfers, contributions, distributions, loan/margin paydowns.

**Skipped:** ordinary dividends, interest, margin interest, buys/sells, unrealized marks, realized gain lines, fees.

Review flags include `LARGE_AMOUNT` (≥ $100,000), `INTER_ENTITY`, `MISSING_COUNTERPARTY`, `AMBIGUOUS_TYPE` (keyword-only “journal”), and `NEEDS_HUMAN_REVIEW`. The report always sets `balances_updated=false`.

### 2. YTD map pass

Reads dummy GL rows (`fixtures/gl_workbook.xlsx` or `fixtures/gl_ledger.csv`) plus a positional statement YTD list (`fixtures/statement_ytd.csv`, or a `statement_ytd` column on the workbook).

Alignment is **row order**, not GL code. That is intentional: the paste column is meant to drop next to an existing workpaper without re-sorting.

Inconsistencies flagged: row-count mismatch, missing statement values, extra statement rows dropped, income sign that is still positive after the flip, 3000-series prior balances that are not credits.

### 3. Journal pass

`difference = statement_ytd_mapped − prior_ledger`

- difference `> 0` → Debit that amount
- difference `< 0` → Credit the absolute value
- difference `= 0` → omitted from the entry

If debits ≠ credits, a **9999 Balancing (demo plug)** row is added. A large plug is expected in this fixture set: pass 1 did not book the wires/contributions into income. The plug is a review signal, not an auto-post.

## Fixtures (August 2026, fictional)

- `fixtures/statement_activity.csv` and `.json` — Wayne Family Trust `****1234` and Parker Holdings LLC `****5678`
- `fixtures/gl_ledger.csv` / `fixtures/gl_workbook.xlsx` — prior ledger + optional raw statement column
- `fixtures/statement_ytd.csv` — same row order as the ledger

Securities (Gotham Utilities, Gotham Steel, Metropolis REIT, Daily Planet Inc, Bugle Bond Fund) are fictional.

## Tests

```bash
python -m unittest discover -s tests -v
```

Coverage: transfer detection vs ordinary activity, row-aligned mapping + sign-flip + missing→0, journal balance and credit-side sign, scrub guards (email / unmasked account / cents / non-dummy GL), and a full fixture pipeline.

## What this is not

- Not a broker integration, OCR engine, or general ledger product.
- Not advice, and not a substitute for a close checklist.
- Not a copy of any employer playbook — only the transferable three-pass shape.

## License

MIT. Synthetic demo data. Use it to show the pattern, not to process real statements.
