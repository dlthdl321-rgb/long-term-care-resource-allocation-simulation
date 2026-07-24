"""공개 원본 파일에서 분석용 표를 전부 다시 만드는 Python 파이프라인."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from build_core_time_series import main as build_time_series
from extract_xlsx_sheet import extract


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
READY = ROOT / "data" / "analysis_ready"
MANIFEST = ROOT / "outputs" / "raw_preprocessing" / "lineage_manifest.json"
GRADES = ["1등급", "2등급", "3등급", "4등급", "5등급", "인지지원등급"]
STAFF = ["사회복지사", "간호사", "간호조무사", "물리치료사", "작업치료사", "요양보호사"]


def read_csv(path: Path, encoding: str = "cp949") -> pd.DataFrame:
    """식별자를 문자열로 보존해 CSV 전체를 읽는다."""
    return pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)


def number(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """쉼표·공백을 제거하고 지정 컬럼만 숫자로 바꾼다."""
    result = frame.copy()
    for column in columns:
        if column in result:
            result[column] = pd.to_numeric(
                result[column].str.replace(",", "", regex=False).str.strip(),
                errors="coerce",
            ).fillna(0)
    return result


def write(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_facility_workbooks() -> list[dict[str, object]]:
    """원본 XLSX의 필요한 시트를 표준 CSV로 추출한다."""
    specs = [
        ("ltci_facility_status_20260610.xlsx", "ltci_facility_status_20260610", "20260610"),
        ("ltci_facility_status_20250401.xlsx", "ltci_facility_status_20250401", "20250401"),
        ("time_series/facility_status/facility_status_20231026.xlsx", "time_series/facility_status_20231026", ""),
        ("time_series/facility_status/facility_status_20240430.xlsx", "time_series/facility_status_20240430", ""),
        ("time_series/facility_status/facility_status_20240716.xlsx", "time_series/facility_status_20240716", ""),
    ]
    records = []
    for raw_name, processed_name, suffix in specs:
        source = RAW / raw_name
        destination = PROCESSED / processed_name
        names = {
            "일반현황": f"ltci_facility_general_{suffix}.csv" if suffix else "general.csv",
            "입소인원": (
                f"ltci_facility_{'capacity' if suffix == '20260610' else 'occupancy'}_{suffix}.csv"
                if suffix
                else "occupancy.csv"
            ),
            "인력현황": f"ltci_facility_staff_{suffix}.csv" if suffix else "staff.csv",
        }
        for sheet, filename in names.items():
            target = destination / filename
            rows = extract(source, sheet, target) - 1
            records.append(
                {
                    "source": str(source.relative_to(ROOT)),
                    "source_sha256": sha256(source),
                    "sheet": sheet,
                    "output": str(target.relative_to(ROOT)),
                    "rows": rows,
                }
            )
    return records


def age_columns(columns: list[str], minimum: int, sex: str) -> list[str]:
    selected = []
    for column in columns:
        match = re.search(r"(\d+)세", column)
        if sex in column and match and int(match.group(1)) >= minimum:
            selected.append(column)
    return selected


def build_current_population() -> tuple[pd.DataFrame, pd.DataFrame]:
    source = RAW / "population_age_sex_admin_dong_202606.csv"
    raw = read_csv(source)
    ages = {
        (minimum, sex): age_columns(list(raw.columns), minimum, sex)
        for minimum in (65, 75, 85)
        for sex in ("남자", "여자")
    }
    numeric = sorted({"계", *sum(ages.values(), [])})
    raw = number(raw, numeric)
    output = raw[["행정기관코드", "기준연월", "시도명", "시군구명", "읍면동명"]].copy()
    output["총인구"] = raw["계"]
    for minimum in (65, 75, 85):
        output[f"{minimum}세이상인구"] = raw[ages[(minimum, "남자")] + ages[(minimum, "여자")]].sum(axis=1)
    output["65세이상남자"] = raw[ages[(65, "남자")]].sum(axis=1)
    output["65세이상여자"] = raw[ages[(65, "여자")]].sum(axis=1)
    output["고령화율"] = np.where(
        output["총인구"].gt(0), output["65세이상인구"] / output["총인구"] * 100, np.nan
    )
    write(output, READY / "elderly_population_admin_dong_202606.csv")

    aggregations = {
        "총인구": "sum", "65세이상인구": "sum", "75세이상인구": "sum",
        "85세이상인구": "sum", "65세이상남자": "sum", "65세이상여자": "sum",
    }
    coded = output.assign(주민등록_시군구코드=output["행정기관코드"].str[:5])
    sigungu = coded.groupby(["주민등록_시군구코드", "기준연월"], as_index=False).agg(
        시도명=("시도명", "first"),
        시군구명=("시군구명", "first"),
        **{column: (column, method) for column, method in aggregations.items()},
    )
    sigungu["고령화율"] = np.where(
        sigungu["총인구"].gt(0), sigungu["65세이상인구"] / sigungu["총인구"] * 100, np.nan
    )
    write(sigungu, READY / "elderly_population_sigungu_202606.csv")
    return raw, sigungu


def build_current_households() -> tuple[pd.DataFrame, pd.DataFrame]:
    source = RAW / "single_person_households_age_sex_legal_dong_202606.csv"
    raw = read_csv(source)
    male = age_columns(list(raw.columns), 65, "남자")
    female = age_columns(list(raw.columns), 65, "여자")
    raw = number(raw, male + female)
    output = raw[["법정동코드", "기준연월", "시도명", "시군구명", "읍면동명", "리명"]].copy()
    output["65세이상남자1인세대"] = raw[male].sum(axis=1)
    output["65세이상여자1인세대"] = raw[female].sum(axis=1)
    output["65세이상1인세대"] = output["65세이상남자1인세대"] + output["65세이상여자1인세대"]
    write(output, READY / "elderly_single_person_households_legal_dong_202606.csv")
    sigungu = output.assign(법정동_시군구코드=output["법정동코드"].str[:5]).groupby(
        ["법정동_시군구코드", "기준연월"], as_index=False
    ).agg(
        시도명=("시도명", "first"),
        시군구명=("시군구명", "first"),
        **{
            column: (column, "sum")
            for column in ["65세이상1인세대", "65세이상남자1인세대", "65세이상여자1인세대"]
        },
    )
    write(sigungu, READY / "elderly_single_person_households_sigungu_202606.csv")
    return raw, sigungu


def build_current_demand() -> pd.DataFrame:
    raw = read_csv(RAW / "ltci_grade_decisions_sigungu_202605.csv")
    records = []
    for (sido, sigungu), group in raw.groupby(["시도", "시군구"], sort=True):
        applicants_hidden = group["신청자"].eq("*").sum()
        recognized_hidden = sum(group[column].eq("*").sum() for column in GRADES)
        applicants_known = pd.to_numeric(group["신청자"].where(group["신청자"].ne("*")), errors="coerce").sum()
        recognized_known = sum(
            pd.to_numeric(group[column].where(group[column].ne("*")), errors="coerce").sum()
            for column in GRADES
        )
        records.append({
            "시도": sido, "시군구": sigungu,
            "신청자_공개값합계": int(applicants_known), "신청자_비공개셀수": int(applicants_hidden),
            "신청자_추정하한": int(applicants_known + applicants_hidden),
            "신청자_추정상한": int(applicants_known + 4 * applicants_hidden),
            "인정자_공개값합계": int(recognized_known), "인정자_비공개셀수": int(recognized_hidden),
            "인정자_추정하한": int(recognized_known + recognized_hidden),
            "인정자_추정상한": int(recognized_known + 4 * recognized_hidden),
            "자료기준": "2026-05-31",
        })
    output = pd.DataFrame(records)
    write(output, READY / "ltci_demand_sigungu_bounds_202605.csv")
    return output


def location(frame: pd.DataFrame) -> pd.DataFrame:
    parts = frame["시도 시군구 법정동명"].fillna("").str.split()
    frame = frame.copy()
    frame["시도명"] = parts.str[0].fillna("")
    second, third = parts.str[1].fillna(""), parts.str[2].fillna("")
    frame["시군구명"] = np.where(second.str.endswith("시") & third.str.endswith("구"), second + " " + third, second)
    frame["시설_지역코드"] = frame["시도코드"].astype(str) + frame["시군구코드"].astype(str)
    # 같은 지역코드의 주소가 있는 행을 이용해 주소 공란 행의 지역명을 복원한다.
    for column in ("시도명", "시군구명"):
        known = (
            frame.loc[frame[column].astype(str).str.strip().ne("")]
            .drop_duplicates("시설_지역코드")
            .set_index("시설_지역코드")[column]
        )
        missing = frame[column].astype(str).str.strip().eq("")
        frame.loc[missing, column] = frame.loc[missing, "시설_지역코드"].map(known).fillna("")
    return frame


def build_current_supply() -> pd.DataFrame:
    directory = PROCESSED / "ltci_facility_status_20260610"
    general = read_csv(directory / "ltci_facility_general_20260610.csv", "utf-8-sig")
    general = general.loc[
        general["시도코드"].str.strip().ne("")
        & general["시군구코드"].str.strip().ne("")
        & general["장기요양기관코드"].str.strip().ne("")
    ]
    general = location(general)
    geo = general.drop_duplicates("장기요양기관코드")[
        ["장기요양기관코드", "시설_지역코드", "시도명", "시군구명"]
    ]
    capacity = number(read_csv(directory / "ltci_facility_capacity_20260610.csv", "utf-8-sig"), ["정원"]).merge(
        geo, on="장기요양기관코드", how="inner", validate="many_to_one"
    )
    staff = number(read_csv(directory / "ltci_facility_staff_20260610.csv", "utf-8-sig"), STAFF).merge(
        geo, on="장기요양기관코드", how="inner", validate="many_to_one"
    )
    keys = ["시설_지역코드", "기관유형코드"]
    cap = capacity.groupby(keys, as_index=False).agg(
        시도명=("시도명", "first"), 시군구명=("시군구명", "first"),
        기관유형명=("기관유형명", "first"), 정원=("정원", "sum"),
        기관목록_정원=("장기요양기관코드", lambda value: set(value)),
    )
    people = staff.groupby(keys, as_index=False).agg(
        시도명_인력=("시도명", "first"), 시군구명_인력=("시군구명", "first"),
        기관유형명_인력=("기관유형코드명", "first"),
        기관목록_인력=("장기요양기관코드", lambda value: set(value)),
        **{column: (column, "sum") for column in STAFF},
    )
    supply = cap.merge(people, on=keys, how="outer")
    supply["시도명"] = supply["시도명"].fillna(supply["시도명_인력"])
    supply["시군구명"] = supply["시군구명"].fillna(supply["시군구명_인력"])
    supply["기관유형명"] = supply["기관유형명"].fillna(supply["기관유형명_인력"])
    supply["기관수"] = supply.apply(
        lambda row: len((row["기관목록_정원"] if isinstance(row["기관목록_정원"], set) else set())
                        | (row["기관목록_인력"] if isinstance(row["기관목록_인력"], set) else set())), axis=1
    )
    for column in ["정원", *STAFF]:
        supply[column] = supply[column].fillna(0)
    supply["자료기준"] = "2026-06-10"
    output = supply[[
        "시설_지역코드", "시도명", "시군구명", "기관유형코드", "기관유형명",
        "기관수", "정원", *STAFF, "자료기준",
    ]].sort_values(["시설_지역코드", "기관유형코드"])
    write(output, READY / "ltci_supply_sigungu_service_type_20260610.csv")
    return output


def build_historical_occupancy() -> pd.DataFrame:
    directory = PROCESSED / "ltci_facility_status_20250401"
    general = read_csv(directory / "ltci_facility_general_20250401.csv", "utf-8-sig")
    general = general.loc[
        general["시도코드"].str.strip().ne("")
        & general["시군구코드"].str.strip().ne("")
        & general["장기요양기관코드"].str.strip().ne("")
    ]
    general = location(general)
    geo = general.drop_duplicates("장기요양기관코드")[
        ["장기요양기관코드", "시설_지역코드", "시도명", "시군구명"]
    ]
    occupancy = read_csv(directory / "ltci_facility_occupancy_20250401.csv", "utf-8-sig")
    occupancy["현원결측"] = occupancy["현원"].str.strip().eq("")
    occupancy = number(occupancy, ["정원", "현원"]).merge(
        geo, on="장기요양기관코드", how="inner", validate="many_to_one"
    )
    occupancy["정원초과"] = (~occupancy["현원결측"]) & occupancy["정원"].gt(0) & occupancy["현원"].gt(occupancy["정원"])
    keys = ["시설_지역코드", "기관유형코드"]
    records = []
    for key, group in occupancy.groupby(keys, sort=True):
        known = group.loc[~group["현원결측"]]
        service_code = key[1]
        constrained = bool(
            re.match(r"^(A|G|H|I|M|S)", service_code)
            or service_code in {"B03", "B04", "C03", "C04"}
        )
        capacity, current = known["정원"].sum(), known["현원"].sum()
        records.append(dict(zip(keys, key)) | {
            "시도명": group["시도명"].iloc[0], "시군구명": group["시군구명"].iloc[0],
            "기관유형명": group["기관유형명"].iloc[0],
            "기관수": group["장기요양기관코드"].nunique(),
            "현원확인기관수": known["장기요양기관코드"].nunique(),
            "현원결측행수": int(group["현원결측"].sum()),
            "정원합계_현원확인기관": capacity, "현원합계": current,
            "원자료_현원정원비": current / capacity if capacity else np.nan,
            "가동률": current / capacity if constrained and capacity else np.nan,
            "가동률해석가능": constrained,
            "지표해석": "정원 대비 현원 가동률" if constrained else "방문형·복지용구는 정원 대비 비율 해석 금지",
            "정원초과행수": int(known["정원초과"].sum()) if constrained else np.nan,
            "자료기준": "2025-04-01", "용도": "2026년 현재값이 아닌 과거 가동률 민감도 기준",
        })
    output = pd.DataFrame(records)
    write(output, READY / "ltci_historical_occupancy_sigungu_service_type_20250401.csv")
    return output


def main() -> None:
    READY.mkdir(parents=True, exist_ok=True)
    lineage = extract_facility_workbooks()
    tables = {
        "current_population": build_current_population()[1],
        "current_households": build_current_households()[1],
        "current_demand": build_current_demand(),
        "current_supply": build_current_supply(),
        "historical_occupancy": build_historical_occupancy(),
    }
    build_time_series()
    for name, frame in tables.items():
        print(f"{name}: {len(frame):,} rows")
    outputs = sorted(READY.glob("*.csv"))
    payload = {
        "pipeline": "raw -> Python extraction/transformation -> analysis_ready",
        "manual_value_edits": False,
        "raw_excel_extractions": lineage,
        "analysis_ready": [
            {"file": str(path.relative_to(ROOT)), "rows": len(read_csv(path, "utf-8-sig")), "sha256": sha256(path)}
            for path in outputs
        ],
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
