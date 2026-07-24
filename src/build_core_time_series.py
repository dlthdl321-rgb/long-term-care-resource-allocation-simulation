#!/usr/bin/env python3
"""Build comparable year-end demand/population and supply-snapshot tables."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "time_series"
PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "data" / "analysis_ready"


def integer(value: str | None) -> int:
    text = (value or "").replace(",", "").strip()
    return int(text) if re.fullmatch(r"-?\d+", text) else 0


def normalized(text: str) -> str:
    return re.sub(r"[\s()（）]", "", text).replace("등급외(A)", "등급외A")


def read_csv(path: Path, encoding: str = "utf-8-sig"):
    with path.open(encoding=encoding, newline="") as handle:
        yield from csv.DictReader(handle)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_demand() -> list[dict]:
    output = []
    for path in sorted((RAW / "ltci_demand").glob("*.csv")):
        date = re.search(r"(\d{8})", path.stem).group(1)
        groups = defaultdict(lambda: [0, 0, 0, 0])
        for raw_row in read_csv(path, "cp949"):
            row = {normalized(key): (value or "").strip() for key, value in raw_row.items()}
            key = (row["시도"], row["시군구"])
            if row.get("신청자") == "*":
                groups[key][1] += 1
            else:
                groups[key][0] += integer(row.get("신청자"))
            for column in ("1등급", "2등급", "3등급", "4등급", "5등급", "인지지원등급"):
                if row.get(column) == "*":
                    groups[key][3] += 1
                else:
                    groups[key][2] += integer(row.get(column))
        for (sido, sigungu), values in groups.items():
            known_app, hidden_app, known_rec, hidden_rec = values
            output.append(
                {
                    "기준일": f"{date[:4]}-{date[4:6]}-{date[6:]}",
                    "시도": sido,
                    "시군구": sigungu,
                    "신청자_공개값합계": known_app,
                    "신청자_비공개셀수": hidden_app,
                    "신청자_추정하한": known_app + hidden_app,
                    "신청자_추정상한": known_app + 4 * hidden_app,
                    "인정자_공개값합계": known_rec,
                    "인정자_비공개셀수": hidden_rec,
                    "인정자_추정하한": known_rec + hidden_rec,
                    "인정자_추정상한": known_rec + 4 * hidden_rec,
                    "비공개규칙주의": "2022년 파일은 5명 미만 실제 숫자가 보이며 이후 파일과 공개규칙이 다를 수 있음",
                }
            )
    return output


def age_columns(headers: list[str], minimum: int, sex: str) -> list[str]:
    selected = []
    for header in headers:
        if sex not in header:
            continue
        match = re.search(r"(\d+)세", header)
        if match and int(match.group(1)) >= minimum:
            selected.append(header)
    return selected


def build_population() -> list[dict]:
    output = []
    for path in sorted((RAW / "population").glob("*.csv")):
        rows = list(read_csv(path, "cp949"))
        if not rows:
            continue
        headers = list(rows[0])
        columns = {
            age: age_columns(headers, age, "남자") + age_columns(headers, age, "여자")
            for age in (65, 75, 85)
        }
        groups = defaultdict(lambda: [0, 0, 0, 0])
        for row in rows:
            key = (
                row["기준연월"],
                (row["시도명"] or "").strip(),
                (row["시군구명"] or "").strip(),
            )
            groups[key][0] += integer(row.get("계"))
            for index, age in enumerate((65, 75, 85), start=1):
                groups[key][index] += sum(integer(row.get(column)) for column in columns[age])
        for (date, sido, sigungu), values in groups.items():
            output.append(
                {
                    "기준일": date,
                    "시도명": sido,
                    "시군구명": sigungu,
                    "총인구": values[0],
                    "65세이상인구": values[1],
                    "75세이상인구": values[2],
                    "85세이상인구": values[3],
                    "고령화율": round(values[1] / values[0] * 100, 6) if values[0] else "",
                }
            )
    return output


def build_single_households() -> list[dict]:
    output = []
    for path in sorted((RAW / "single_households").glob("*.csv")):
        rows = list(read_csv(path, "cp949"))
        if not rows:
            continue
        headers = list(rows[0])
        male = age_columns(headers, 65, "남자")
        female = age_columns(headers, 65, "여자")
        groups = defaultdict(lambda: [0, 0])
        for row in rows:
            key = (
                row["기준연월"],
                (row["시도명"] or "").strip(),
                (row["시군구명"] or "").strip(),
            )
            groups[key][0] += sum(integer(row.get(column)) for column in male)
            groups[key][1] += sum(integer(row.get(column)) for column in female)
        for (date, sido, sigungu), values in groups.items():
            output.append(
                {
                    "기준일": date,
                    "시도명": sido,
                    "시군구명": sigungu,
                    "65세이상1인세대": sum(values),
                    "65세이상남자1인세대": values[0],
                    "65세이상여자1인세대": values[1],
                }
            )
    return output


def location(full_name: str | None) -> tuple[str, str]:
    parts = (full_name or "").split()
    if not parts:
        return "", ""
    sigungu = parts[1] if len(parts) > 1 else ""
    if len(parts) > 2 and parts[1].endswith("시") and parts[2].endswith("구"):
        sigungu = f"{parts[1]} {parts[2]}"
    return parts[0], sigungu


def build_supply_snapshots() -> list[dict]:
    snapshots = [
        ("2023-10-26", PROCESSED / "time_series/facility_status_20231026/general.csv",
         PROCESSED / "time_series/facility_status_20231026/occupancy.csv",
         PROCESSED / "time_series/facility_status_20231026/staff.csv"),
        ("2024-04-30", PROCESSED / "time_series/facility_status_20240430/general.csv",
         PROCESSED / "time_series/facility_status_20240430/occupancy.csv",
         PROCESSED / "time_series/facility_status_20240430/staff.csv"),
        ("2024-07-16", PROCESSED / "time_series/facility_status_20240716/general.csv",
         PROCESSED / "time_series/facility_status_20240716/occupancy.csv",
         PROCESSED / "time_series/facility_status_20240716/staff.csv"),
        ("2025-04-01", PROCESSED / "ltci_facility_status_20250401/ltci_facility_general_20250401.csv",
         PROCESSED / "ltci_facility_status_20250401/ltci_facility_occupancy_20250401.csv",
         PROCESSED / "ltci_facility_status_20250401/ltci_facility_staff_20250401.csv"),
        ("2026-06-10", PROCESSED / "ltci_facility_status_20260610/ltci_facility_general_20260610.csv",
         PROCESSED / "ltci_facility_status_20260610/ltci_facility_capacity_20260610.csv",
         PROCESSED / "ltci_facility_status_20260610/ltci_facility_staff_20260610.csv"),
    ]
    output = []
    for date, general_path, occupancy_path, staff_path in snapshots:
        geo = {}
        region_names = {}
        for row in read_csv(general_path):
            if row.get("시도코드") and row.get("시군구코드"):
                sido, sigungu = location(row.get("시도 시군구 법정동명", ""))
                region_code = f'{row["시도코드"]}{row["시군구코드"]}'
                if sido or sigungu:
                    region_names[region_code] = (sido, sigungu)
                geo.setdefault(
                    row["장기요양기관코드"],
                    region_code,
                )
        groups = defaultdict(lambda: {"institutions": set(), "capacity": 0, "current": 0, "current_rows": 0,
                                      "social": 0, "nurse": 0, "assistant": 0, "caregiver": 0})
        type_names = {}
        for row in read_csv(occupancy_path):
            inst = row["장기요양기관코드"]
            if inst not in geo:
                continue
            type_code = row["기관유형코드"]
            key = (geo[inst], type_code)
            group = groups[key]
            group["institutions"].add(inst)
            group["capacity"] += integer(row.get("정원"))
            if "현원" in row and (row.get("현원") or "").strip() != "":
                group["current"] += integer(row.get("현원"))
                group["current_rows"] += 1
            type_names[type_code] = row.get("기관유형명", "")
        if staff_path and staff_path.exists():
            for row in read_csv(staff_path):
                inst = row["장기요양기관코드"]
                if inst not in geo:
                    continue
                type_code = row["기관유형코드"]
                key = (geo[inst], type_code)
                group = groups[key]
                group["institutions"].add(inst)
                group["social"] += integer(row.get("사회복지사"))
                group["nurse"] += integer(row.get("간호사"))
                group["assistant"] += integer(row.get("간호조무사"))
                group["caregiver"] += integer(row.get("요양보호사"))
                type_names.setdefault(type_code, row.get("기관유형코드명", ""))
        for (region_code, type_code), group in groups.items():
            sido, sigungu = region_names.get(region_code, ("", ""))
            interpretable = bool(
                re.match(r"^(A|G|H|I|M|S)", type_code)
                or type_code in {"B03", "B04", "C03", "C04"}
            )
            output.append(
                {
                    "기준일": date,
                    "시설_지역코드": region_code,
                    "시도명": sido,
                    "시군구명": sigungu,
                    "기관유형코드": type_code,
                    "기관유형명": type_names.get(type_code, ""),
                    "기관수": len(group["institutions"]),
                    "정원": group["capacity"],
                    "현원": group["current"] if group["current_rows"] else "",
                    "가동률": (
                        round(group["current"] / group["capacity"], 6)
                        if interpretable and group["current_rows"] and group["capacity"]
                        else ""
                    ),
                    "가동률해석가능": interpretable,
                    "사회복지사": group["social"],
                    "간호사": group["nurse"],
                    "간호조무사": group["assistant"],
                    "요양보호사": group["caregiver"],
                    "비교주의": "공개 스냅샷 간 추출·기관신고 체계 변경 가능; 2026년 현원 미제공",
                }
            )
    return output


def main() -> None:
    tables = {
        "ltci_demand_sigungu_year_end_2022_2025.csv": build_demand(),
        "elderly_population_sigungu_year_end_2022_2025.csv": build_population(),
        "elderly_single_households_sigungu_year_end_2022_2025.csv": build_single_households(),
        "ltci_supply_snapshots_202310_202606.csv": build_supply_snapshots(),
    }
    for name, rows in tables.items():
        write_csv(OUTPUT / name, rows)
        print(f"{name}: {len(rows)}")


if __name__ == "__main__":
    main()
