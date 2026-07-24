"""행정안전부 주민등록 연령별 인구 원본 CSV를 3개월 단위로 수집한다.

공식 사이트는 월간 조회 시 한 번에 최대 3개월을 허용한다. 이 스크립트는
전국 시군구, 1세별 인구를 분기 묶음으로 내려받고 SHA-256 검산표를 만든다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from project_paths import RAW_DIR

BASE_URL = "https://jumin.mois.go.kr"
LANDING_URL = f"{BASE_URL}/ageStatMonth.do"
DOWNLOAD_URL = f"{BASE_URL}/downloadCsvAge.do?searchYearMonth=month&xlsStats=2"


@dataclass(frozen=True)
class Quarter:
    year: int
    start_month: int
    end_month: int

    @property
    def stem(self) -> str:
        return f"mois_age_population_sigungu_{self.year}{self.start_month:02d}_{self.year}{self.end_month:02d}"


def quarters(start_year: int, end_year: int) -> list[Quarter]:
    return [
        Quarter(year, start_month, start_month + 2)
        for year in range(start_year, end_year + 1)
        for start_month in (1, 4, 7, 10)
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def request_csv(opener: urllib.request.OpenerDirector, quarter: Quarter) -> tuple[bytes, str]:
    form = {
        "sltOrgType": "1",
        "sltOrgLvl1": "A",
        "sltOrgLvl2": "",
        "gender": "gender",
        "sum": "sum",
        "sltUndefType": "",
        "searchYearStart": str(quarter.year),
        "searchMonthStart": f"{quarter.start_month:02d}",
        "searchYearEnd": str(quarter.year),
        "searchMonthEnd": f"{quarter.end_month:02d}",
        "sltOrderType": "1",
        "sltOrderValue": "ASC",
        "sltArgTypes": "1",
        "sltArgTypeA": "0",
        "sltArgTypeB": "100",
        "category": "month",
        "state": "2",
    }
    request = urllib.request.Request(
        DOWNLOAD_URL,
        data=urllib.parse.urlencode(form).encode("ascii"),
        headers={"Referer": LANDING_URL, "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with opener.open(request, timeout=120) as response:
        payload = response.read()
        content_type = response.headers.get("Content-Type", "")
        disposition = response.headers.get("Content-Disposition", "")
    if "application/octet-stream" not in content_type or len(payload) < 1_000:
        raise RuntimeError(
            f"{quarter.stem}: CSV 응답이 아님(content-type={content_type}, bytes={len(payload)})"
        )
    return payload, disposition


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RAW_DIR / "monthly_panel" / "mois_age_population",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.start_year < 2008 or args.end_year < args.start_year:
        raise ValueError("연도 범위는 2008년 이후이며 시작연도는 종료연도보다 늦을 수 없습니다.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    opener.open(
        urllib.request.Request(LANDING_URL, headers={"User-Agent": "Mozilla/5.0"}),
        timeout=60,
    ).close()

    manifest_rows: list[dict[str, object]] = []
    for quarter in quarters(args.start_year, args.end_year):
        path = args.output_dir / f"{quarter.stem}.csv"
        disposition = ""
        if args.overwrite or not path.exists():
            payload, disposition = request_csv(opener, quarter)
            path.write_bytes(payload)
        else:
            payload = path.read_bytes()

        # 원본은 CP949 CSV이며 첫 행에 기준월 표기가 있어 기본 구조를 검산한다.
        first_line = payload.splitlines()[0].decode("cp949", errors="replace")
        expected_start = f"{quarter.year}년{quarter.start_month:02d}월"
        if expected_start not in first_line:
            raise RuntimeError(f"{path.name}: 예상 시작월({expected_start})이 첫 행에 없음")

        manifest_rows.append(
            {
                "file": path.name,
                "period_start": f"{quarter.year}-{quarter.start_month:02d}",
                "period_end": f"{quarter.year}-{quarter.end_month:02d}",
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "source_url": DOWNLOAD_URL,
                "content_disposition": re.sub(r"[\r\n]+", " ", disposition),
            }
        )
        print(f"OK {path.name} ({path.stat().st_size:,} bytes)")

    manifest = args.output_dir / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)

    metadata = args.output_dir / "collection_metadata.txt"
    metadata.write_text(
        "\n".join(
            [
                "dataset=행정안전부 주민등록 연령별 인구현황",
                "geography=전국 시군구",
                "frequency=월간 (원본 파일은 3개월 묶음)",
                f"period={args.start_year}-01..{args.end_year}-12",
                "age_detail=1세별, 0세..100세 이상",
                "sex_detail=계/남/여",
                f"landing_url={LANDING_URL}",
                f"download_endpoint={DOWNLOAD_URL}",
                f"collected_utc={datetime.now(timezone.utc).isoformat()}",
                "encoding=CP949",
                "license=공공누리/공식 사이트 이용조건 확인",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"manifest={manifest}")


if __name__ == "__main__":
    main()
