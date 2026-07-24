"""공공데이터포털의 장기요양 등급판정 과거 주기성 CSV를 수집한다."""

from __future__ import annotations

import csv
import hashlib
import html
import re
import urllib.parse
import urllib.request
from pathlib import Path

from project_paths import RAW_DIR

PUBLIC_DATA_PK = "3051421"
PUBLIC_DATA_DETAIL_PK = "uddi:7b2c3381-2bce-421a-8ae6-e83f77d824ee"
LANDING_URL = f"https://www.data.go.kr/data/{PUBLIC_DATA_PK}/fileData.do"
HISTORY_URL = "https://www.data.go.kr/tcs/dss/selectHistAndCsvData.do"
DETAIL_URL = "https://www.data.go.kr/tcs/dss/selectDpkDetailInfo.do"
FILE_URL = "https://www.data.go.kr/cmm/cmm/fileDownload.do"
OUTPUT_DIR = RAW_DIR / "monthly_panel" / "ltci_grade_decisions"


def fetch(opener: urllib.request.OpenerDirector, url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Referer": LANDING_URL,
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with opener.open(request, timeout=120) as response:
        return response.read()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    fetch(opener, LANDING_URL)

    history_query = urllib.parse.urlencode(
        {
            "publicDataPk": PUBLIC_DATA_PK,
            "publicDataDetailPk": PUBLIC_DATA_DETAIL_PK,
        }
    )
    history = fetch(opener, f"{HISTORY_URL}?{history_query}").decode("utf-8", errors="replace")
    entry_pattern = re.compile(
        r'title="[^"]*_(20\d{6})"[^>]*onclick="fileDetailObj\.fn_fileDataDetail'
        r"\('([^']+)',\s*'[^']+'\)",
        re.IGNORECASE,
    )
    entries = {
        date: html.unescape(detail_pk)
        for date, detail_pk in entry_pattern.findall(history)
        if "20160101" <= date <= "20251231"
    }
    if not entries:
        raise RuntimeError("과거파일 목록을 찾지 못했습니다.")

    rows: list[dict[str, object]] = []
    download_pattern = re.compile(
        r"fn_fileDataDown\('[^']+',\s*'[^']+',\s*'(FILE_[^']+)',\s*'(\d+)',\s*'csv'\)",
        re.IGNORECASE,
    )
    for date, detail_pk in sorted(entries.items()):
        path = OUTPUT_DIR / f"ltci_grade_decisions_{date}.csv"
        file_id = ""
        file_sn = ""
        if not path.exists():
            detail_query = urllib.parse.urlencode({"publicDataDetailPk": detail_pk})
            detail = fetch(opener, f"{DETAIL_URL}?{detail_query}").decode("utf-8", errors="replace")
            match = download_pattern.search(detail)
            if not match:
                raise RuntimeError(f"{date}: CSV 첨부파일 정보를 찾지 못했습니다.")
            file_id, file_sn = match.groups()
            file_query = urllib.parse.urlencode(
                {
                    "atchFileId": file_id,
                    "fileDetailSn": file_sn,
                    "insertDataPrcus": "N",
                }
            )
            payload = fetch(opener, f"{FILE_URL}?{file_query}")
            if len(payload) < 1_000 or payload.lstrip().startswith(b"<"):
                raise RuntimeError(f"{date}: 다운로드 파일이 CSV가 아닙니다.")
            path.write_bytes(payload)

        rows.append(
            {
                "reference_date": date,
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "public_data_detail_pk": detail_pk,
                "attachment_file_id": file_id,
                "attachment_file_sn": file_sn,
                "landing_url": LANDING_URL,
            }
        )
        print(f"OK {date} {path.stat().st_size:,} bytes")

    with (OUTPUT_DIR / "manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"files={len(rows)} period={rows[0]['reference_date']}..{rows[-1]['reference_date']}")


if __name__ == "__main__":
    main()
