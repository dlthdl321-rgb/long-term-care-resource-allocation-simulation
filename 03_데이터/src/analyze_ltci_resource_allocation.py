"""장기요양 수급 취약성과 자원배치 시뮬레이션 분석 파이프라인.

이 스크립트는 다음 순서로 실행한다.
1. 입력 파일·컬럼·키·결측·중복 감사
2. 변수 사전과 기술통계 생성
3. 시군구×서비스 유형 핵심 지표 계산
4. 경쟁 가설 A~C의 탐색적 검증
5. 선택한 서비스의 자원배치 시나리오 비교

주의:
- 기본 실행은 데이터 감사만 수행한다.
- 지역 결합률이 기준보다 낮으면 지표 분석을 중단한다.
- 추론통계는 --run-inference를 지정했을 때만 수행한다.
- 기관 상세 API 1,600건 표본은 모집단 추론에 사용하지 않는다.
- 결과는 실제 서비스 부족이나 인과효과가 아니라 상대적 공급압력과
  설정한 가정 안의 공급지표 변화를 보여준다.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "analysis_ready"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "analysis"

FILES = {
    "demand_current": DATA_DIR / "ltci_demand_sigungu_bounds_202605.csv",
    "population_current": DATA_DIR / "elderly_population_sigungu_202606.csv",
    "single_household_current": (
        DATA_DIR / "elderly_single_person_households_sigungu_202606.csv"
    ),
    "supply_current": DATA_DIR / "ltci_supply_sigungu_service_type_20260610.csv",
    "demand_panel": DATA_DIR / "ltci_demand_sigungu_year_end_2022_2025.csv",
    "population_panel": DATA_DIR / "elderly_population_sigungu_year_end_2022_2025.csv",
    "single_household_panel": (
        DATA_DIR / "elderly_single_households_sigungu_year_end_2022_2025.csv"
    ),
    "supply_snapshots": DATA_DIR / "ltci_supply_snapshots_202310_202606.csv",
    "historical_occupancy": (
        DATA_DIR / "ltci_historical_occupancy_sigungu_service_type_20250401.csv"
    ),
}

REQUIRED_COLUMNS = {
    "demand_current": {
        "시도",
        "시군구",
        "인정자_공개값합계",
        "인정자_비공개셀수",
        "인정자_추정하한",
        "인정자_추정상한",
        "자료기준",
    },
    "population_current": {
        "주민등록_시군구코드",
        "기준연월",
        "시도명",
        "시군구명",
        "총인구",
        "65세이상인구",
        "75세이상인구",
        "85세이상인구",
    },
    "single_household_current": {
        "법정동_시군구코드",
        "기준연월",
        "시도명",
        "시군구명",
        "65세이상1인세대",
    },
    "supply_current": {
        "시설_지역코드",
        "시도명",
        "시군구명",
        "기관유형코드",
        "기관유형명",
        "기관수",
        "정원",
        "사회복지사",
        "간호사",
        "간호조무사",
        "요양보호사",
        "자료기준",
    },
    "demand_panel": {
        "기준일",
        "시도",
        "시군구",
        "인정자_공개값합계",
        "인정자_추정하한",
        "인정자_추정상한",
    },
    "population_panel": {
        "기준일",
        "시도명",
        "시군구명",
        "총인구",
        "65세이상인구",
        "75세이상인구",
        "85세이상인구",
    },
    "single_household_panel": {
        "기준일",
        "시도명",
        "시군구명",
        "65세이상1인세대",
    },
    "supply_snapshots": {
        "기준일",
        "시설_지역코드",
        "시도명",
        "시군구명",
        "기관유형코드",
        "기관유형명",
        "기관수",
        "정원",
        "현원",
        "가동률",
        "가동률해석가능",
        "요양보호사",
        "비교주의",
    },
    "historical_occupancy": {
        "시설_지역코드",
        "시도명",
        "시군구명",
        "기관유형코드",
        "기관유형명",
        "기관수",
        "현원확인기관수",
        "현원결측행수",
        "정원합계_현원확인기관",
        "현원합계",
        "가동률",
        "가동률해석가능",
        "정원초과행수",
        "자료기준",
    },
}

KEY_COLUMNS = {
    "demand_current": ["시도", "시군구"],
    "population_current": ["주민등록_시군구코드"],
    "single_household_current": ["법정동_시군구코드"],
    "supply_current": ["시설_지역코드", "기관유형코드"],
    "demand_panel": ["기준일", "시도", "시군구"],
    "population_panel": ["기준일", "시도명", "시군구명"],
    "single_household_panel": ["기준일", "시도명", "시군구명"],
    "supply_snapshots": ["기준일", "시설_지역코드", "기관유형코드"],
    "historical_occupancy": ["시설_지역코드", "기관유형코드"],
}

NUMERIC_COLUMNS = {
    "신청자_공개값합계",
    "신청자_비공개셀수",
    "신청자_추정하한",
    "신청자_추정상한",
    "인정자_공개값합계",
    "인정자_비공개셀수",
    "인정자_추정하한",
    "인정자_추정상한",
    "총인구",
    "65세이상인구",
    "75세이상인구",
    "85세이상인구",
    "65세이상남자",
    "65세이상여자",
    "고령화율",
    "65세이상1인세대",
    "65세이상남자1인세대",
    "65세이상여자1인세대",
    "기관수",
    "정원",
    "현원",
    "사회복지사",
    "간호사",
    "간호조무사",
    "물리치료사",
    "작업치료사",
    "요양보호사",
    "가동률",
    "현원확인기관수",
    "현원결측행수",
    "정원합계_현원확인기관",
    "현원합계",
    "원자료_현원정원비",
    "정원초과행수",
}

PROVINCE_ALIASES = {
    "서울": "서울특별시",
    "부산": "부산광역시",
    "대구": "대구광역시",
    "인천": "인천광역시",
    "광주": "광주광역시",
    "대전": "대전광역시",
    "울산": "울산광역시",
    "세종": "세종특별자치시",
    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "경기": "경기도",
    "경남": "경상남도",
    "경북": "경상북도",
    "전남": "전라남도",
    "전북": "전북특별자치도",
    "전라북도": "전북특별자치도",
    "제주": "제주특별자치도",
    "제주도": "제주특별자치도",
    "충남": "충청남도",
    "충북": "충청북도",
}

REGION_NAME_ALIASES = {
    ("인천광역시", "남구"): "미추홀구",
}

REGION_KEY_ALIASES = {
    ("경상북도", "군위군"): ("대구광역시", "군위군"),
}

OBSOLETE_DEMAND_REGIONS = {
    "경기도|여주군",
    "경기도|포천군",
}


@dataclass
class AuditResult:
    dataset: str
    path: str
    rows: int
    columns: int
    duplicate_keys: int
    missing_cells: int
    missing_rate: float
    date_min: str | None
    date_max: str | None
    status: str
    note: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=["audit", "describe", "metrics", "hypotheses", "simulation", "all"],
        default="audit",
        help="실행 단계. 기본값 audit는 원자료를 변경하지 않고 품질만 검사한다.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="분석 결과 저장 폴더",
    )
    parser.add_argument(
        "--crosswalk",
        type=Path,
        default=None,
        help="선택 사항: source,시도명,시군구명,분석_시도명,분석_시군구명 컬럼의 지역 대응표",
    )
    parser.add_argument(
        "--minimum-join-rate",
        type=float,
        default=0.99,
        help="핵심 지표 분석을 허용할 최소 수요지역 결합률",
    )
    parser.add_argument(
        "--run-inference",
        action="store_true",
        help="가설 A의 탐색적 Spearman 순위상관을 실행한다.",
    )
    parser.add_argument(
        "--service-code",
        default=None,
        help="시뮬레이션 대상 기관유형코드. simulation 단계에서 필수",
    )
    parser.add_argument(
        "--additional-units",
        type=int,
        default=10,
        help="시뮬레이션에서 배치할 추가 기관 단위",
    )
    parser.add_argument(
        "--candidate-quantile",
        type=float,
        default=0.25,
        help="탐색용 공급 취약 분위수. 기본값 0.25",
    )
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"필수 입력 파일이 없습니다: {path}")
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def normalize_text(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .replace({"_": "세종특별자치시", "<NA>": pd.NA})
    )


def normalize_province(series: pd.Series) -> pd.Series:
    normalized = normalize_text(series)
    return normalized.replace(PROVINCE_ALIASES)


def normalize_district(series: pd.Series) -> pd.Series:
    normalized = normalize_text(series)
    # 수요자료는 복합시를 시 단위로 제공하므로 수원시 장안구,
    # 창원시 의창구 등 일반구를 상위 시로 집계한다.
    return normalized.str.replace(r"^(.+시)\s+.+구$", r"\1", regex=True)


def numeric_candidates(frame: pd.DataFrame) -> list[str]:
    return [
        column
        for column in frame.columns
        if (
            column in NUMERIC_COLUMNS
            or (
                pd.api.types.is_numeric_dtype(frame[column])
                and not pd.api.types.is_bool_dtype(frame[column])
                and "코드" not in column
                and column not in {"기준일", "자료기준", "기준연월"}
            )
        )
    ]


def coerce_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    converted = frame.copy()
    for column in numeric_candidates(converted):
        converted[column] = pd.to_numeric(converted[column], errors="coerce")
    return converted


def date_bounds(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    date_columns = [
        column
        for column in ("기준일", "자료기준", "기준연월")
        if column in frame.columns
    ]
    if not date_columns:
        return None, None
    parsed = pd.to_datetime(frame[date_columns[0]], errors="coerce")
    if not parsed.notna().any():
        return None, None
    return parsed.min().date().isoformat(), parsed.max().date().isoformat()


def audit_dataset(name: str, path: Path, frame: pd.DataFrame) -> AuditResult:
    missing_columns = sorted(REQUIRED_COLUMNS[name] - set(frame.columns))
    keys = KEY_COLUMNS[name]
    unavailable_keys = [column for column in keys if column not in frame.columns]
    duplicate_keys = (
        int(frame.duplicated(keys, keep=False).sum()) if not unavailable_keys else -1
    )
    missing_cells = int(frame.isna().sum().sum())
    total_cells = frame.shape[0] * frame.shape[1]
    missing_rate = missing_cells / total_cells if total_cells else math.nan
    date_min, date_max = date_bounds(frame)

    problems = []
    if missing_columns:
        problems.append(f"필수 컬럼 누락: {', '.join(missing_columns)}")
    if unavailable_keys:
        problems.append(f"키 컬럼 누락: {', '.join(unavailable_keys)}")
    if duplicate_keys > 0:
        problems.append(f"중복 키 관련 행 {duplicate_keys:,}개")
    if missing_columns or unavailable_keys:
        status = "FAIL"
    elif duplicate_keys > 0:
        status = "WARN"
    else:
        status = "PASS"
    return AuditResult(
        dataset=name,
        path=str(path.relative_to(PROJECT_ROOT)),
        rows=len(frame),
        columns=len(frame.columns),
        duplicate_keys=duplicate_keys,
        missing_cells=missing_cells,
        missing_rate=missing_rate,
        date_min=date_min,
        date_max=date_max,
        status=status,
        note="; ".join(problems),
    )


def classify_variable(column: str, series: pd.Series) -> str:
    if "코드" in column or column.endswith("ID") or column.endswith("id"):
        return "식별자"
    if column in {"기준일", "자료기준", "기준연월"}:
        return "날짜·시간형"
    if pd.api.types.is_numeric_dtype(series):
        return "수치형"
    return "범주형"


def build_variable_dictionary(
    datasets: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    records = []
    for name, frame in datasets.items():
        for column in frame.columns:
            series = frame[column]
            variable_type = classify_variable(column, series)
            record = {
                "데이터셋": name,
                "칼럼": column,
                "변수종류": variable_type,
                "pandas_dtype": str(series.dtype),
                "행수": len(series),
                "결측수": int(series.isna().sum()),
                "결측률": float(series.isna().mean()),
                "고유값수": int(series.nunique(dropna=True)),
            }
            if variable_type == "수치형":
                numeric = pd.to_numeric(series, errors="coerce")
                record.update(
                    {
                        "최솟값": numeric.min(),
                        "중앙값": numeric.median(),
                        "평균": numeric.mean(),
                        "최댓값": numeric.max(),
                    }
                )
            records.append(record)
    return pd.DataFrame(records)


def descriptive_statistics(
    datasets: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    records = []
    for name, frame in datasets.items():
        for column in numeric_candidates(frame):
            values = pd.to_numeric(frame[column], errors="coerce").dropna()
            if values.empty:
                continue
            q1, median, q3 = values.quantile([0.25, 0.5, 0.75])
            mean = values.mean()
            std = values.std(ddof=1)
            records.append(
                {
                    "데이터셋": name,
                    "칼럼": column,
                    "유효값수": len(values),
                    "결측수": int(frame[column].isna().sum()),
                    "평균": mean,
                    "중앙값": median,
                    "최솟값": values.min(),
                    "최댓값": values.max(),
                    "범위": values.max() - values.min(),
                    "1사분위수": q1,
                    "3사분위수": q3,
                    "사분위범위": q3 - q1,
                    "표준편차": std,
                    "변동계수": std / mean if mean != 0 else np.nan,
                }
            )
    return pd.DataFrame(records)


def standardize_region_columns(
    frame: pd.DataFrame,
    province_column: str,
    district_column: str,
    source: str,
    crosswalk: pd.DataFrame | None,
) -> pd.DataFrame:
    result = frame.copy()
    result["원본_시도명"] = normalize_province(result[province_column])
    result["원본_시군구명"] = normalize_district(result[district_column])
    for (province, old_district), current_district in REGION_NAME_ALIASES.items():
        renamed_mask = (
            result["원본_시도명"].eq(province)
            & result["원본_시군구명"].eq(old_district)
        )
        result.loc[renamed_mask, "원본_시군구명"] = current_district
    for (
        old_province,
        old_district,
    ), (
        current_province,
        current_district,
    ) in REGION_KEY_ALIASES.items():
        moved_mask = (
            result["원본_시도명"].eq(old_province)
            & result["원본_시군구명"].eq(old_district)
        )
        result.loc[moved_mask, "원본_시도명"] = current_province
        result.loc[moved_mask, "원본_시군구명"] = current_district
    sejong_mask = result["원본_시도명"].eq("세종특별자치시")
    result.loc[sejong_mask, "원본_시군구명"] = "세종특별자치시"
    result["분석_시도명"] = result["원본_시도명"]
    result["분석_시군구명"] = result["원본_시군구명"]

    if crosswalk is not None:
        mapping = crosswalk.loc[crosswalk["source"].eq(source)].copy()
        mapping["시도명"] = normalize_text(mapping["시도명"])
        mapping["시군구명"] = normalize_text(mapping["시군구명"])
        result = result.merge(
            mapping[
                ["시도명", "시군구명", "분석_시도명", "분석_시군구명"]
            ].rename(
                columns={
                    "시도명": "원본_시도명",
                    "시군구명": "원본_시군구명",
                    "분석_시도명": "대응_시도명",
                    "분석_시군구명": "대응_시군구명",
                }
            ),
            on=["원본_시도명", "원본_시군구명"],
            how="left",
            validate="many_to_one",
        )
        result["분석_시도명"] = result["대응_시도명"].fillna(result["분석_시도명"])
        result["분석_시군구명"] = result["대응_시군구명"].fillna(
            result["분석_시군구명"]
        )
        result = result.drop(columns=["대응_시도명", "대응_시군구명"])

    result["지역키"] = result["분석_시도명"] + "|" + result["분석_시군구명"]
    return result


def load_crosswalk(path: Path | None) -> pd.DataFrame | None:
    if path is None:
        return None
    crosswalk = read_csv(path)
    required = {"source", "시도명", "시군구명", "분석_시도명", "분석_시군구명"}
    missing = required - set(crosswalk.columns)
    if missing:
        raise ValueError(f"지역 대응표 필수 컬럼 누락: {sorted(missing)}")
    return crosswalk


def prepare_current_metrics(
    datasets: dict[str, pd.DataFrame],
    crosswalk: pd.DataFrame | None,
    minimum_join_rate: float,
    output_dir: Path,
) -> pd.DataFrame:
    demand = standardize_region_columns(
        datasets["demand_current"], "시도", "시군구", "demand", crosswalk
    )
    population = standardize_region_columns(
        datasets["population_current"],
        "시도명",
        "시군구명",
        "population",
        crosswalk,
    )
    households = standardize_region_columns(
        datasets["single_household_current"],
        "시도명",
        "시군구명",
        "single_household",
        crosswalk,
    )
    supply = standardize_region_columns(
        datasets["supply_current"], "시도명", "시군구명", "supply", crosswalk
    )

    demand["인정자_추정중앙"] = (
        demand["인정자_추정하한"] + demand["인정자_추정상한"]
    ) / 2
    demand = demand.loc[demand["인정자_추정상한"].gt(0)].copy()
    demand = demand.loc[~demand["지역키"].isin(OBSOLETE_DEMAND_REGIONS)].copy()

    pop_agg = (
        population.groupby("지역키", as_index=False)
        .agg(
            분석_시도명=("분석_시도명", "first"),
            분석_시군구명=("분석_시군구명", "first"),
            총인구=("총인구", "sum"),
            **{
                "65세이상인구": ("65세이상인구", "sum"),
                "75세이상인구": ("75세이상인구", "sum"),
                "85세이상인구": ("85세이상인구", "sum"),
            },
        )
    )
    hh_agg = (
        households.groupby("지역키", as_index=False)["65세이상1인세대"]
        .sum()
    )
    supply_value_columns = [
        "기관수",
        "정원",
        "사회복지사",
        "간호사",
        "간호조무사",
        "물리치료사",
        "작업치료사",
        "요양보호사",
    ]
    supply_agg = (
        supply.groupby(
            ["지역키", "기관유형코드", "기관유형명"],
            as_index=False,
            dropna=False,
        )
        .agg(
            분석_시도명=("분석_시도명", "first"),
            분석_시군구명=("분석_시군구명", "first"),
            시설_지역코드=("시설_지역코드", lambda values: "|".join(
                sorted({str(value) for value in values if pd.notna(value)})
            )),
            자료기준=("자료기준", "max"),
            **{column: (column, "sum") for column in supply_value_columns},
        )
    )

    demand_regions = set(demand["지역키"])
    unused_supply = supply_agg.loc[~supply_agg["지역키"].isin(demand_regions)].copy()
    unused_supply.to_csv(
        output_dir / "supply_regions_outside_demand_scope.csv",
        index=False,
        encoding="utf-8-sig",
    )
    join_report = []
    for name, region_frame in {
        "population": pop_agg,
        "single_household": hh_agg,
        "supply": supply_agg,
    }.items():
        matched = demand_regions & set(region_frame["지역키"])
        unmatched = sorted(demand_regions - set(region_frame["지역키"]))
        join_report.append(
            {
                "dataset": name,
                "demand_regions": len(demand_regions),
                "matched_regions": len(matched),
                "join_rate": len(matched) / len(demand_regions),
                "unmatched_regions": "|".join(unmatched),
            }
        )
    join_report_frame = pd.DataFrame(join_report)
    join_report_frame.to_csv(
        output_dir / "region_join_report.csv", index=False, encoding="utf-8-sig"
    )
    worst_join_rate = join_report_frame["join_rate"].min()
    if worst_join_rate < minimum_join_rate:
        raise RuntimeError(
            f"지역 결합률 {worst_join_rate:.2%}가 기준 "
            f"{minimum_join_rate:.2%}보다 낮습니다. "
            "region_join_report.csv를 확인하고 --crosswalk를 지정하세요."
        )

    base = demand[
        [
            "지역키",
            "분석_시도명",
            "분석_시군구명",
            "인정자_공개값합계",
            "인정자_비공개셀수",
            "인정자_추정하한",
            "인정자_추정중앙",
            "인정자_추정상한",
        ]
    ].merge(pop_agg, on=["지역키", "분석_시도명", "분석_시군구명"])
    base = base.merge(hh_agg, on="지역키")
    service_master = supply_agg[["기관유형코드", "기관유형명"]].drop_duplicates()
    if service_master["기관유형코드"].duplicated().any():
        raise RuntimeError("하나의 기관유형코드에 둘 이상의 기관유형명이 연결됩니다.")
    complete_grid = base[["지역키"]].merge(service_master, how="cross")
    complete_supply = complete_grid.merge(
        supply_agg,
        on=["지역키", "기관유형코드", "기관유형명"],
        how="left",
        validate="one_to_one",
        indicator="공급원자료결합",
    )
    complete_supply["공급원자료행존재"] = complete_supply["공급원자료결합"].eq("both")
    complete_supply = complete_supply.drop(columns="공급원자료결합")
    for column in supply_value_columns:
        complete_supply[column] = complete_supply[column].fillna(0)
    metrics = complete_supply.merge(
        base,
        on="지역키",
        how="inner",
        validate="many_to_one",
        suffixes=("", "_수요"),
    )
    for column in ["분석_시도명", "분석_시군구명"]:
        demand_column = f"{column}_수요"
        metrics[column] = metrics[column].fillna(metrics[demand_column])
        metrics = metrics.drop(columns=demand_column)

    visit_pattern = r"방문요양|방문목욕|방문간호|복지용구"
    metrics["서비스분류"] = np.where(
        metrics["기관유형명"].str.contains(visit_pattern, regex=True, na=False),
        "방문·복지용구형",
        "정원기반형",
    )
    metrics["정원개념적용"] = metrics["서비스분류"].eq("정원기반형")
    service_rules = (
        metrics.groupby(["기관유형코드", "기관유형명", "서비스분류"], as_index=False)
        .agg(
            전국기관수=("기관수", "sum"),
            전국정원=("정원", "sum"),
            기관존재지역수=("기관수", lambda values: int(values.gt(0).sum())),
            정원양수지역수=("정원", lambda values: int(values.gt(0).sum())),
        )
    )
    service_rules["정원개념적용"] = service_rules["서비스분류"].eq("정원기반형")
    service_rules["정원자료충족률"] = np.where(
        service_rules["기관존재지역수"].gt(0),
        service_rules["정원양수지역수"] / service_rules["기관존재지역수"],
        np.nan,
    )
    service_rules["정원지표사용상태"] = np.select(
        [
            ~service_rules["정원개념적용"],
            service_rules["정원자료충족률"].ge(0.80),
        ],
        [
            "비적용",
            "사용가능",
        ],
        default="조건부_정원자료부족",
    )
    service_rules.to_csv(
        output_dir / "service_metric_rules.csv",
        index=False,
        encoding="utf-8-sig",
    )
    metrics = metrics.merge(
        service_rules[
            [
                "기관유형코드",
                "정원자료충족률",
                "정원지표사용상태",
            ]
        ],
        on="기관유형코드",
        how="left",
        validate="many_to_one",
    )
    metrics["정원지표사용가능"] = metrics["정원지표사용상태"].eq("사용가능")
    metrics["공급0근거"] = np.select(
        [
            metrics["기관수"].gt(0),
            ~metrics["공급원자료행존재"],
        ],
        [
            "기관존재",
            "전수시설표_지역유형조합미관측",
        ],
        default="원자료행은있으나기관수0",
    )
    zero_validation = (
        metrics.groupby(
            ["기관유형코드", "기관유형명", "정원지표사용상태"],
            as_index=False,
        )
        .agg(
            지역수=("지역키", "nunique"),
            기관합계=("기관수", "sum"),
            공급0지역수=("기관수", lambda values: int(values.eq(0).sum())),
            원자료행미관측지역수=(
                "공급원자료행존재",
                lambda values: int((~values).sum()),
            ),
        )
    )
    zero_validation.to_csv(
        output_dir / "supply_zero_validation.csv",
        index=False,
        encoding="utf-8-sig",
    )

    for suffix, denominator in {
        "하한수요": "인정자_추정하한",
        "중앙수요": "인정자_추정중앙",
        "상한수요": "인정자_추정상한",
    }.items():
        metrics[f"인정자1000명당기관수_{suffix}"] = (
            metrics["기관수"] / metrics[denominator] * 1000
        )
        metrics[f"인정자1000명당정원_{suffix}"] = (
            metrics["정원"] / metrics[denominator] * 1000
        ).where(metrics["정원지표사용가능"])
        metrics[f"인정자1000명당요양보호사_{suffix}"] = (
            metrics["요양보호사"] / metrics[denominator] * 1000
        )

    metrics["75세이상1000명당기관수"] = (
        metrics["기관수"] / metrics["75세이상인구"] * 1000
    )
    metrics["고령1인세대1000세대당기관수"] = (
        metrics["기관수"] / metrics["65세이상1인세대"] * 1000
    )
    metrics["기관1곳당인정자"] = (
        metrics["인정자_추정중앙"] / metrics["기관수"].replace(0, np.nan)
    )
    return metrics


def demand_growth_panel(
    demand_panel: pd.DataFrame,
    crosswalk: pd.DataFrame | None,
) -> pd.DataFrame:
    demand = standardize_region_columns(
        demand_panel, "시도", "시군구", "demand", crosswalk
    )
    demand["기준일"] = pd.to_datetime(demand["기준일"], errors="coerce")
    demand["인정자_추정중앙"] = (
        demand["인정자_추정하한"] + demand["인정자_추정상한"]
    ) / 2
    wide = demand.pivot_table(
        index="지역키",
        columns=demand["기준일"].dt.year,
        values="인정자_추정중앙",
        aggfunc="sum",
    )
    if 2022 not in wide or 2025 not in wide:
        raise RuntimeError("수요 패널에 2022년 또는 2025년 자료가 없습니다.")
    growth = wide.reset_index()
    growth["인정자증가율_2022_2025"] = (
        growth[2025] - growth[2022]
    ) / growth[2022].replace(0, np.nan)
    growth["인정자CAGR_2022_2025"] = (
        (growth[2025] / growth[2022].replace(0, np.nan)) ** (1 / 3) - 1
    )
    return growth


def quantile_candidates(
    metrics: pd.DataFrame,
    quantile: float,
) -> pd.DataFrame:
    metric_column = "인정자1000명당기관수_중앙수요"
    result = metrics.copy()
    result["공급하위경계"] = result.groupby("기관유형코드")[metric_column].transform(
        lambda values: values.quantile(quantile)
    )
    result["공급하위후보"] = result[metric_column].le(result["공급하위경계"])
    return result


def plot_supply_distributions(metrics: pd.DataFrame, output_dir: Path) -> None:
    """주요 서비스의 인정자당 기관 수 분포를 히스토그램·상자그림으로 저장한다."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "분포 그림 생성에는 matplotlib가 필요합니다. "
            "requirements-analysis.txt를 설치하세요."
        ) from exc

    preferred_codes = ["A03", "A04", "B01", "B02", "B03", "B05", "C01", "C03"]
    available = [
        code
        for code in preferred_codes
        if metrics["기관유형코드"].astype(str).eq(code).any()
    ]
    if not available:
        return
    metric_column = "인정자1000명당기관수_중앙수요"
    figure, axes = plt.subplots(
        len(available),
        2,
        figsize=(12, 3 * len(available)),
        constrained_layout=True,
    )
    if len(available) == 1:
        axes = np.asarray([axes])
    for row, code in enumerate(available):
        values = metrics.loc[
            metrics["기관유형코드"].astype(str).eq(code),
            metric_column,
        ].dropna()
        axes[row, 0].hist(values, bins=20, color="#4472C4", edgecolor="white")
        axes[row, 0].set_title(f"{code}: histogram")
        axes[row, 0].set_xlabel("institutions per 1,000 recognized people")
        axes[row, 0].set_ylabel("regions")
        axes[row, 1].boxplot(values, orientation="horizontal")
        axes[row, 1].set_title(f"{code}: boxplot")
        axes[row, 1].set_xlabel("institutions per 1,000 recognized people")
    figure.savefig(output_dir / "supply_rate_distributions.png", dpi=160)
    plt.close(figure)


def gini(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    if len(array) == 0 or np.allclose(array.sum(), 0):
        return math.nan
    if np.any(array < 0):
        raise ValueError("지니계수 입력값은 음수가 될 수 없습니다.")
    array = np.sort(array)
    index = np.arange(1, len(array) + 1)
    return float(
        (np.sum((2 * index - len(array) - 1) * array))
        / (len(array) * np.sum(array))
    )


def theil(values: Iterable[float]) -> float:
    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    mean = array.mean() if len(array) else math.nan
    if not np.isfinite(mean) or mean <= 0:
        return math.nan
    ratio = array / mean
    contributions = np.zeros_like(ratio)
    positive = ratio > 0
    contributions[positive] = ratio[positive] * np.log(ratio[positive])
    return float(np.mean(contributions))


def benjamini_hochberg(p_values: Iterable[float]) -> np.ndarray:
    """Benjamini-Hochberg 방식으로 p값의 FDR 보정값을 반환한다."""
    values = np.asarray(list(p_values), dtype=float)
    if len(values) == 0:
        return values
    if np.any(~np.isfinite(values)) or np.any((values < 0) | (values > 1)):
        raise ValueError("p값은 0~1 사이의 유한값이어야 합니다.")
    order = np.argsort(values)
    ranked = values[order]
    count = len(ranked)
    adjusted_ranked = np.minimum.accumulate(
        (ranked * count / np.arange(1, count + 1))[::-1]
    )[::-1]
    adjusted = np.empty(count)
    adjusted[order] = np.clip(adjusted_ranked, 0, 1)
    return adjusted


def safe_spearman(left: pd.Series, right: pd.Series) -> float:
    """결측을 제외한 두 변수에 변동이 있을 때만 순위상관을 계산한다."""
    pairs = pd.concat([left, right], axis=1).dropna()
    if len(pairs) < 2 or (pairs.nunique(dropna=True) < 2).any():
        return np.nan
    return float(pairs.iloc[:, 0].corr(pairs.iloc[:, 1], method="spearman"))


def scenario_summary(frame: pd.DataFrame, scenario: str) -> dict[str, float | str]:
    supply_rate = frame["배치후_인정자1000명당기관수"]
    return {
        "시나리오": scenario,
        "추가기관합계": int(frame["추가기관수"].sum()),
        "평균공급률": float(supply_rate.mean()),
        "중앙공급률": float(supply_rate.median()),
        "최솟값": float(supply_rate.min()),
        "지니계수": gini(supply_rate),
        "Theil지수": theil(supply_rate),
        "공급0지역수": int(frame["배치후기관수"].eq(0).sum()),
    }


def allocate_evenly(frame: pd.DataFrame, units: int) -> pd.Series:
    """모든 지역의 배치 수 차이가 최대 1이 되도록 정수 자원을 배분한다."""
    allocation = pd.Series(0, index=frame.index, dtype=int)
    if units <= 0:
        return allocation
    base, remainder = divmod(units, len(frame))
    allocation[:] = base
    # 정수 나머지는 결과지표와 무관한 지역키 순서로 배치한다.
    # 따라서 수요·현재 공급을 이용하는 다른 시나리오와 구분된다.
    ordered = frame.sort_values("지역키").index
    if remainder:
        allocation.loc[ordered[:remainder]] += 1
    return allocation


def allocate_demand_proportional(frame: pd.DataFrame, units: int) -> pd.Series:
    demand = frame["인정자_추정중앙"].clip(lower=0)
    if demand.sum() == 0 or units <= 0:
        return pd.Series(0, index=frame.index, dtype=int)
    raw = demand / demand.sum() * units
    allocation = np.floor(raw).astype(int)
    remainder = units - int(allocation.sum())
    if remainder:
        fractional_order = (raw - allocation).sort_values(ascending=False).index
        allocation.loc[fractional_order[:remainder]] += 1
    return allocation


def allocate_vulnerability_first(frame: pd.DataFrame, units: int) -> pd.Series:
    allocation = pd.Series(0, index=frame.index, dtype=int)
    if units <= 0:
        return allocation
    if "공급하위후보" in frame.columns and frame["공급하위후보"].any():
        candidates = frame.loc[frame["공급하위후보"]].copy()
    else:
        candidates = frame.copy()
    ordered = candidates.sort_values(
        ["인정자1000명당기관수_중앙수요", "인정자_추정중앙"],
        ascending=[True, False],
    ).index
    for index in range(units):
        allocation.loc[ordered[index % len(ordered)]] += 1
    return allocation


def allocate_equity_greedy(frame: pd.DataFrame, units: int) -> pd.Series:
    """배치할 때마다 현재 최저 공급률 지역을 다시 찾아 1단위씩 배분한다."""
    allocation = pd.Series(0, index=frame.index, dtype=int)
    for _ in range(max(0, units)):
        rates = (
            (frame["기관수"] + allocation)
            / frame["인정자_추정중앙"]
            * 1000
        )
        target = rates.idxmin()
        allocation.loc[target] += 1
    return allocation


def simulate_allocations(
    metrics: pd.DataFrame,
    service_code: str,
    units: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    service = metrics.loc[
        metrics["기관유형코드"].astype(str).eq(str(service_code))
    ].copy()
    if service.empty:
        raise ValueError(f"기관유형코드 {service_code!r}에 해당하는 자료가 없습니다.")
    if units < 0:
        raise ValueError("--additional-units는 0 이상이어야 합니다.")

    allocations = {
        "균등배분": allocate_evenly(service, units),
        "수요비례": allocate_demand_proportional(service, units),
        "취약지역우선": allocate_vulnerability_first(service, units),
        # 형평성 최소화는 기관 1개씩 현재 최저 공급률 지역에 배치하는
        # 탐욕 알고리즘의 기준안이다. 비용·운영제약 최적화가 아니다.
        "형평성최소화_탐욕기준": allocate_equity_greedy(service, units),
    }

    detail_frames = []
    summaries = []
    for name, allocation in allocations.items():
        detail = service.copy()
        detail["시나리오"] = name
        detail["추가기관수"] = allocation
        detail["배치후기관수"] = detail["기관수"] + detail["추가기관수"]
        detail["배치후_인정자1000명당기관수"] = (
            detail["배치후기관수"] / detail["인정자_추정중앙"] * 1000
        )
        if int(detail["추가기관수"].sum()) != units:
            raise AssertionError(f"{name}: 총자원 보존 검산 실패")
        detail_frames.append(detail)
        summaries.append(scenario_summary(detail, name))
    return pd.concat(detail_frames, ignore_index=True), pd.DataFrame(summaries)


def exploratory_hypotheses(
    metrics: pd.DataFrame,
    demand_growth: pd.DataFrame,
    run_inference: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    merged = metrics.merge(
        demand_growth[["지역키", "인정자증가율_2022_2025"]],
        on="지역키",
        how="left",
        validate="many_to_one",
    )
    summaries = []
    for service_code, group in merged.groupby("기관유형코드"):
        capacity_usable = group["정원지표사용가능"].all()
        summaries.append(
            {
                "기관유형코드": service_code,
                "기관유형명": group["기관유형명"].iloc[0],
                "지역수": len(group),
                "인정자증가율_중앙값": group["인정자증가율_2022_2025"].median(),
                "인정자1000명당기관수_중앙값": group[
                    "인정자1000명당기관수_중앙수요"
                ].median(),
                "기관수_중앙값": group["기관수"].median(),
                "정원_중앙값": group["정원"].median(),
                "요양보호사_중앙값": group["요양보호사"].median(),
                "기관수_정원_Spearman": (
                    safe_spearman(group["기관수"], group["정원"])
                    if capacity_usable
                    else np.nan
                ),
                "기관수_요양보호사_Spearman": safe_spearman(
                    group["기관수"], group["요양보호사"]
                ),
                "상관해석제한": (
                    "지역 단면의 기술적 연관성이다. 제공역량의 원인이나 "
                    "실제 서비스 이용 가능성을 의미하지 않는다."
                ),
            }
        )
    inference_records: list[dict[str, float | str | int]] = []
    if run_inference:
        try:
            from scipy.stats import spearmanr
        except ImportError as exc:
            raise RuntimeError(
                "--run-inference에는 scipy가 필요합니다. "
                "requirements-analysis.txt를 설치하세요."
            ) from exc
        for service_code, group in merged.groupby("기관유형코드"):
            valid = group[
                [
                    "인정자증가율_2022_2025",
                    "인정자1000명당기관수_중앙수요",
                ]
            ].dropna()
            tied_rate = (
                1
                - valid["인정자1000명당기관수_중앙수요"].nunique()
                / len(valid)
                if len(valid)
                else np.nan
            )
            if len(valid) < 30 or tied_rate > 0.50:
                inference_records.append(
                    {
                        "가설": "A",
                        "기관유형코드": service_code,
                        "검정": "제외",
                        "표본수": len(valid),
                        "통계량": np.nan,
                        "p값": np.nan,
                        "제외이유": (
                            "완전 관측쌍 30개 미만"
                            if len(valid) < 30
                            else "동률 비율 50% 초과"
                        ),
                        "해석제한": "희소서비스는 기술통계와 공급 0 비율을 우선한다.",
                    }
                )
                continue
            statistic, p_value = spearmanr(
                valid["인정자증가율_2022_2025"],
                valid["인정자1000명당기관수_중앙수요"],
            )
            inference_records.append(
                {
                    "가설": "A",
                    "기관유형코드": service_code,
                    "검정": "Spearman 순위상관",
                    "표본수": len(valid),
                    "통계량": statistic,
                    "p값": p_value,
                    "제외이유": "",
                    "해석제한": (
                        "공급 0 지역을 포함한 전국 행정자료의 탐색적 연관성이다. "
                        "인과관계 또는 실제 미충족수요를 의미하지 않는다."
                    ),
                }
            )
    inference_frame = pd.DataFrame(inference_records)
    if not inference_frame.empty:
        tested = inference_frame["p값"].notna()
        inference_frame["FDR보정p값"] = np.nan
        inference_frame["FDR_0.05기각"] = False
        if tested.any():
            p_values = inference_frame.loc[tested, "p값"].to_numpy(dtype=float)
            adjusted = benjamini_hochberg(p_values)
            inference_frame.loc[tested, "FDR보정p값"] = adjusted
            inference_frame.loc[tested, "FDR_0.05기각"] = adjusted < 0.05
    return pd.DataFrame(summaries), inference_frame


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    datasets: dict[str, pd.DataFrame] = {}
    audits = []
    for name, path in FILES.items():
        frame = coerce_numeric(read_csv(path))
        datasets[name] = frame
        audits.append(audit_dataset(name, path, frame))

    audit_frame = pd.DataFrame(asdict(result) for result in audits)
    audit_frame.to_csv(
        args.output_dir / "data_quality_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )
    if audit_frame["status"].eq("FAIL").any():
        print(audit_frame.to_string(index=False))
        print("\n필수 컬럼 또는 키 문제로 분석을 중단했습니다.", file=sys.stderr)
        return 2

    dictionary = build_variable_dictionary(datasets)
    dictionary.to_csv(
        args.output_dir / "variable_dictionary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    if args.stage == "audit":
        print(audit_frame.to_string(index=False))
        print(f"\n감사 결과: {args.output_dir}")
        return 0

    descriptions = descriptive_statistics(datasets)
    descriptions.to_csv(
        args.output_dir / "descriptive_statistics.csv",
        index=False,
        encoding="utf-8-sig",
    )
    if args.stage == "describe":
        print(descriptions.head(30).to_string(index=False))
        return 0

    crosswalk = load_crosswalk(args.crosswalk)
    metrics = prepare_current_metrics(
        datasets,
        crosswalk,
        args.minimum_join_rate,
        args.output_dir,
    )
    metrics = quantile_candidates(metrics, args.candidate_quantile)
    metrics.to_csv(
        args.output_dir / "current_region_service_metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )
    plot_supply_distributions(metrics, args.output_dir)
    if args.stage == "metrics":
        print(metrics.head(30).to_string(index=False))
        return 0

    growth = demand_growth_panel(datasets["demand_panel"], crosswalk)
    growth.to_csv(
        args.output_dir / "demand_growth_2022_2025.csv",
        index=False,
        encoding="utf-8-sig",
    )
    hypothesis_summary, inference = exploratory_hypotheses(
        metrics,
        growth,
        args.run_inference,
    )
    hypothesis_summary.to_csv(
        args.output_dir / "hypothesis_descriptive_results.csv",
        index=False,
        encoding="utf-8-sig",
    )
    inference.to_csv(
        args.output_dir / "hypothesis_inference_results.csv",
        index=False,
        encoding="utf-8-sig",
    )
    if args.stage == "hypotheses":
        print(hypothesis_summary.to_string(index=False))
        if not args.run_inference:
            print("\n추론통계는 실행하지 않았습니다. 필요 시 --run-inference를 지정하세요.")
        return 0

    if args.stage in {"simulation", "all"}:
        if not args.service_code:
            raise ValueError(
                "simulation 또는 all 단계에는 --service-code가 필요합니다."
            )
        detail, summary = simulate_allocations(
            metrics,
            args.service_code,
            args.additional_units,
        )
        detail.to_csv(
            args.output_dir / f"simulation_detail_{args.service_code}.csv",
            index=False,
            encoding="utf-8-sig",
        )
        summary.to_csv(
            args.output_dir / f"simulation_summary_{args.service_code}.csv",
            index=False,
            encoding="utf-8-sig",
        )
        print(summary.to_string(index=False))

    write_json(
        args.output_dir / "run_config.json",
        {
            "stage": args.stage,
            "crosswalk": str(args.crosswalk) if args.crosswalk else None,
            "minimum_join_rate": args.minimum_join_rate,
            "run_inference": args.run_inference,
            "service_code": args.service_code,
            "additional_units": args.additional_units,
            "candidate_quantile": args.candidate_quantile,
            "limitations": [
                "결과는 상대적 공급압력과 조건부 시나리오이다.",
                "실제 서비스 부족·미충족수요·인과효과를 의미하지 않는다.",
                "기관 상세 API 비확률표본은 모집단 추론에 사용하지 않는다.",
            ],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
