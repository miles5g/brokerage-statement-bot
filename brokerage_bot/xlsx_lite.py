"""Minimal XLSX read/write using only the standard library.

Enough for a single-sheet (or first-sheet) workpaper of strings and integers.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_REL_OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _col_letter(index: int) -> str:
    letters = []
    n = index + 1
    while n:
        n, rem = divmod(n - 1, 26)
        letters.append(chr(65 + rem))
    return "".join(reversed(letters))


def _col_index(letter: str) -> int:
    n = 0
    for char in letter:
        n = n * 26 + (ord(char.upper()) - 64)
    return n - 1


_CELL_REF = re.compile(r"^([A-Z]+)(\d+)$")


def write_xlsx(
    path: Path | str,
    rows: list[list[object]],
    *,
    sheet_name: str = "ledger",
) -> Path:
    """Write a simple first-sheet workbook. Integers stay numeric; other cells are text."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    sheet_xml = _sheet_xml(rows)
    workbook_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="{NS}" xmlns:r="{NS_REL_OFFICE}">
  <sheets>
    <sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    rels_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{NS_REL}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    workbook_rels = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{NS_REL}">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
"""
    content_types = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="{NS_CT}">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
"""
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return dest


def _sheet_xml(rows: list[list[object]]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<worksheet xmlns="{NS}"><sheetData>',
    ]
    for r_idx, row in enumerate(rows, start=1):
        cells = []
        for c_idx, value in enumerate(row):
            ref = f"{_col_letter(c_idx)}{r_idx}"
            if value is None or value == "":
                continue
            if isinstance(value, int) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                text = escape(str(value), {"'": "&apos;", '"': "&quot;"})
                cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'
                )
        lines.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    lines.append("</sheetData></worksheet>")
    return "\n".join(lines)


def read_xlsx(path: Path | str) -> list[list[str]]:
    """Return the first worksheet as a list of row lists (sparse cells filled as '')."""
    src = Path(path)
    with zipfile.ZipFile(src) as zf:
        sheet_path = _first_sheet_path(zf)
        root = ET.fromstring(zf.read(sheet_path))
        shared = _shared_strings(zf)

    rows: dict[int, dict[int, str]] = {}
    max_col = 0
    for row_el in root.findall(f".//{{{NS}}}row"):
        r_attr = row_el.get("r")
        r_idx = int(r_attr) - 1 if r_attr else len(rows)
        for cell in row_el.findall(f"{{{NS}}}c"):
            ref = cell.get("r") or ""
            match = _CELL_REF.match(ref)
            if match:
                c_idx = _col_index(match.group(1))
                r_idx = int(match.group(2)) - 1
            else:
                c_idx = 0
            value = _cell_value(cell, shared)
            rows.setdefault(r_idx, {})[c_idx] = value
            max_col = max(max_col, c_idx)

    if not rows:
        return []
    last_row = max(rows)
    table: list[list[str]] = []
    for r in range(last_row + 1):
        table.append([rows.get(r, {}).get(c, "") for c in range(max_col + 1)])
    return table


def _first_sheet_path(zf: zipfile.ZipFile) -> str:
    names = zf.namelist()
    for candidate in (
        "xl/worksheets/sheet1.xml",
        "xl/worksheets/sheet.xml",
    ):
        if candidate in names:
            return candidate
    for name in names:
        if name.startswith("xl/worksheets/") and name.endswith(".xml"):
            return name
    raise ValueError(f"{zf.filename} has no worksheet part")


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    name = "xl/sharedStrings.xml"
    if name not in zf.namelist():
        return []
    root = ET.fromstring(zf.read(name))
    out: list[str] = []
    for si in root.findall(f"{{{NS}}}si"):
        texts = [t.text or "" for t in si.findall(f".//{{{NS}}}t")]
        out.append("".join(texts))
    return out


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        texts = [t.text or "" for t in cell.findall(f".//{{{NS}}}t")]
        return "".join(texts)
    value_el = cell.find(f"{{{NS}}}v")
    raw = value_el.text if value_el is not None and value_el.text else ""
    if cell_type == "s" and raw.isdigit():
        idx = int(raw)
        if 0 <= idx < len(shared):
            return shared[idx]
    return raw
