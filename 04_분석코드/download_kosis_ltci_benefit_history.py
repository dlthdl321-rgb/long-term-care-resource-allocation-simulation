"""KOSIS 대량통계에서 시군구별 장기요양 급여실적 연도별 ZIP을 수집한다."""

from __future__ import annotations

import csv
import hashlib
import re
import urllib.parse
import urllib.request
from pathlib import Path

from project_paths import RAW_DIR

ORG_ID = "350"
TABLE_ID = "DT_35006_N030"
LIST_URL = (
    "https://kosis.kr/statisticsList/mass/mass_list.jsp"
    f"?org_id={ORG_ID}&tbl_id={TABLE_ID}"
)
DOWNLOAD_URL = "https://kosis.kr/file_mass/file_down.jsp"
OUTPUT_DIR = RAW_DIR / "causal_panel" / "kosis_ltci_benefit"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    request = urllib.request.Request(LIST_URL, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(request, timeout=60) as response:
        page = response.read().decode("utf-8", errors="replace")

    entries = re.findall(
        r'name="file_data_\d+"\s+value="(\d+)/(350_DT_35006_N030_Y_(20\d{2}))"',
        page,
    )
    if not entries:
        raise RuntimeError("KOSIS 대량통계 연도별 파일 목록을 찾지 못했습니다.")

    rows: list[dict[str, object]] = []
    for file_no, filename, year in sorted(entries, key=lambda value: value[2]):
        path = OUTPUT_DIR / f"{filename}.zip"
        if not path.exists():
            body = urllib.parse.urlencode(
                {
                    "tbl_id": TABLE_ID,
                    "org_id": ORG_ID,
                    "filename": filename,
                    "file_no": file_no,
                    "file_type": "ONE",
                    "vw_cd": "",
                    "list_id": "",
                    "usrId": "null",
                    "usrName": "null",
                    "down_cnt": "1",
                    "use_no": "0",
                    "page": "kosis",
                }
            ).encode("ascii")
            download_request = urllib.request.Request(
                DOWNLOAD_URL,
                data=body,
                headers={"Referer": LIST_URL, "User-Agent": "Mozilla/5.0"},
                method="POST",
            )
            with opener.open(download_request, timeout=120) as response:
                payload = response.read()
            if not payload.startswith(b"PK") or len(payload) < 1_000:
                raise RuntimeError(f"{year}: ZIP 응답이 아닙니다.")
            path.write_bytes(payload)

        rows.append(
            {
                "year": year,
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "table_id": TABLE_ID,
                "title": "시군구별 등급별 급여종류별 장기요양 급여실적",
                "source_url": LIST_URL,
            }
        )
        print(f"OK {year} {path.stat().st_size:,} bytes")

    with (OUTPUT_DIR / "manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"files={len(rows)} period={rows[0]['year']}..{rows[-1]['year']}")


if __name__ == "__main__":
    main()
