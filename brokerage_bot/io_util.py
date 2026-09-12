"""Load and write CSV / JSON / XLSX tables without third-party packages."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from brokerage_bot.xlsx_lite import read_xlsx, write_xlsx


def load_tabular(path: Path | str) -> list[dict[str, str]]:
    """Load a list of row dicts from .csv, .json, or .xlsx."""
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(src)
    suffix = src.suffix.lower()
    if suffix == ".csv":
        return _load_csv(src)
    if suffix == ".json":
        return _load_json_rows(src)
    if suffix == ".xlsx":
        return _load_xlsx(src)
    raise ValueError(f"Unsupported table format: {src.suffix}")


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            {k: (v if v is not None else "") for k, v in row.items()}
            for row in csv.DictReader(handle)
        ]


def _load_json_rows(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for key in ("activities", "rows", "ledger", "items"):
            if key in payload and isinstance(payload[key], list):
                rows = payload[key]
                break
        else:
            raise ValueError(f"{path} JSON must be a list or contain activities/rows")
    else:
        raise ValueError(f"{path} JSON must be a list or object")
    return [{str(k): "" if v is None else str(v) for k, v in row.items()} for row in rows]


def _load_xlsx(path: Path) -> list[dict[str, str]]:
    table = read_xlsx(path)
    if not table:
        return []
    headers = [str(cell).strip() for cell in table[0]]
    rows: list[dict[str, str]] = []
    for raw in table[1:]:
        if all(str(cell).strip() == "" for cell in raw):
            continue
        row = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            row[header] = raw[idx] if idx < len(raw) else ""
        rows.append(row)
    return rows


def write_csv(path: Path | str, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
    return dest


def write_json(path: Path | str, payload: Any) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return dest


def write_xlsx_table(
    path: Path | str,
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Sequence[str],
    *,
    sheet_name: str = "ledger",
) -> Path:
    table: list[list[object]] = [list(fieldnames)]
    for row in rows:
        table.append([row.get(name, "") for name in fieldnames])
    return write_xlsx(path, table, sheet_name=sheet_name)


def write_lines(path: Path | str, values: Iterable[Any]) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(str(v) for v in values) + "\n", encoding="utf-8")
    return dest
