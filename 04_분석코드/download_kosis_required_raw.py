"""Download the KOSIS source tables required for the LTC resource study.

The API key is read only from ``KOSIS_API_KEY``. It is never written to disk
or included in the manifest. Each annual API response is retained unchanged.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from project_paths import RAW_DIR

API_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
OUTPUT_ROOT = RAW_DIR / "causal_panel" / "kosis_openapi"


@dataclass(frozen=True)
class Table:
    org_id: str
    table_id: str
    title: str
    start_year: int
    end_year: int


TABLES = [
    Table("350", "DT_35006_N021", "시군구별 급여종류별 장기요양기관 현황", 2010, 2024),
    Table("350", "DT_35006_N022", "시군구별 장기요양기관 인력 현황", 2010, 2024),
    Table("350", "TX_35003_A027", "수도권·강원 관내 입원", 2006, 2024),
    Table("350", "TX_35003_A030", "수도권·강원 관외 입원", 2006, 2024),
    Table("350", "TX_35003_A056", "충청권 관내 입원", 2006, 2024),
    Table("350", "TX_35003_A059", "충청권 관외 입원", 2006, 2024),
    Table("350", "TX_35003_A085", "호남·제주 관내 입원", 2006, 2024),
    Table("350", "TX_35003_A088", "호남·제주 관외 입원", 2006, 2024),
    Table("350", "TX_35003_A114", "영남권 관내 입원", 2006, 2024),
    Table("350", "TX_35003_A117", "영남권 관외 입원", 2006, 2024),
    Table("177", "DT_117075_HEALTH_EQ_5D", "시군구별 삶의 질 지수(EQ-5D)", 2008, 2019),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def request_payload(api_key: str, table: Table, year: int, object_levels: int) -> bytes:
    params = {
        "method": "getList",
        "apiKey": api_key,
        "itmId": "ALL",
        "format": "json",
        "jsonVD": "Y",
        "prdSe": "Y",
        "startPrdDe": str(year),
        "endPrdDe": str(year),
        "orgId": table.org_id,
        "tblId": table.table_id,
    }
    for level in range(1, 9):
        params[f"objL{level}"] = "ALL" if level <= object_levels else ""
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "ltc-research/1.0"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def validate(payload: bytes) -> tuple[int, list[str]]:
    decoded = json.loads(payload.decode("utf-8-sig"))
    if isinstance(decoded, dict) and "err" in decoded:
        raise ValueError(f"KOSIS error {decoded.get('err')}: {decoded.get('errMsg')}")
    if not isinstance(decoded, list) or not decoded:
        raise ValueError("KOSIS response is not a non-empty record list")
    columns = sorted({key for row in decoded if isinstance(row, dict) for key in row})
    return len(decoded), columns


def download_table(api_key: str, table: Table) -> list[dict[str, object]]:
    table_dir = OUTPUT_ROOT / table.table_id
    table_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    object_levels: int | None = None

    for year in range(table.start_year, table.end_year + 1):
        path = table_dir / f"{table.table_id}_{year}.json"
        if path.exists():
            payload = path.read_bytes()
            record_count, columns = validate(payload)
        else:
            errors: list[str] = []
            candidate_levels = [object_levels] if object_levels else [1, 2, 3, 4]
            for levels in candidate_levels:
                assert levels is not None
                try:
                    payload = request_payload(api_key, table, year, levels)
                    record_count, columns = validate(payload)
                    object_levels = levels
                    break
                except (ValueError, urllib.error.URLError) as exc:
                    errors.append(f"objL1..{levels}: {exc}")
            else:
                raise RuntimeError(
                    f"{table.table_id} {year} failed: {'; '.join(errors)}"
                )
            path.write_bytes(payload)
            time.sleep(0.15)

        rows.append(
            {
                "org_id": table.org_id,
                "table_id": table.table_id,
                "title": table.title,
                "year": year,
                "file": path.relative_to(OUTPUT_ROOT).as_posix(),
                "records": record_count,
                "columns": "|".join(columns),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "source_url": (
                    "https://kosis.kr/statHtml/statHtml.do"
                    f"?orgId={table.org_id}&tblId={table.table_id}"
                ),
            }
        )
        print(f"OK {table.table_id} {year}: {record_count:,} records")
    return rows


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    api_key = os.environ.get("KOSIS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set KOSIS_API_KEY before running this script.")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for table in TABLES:
        try:
            manifest_rows.extend(download_table(api_key, table))
        except Exception as exc:  # continue so one unavailable table does not lose others
            failures.append({"table_id": table.table_id, "error": str(exc)})
            print(f"FAILED {table.table_id}: {exc}")

    if manifest_rows:
        manifest_path = OUTPUT_ROOT / "manifest.csv"
        with manifest_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
            writer.writeheader()
            writer.writerows(manifest_rows)
    (OUTPUT_ROOT / "collection_summary.json").write_text(
        json.dumps(
            {
                "tables_requested": len(TABLES),
                "tables_collected": len({row["table_id"] for row in manifest_rows}),
                "files_collected": len(manifest_rows),
                "failures": failures,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if failures:
        raise SystemExit(f"Collection completed with {len(failures)} failed table(s).")


if __name__ == "__main__":
    main()
