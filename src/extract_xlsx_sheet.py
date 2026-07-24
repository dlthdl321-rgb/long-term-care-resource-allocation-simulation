#!/usr/bin/env python3
"""Extract one XLSX worksheet to UTF-8 CSV using only the Python standard library."""

from __future__ import annotations

import argparse
import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def column_number(cell_reference: str) -> int:
    letters = re.match(r"[A-Z]+", cell_reference)
    if not letters:
        return 1
    number = 0
    for letter in letters.group(0):
        number = number * 26 + ord(letter) - ord("A") + 1
    return number


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    path = "xl/sharedStrings.xml"
    if path not in archive.namelist():
        return []
    root = ET.fromstring(archive.read(path))
    return [
        "".join(text.text or "" for text in item.iter(f"{{{MAIN_NS}}}t"))
        for item in root.findall(f"{{{MAIN_NS}}}si")
    ]


def sheet_path(archive: zipfile.ZipFile, requested_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationship_id = None
    for sheet in workbook.findall(f".//{{{MAIN_NS}}}sheet"):
        if sheet.get("name") == requested_name:
            relationship_id = sheet.get(f"{{{REL_NS}}}id")
            break
    if not relationship_id:
        raise SystemExit(f"Worksheet not found: {requested_name}")

    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relationship in relationships.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if relationship.get("Id") == relationship_id:
            target = relationship.get("Target", "")
            return target.lstrip("/") if target.startswith("/xl/") else f"xl/{target.lstrip('/')}"
    raise SystemExit(f"Worksheet relationship not found: {requested_name}")


def extract(input_path: Path, sheet_name: str, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    with zipfile.ZipFile(input_path) as archive:
        strings = shared_strings(archive)
        worksheet = sheet_path(archive, sheet_name)
        with archive.open(worksheet) as source, output_path.open(
            "w", encoding="utf-8-sig", newline=""
        ) as destination:
            writer = csv.writer(destination)
            for event, element in ET.iterparse(source, events=("end",)):
                if element.tag != f"{{{MAIN_NS}}}row":
                    continue
                cells: dict[int, str] = {}
                for cell in element.findall(f"{{{MAIN_NS}}}c"):
                    position = column_number(cell.get("r", "A1"))
                    cell_type = cell.get("t", "")
                    if cell_type == "inlineStr":
                        value = "".join(
                            text.text or "" for text in cell.iter(f"{{{MAIN_NS}}}t")
                        )
                    else:
                        value_element = cell.find(f"{{{MAIN_NS}}}v")
                        value = value_element.text if value_element is not None else ""
                        if cell_type == "s" and value:
                            value = strings[int(value)]
                        elif cell_type == "b":
                            value = "TRUE" if value == "1" else "FALSE"
                    cells[position] = value
                if cells:
                    writer.writerow([cells.get(index, "") for index in range(1, max(cells) + 1)])
                    row_count += 1
                element.clear()
    return row_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--sheet", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    count = extract(args.input, args.sheet, args.output)
    print(f"rows={count} output={args.output}")


if __name__ == "__main__":
    main()
