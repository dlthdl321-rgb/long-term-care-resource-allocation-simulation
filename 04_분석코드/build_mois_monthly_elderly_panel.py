"""수집한 행정안전부 원본에서 시군구 월별 고령인구 패널과 검산표를 만든다."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from project_paths import ANALYSIS_READY_DIR, OUTPUTS_DIR, RAW_DIR

SOURCE_DIR = RAW_DIR / "monthly_panel" / "mois_age_population"
OUTPUT_DIR = ANALYSIS_READY_DIR
AUDIT_DIR = OUTPUTS_DIR / "data_quality"
MONTH_RE = re.compile(r"^(\d{4})년(\d{2})월_계_총인구수$")
CODE_RE = re.compile(r"\((\d{10})\)\s*$")


def number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")


def main() -> None:
    files = sorted(SOURCE_DIR.glob("mois_age_population_sigungu_*.csv"))
    if not files:
        raise FileNotFoundError(f"원본 CSV가 없습니다: {SOURCE_DIR}")

    frames: list[pd.DataFrame] = []
    file_audit: list[dict[str, object]] = []
    for path in files:
        raw = pd.read_csv(path, encoding="cp949", dtype=str)
        area_col = raw.columns[0]
        codes = raw[area_col].str.extract(CODE_RE, expand=False)
        sigungu_mask = codes.str.endswith("00000", na=False) & ~codes.str.endswith("00000000", na=False)
        sigungu = raw.loc[sigungu_mask].copy()
        sigungu_codes = codes.loc[sigungu_mask]
        months = [
            f"{match.group(1)}{match.group(2)}"
            for col in raw.columns
            if (match := MONTH_RE.match(col))
        ]

        if len(months) != 3 or len(set(months)) != 3:
            raise ValueError(f"{path.name}: 월 컬럼이 정확히 3개가 아닙니다: {months}")
        if sigungu_codes.duplicated().any():
            raise ValueError(f"{path.name}: 시군구 코드 중복이 있습니다.")

        for month in months:
            month_label = f"{month[:4]}년{month[4:]}월"
            age_columns = {
                age: f"{month_label}_계_{age}세" if age < 100 else f"{month_label}_계_100세 이상"
                for age in range(65, 101)
            }
            missing = [column for column in age_columns.values() if column not in sigungu]
            if missing:
                raise ValueError(f"{path.name}: 고령인구 계산 컬럼 누락: {missing[:3]}")

            elderly_65 = sum((number(sigungu[col]) for col in age_columns.values()))
            elderly_75 = sum((number(sigungu[col]) for age, col in age_columns.items() if age >= 75))
            elderly_85 = sum((number(sigungu[col]) for age, col in age_columns.items() if age >= 85))
            total = number(sigungu[f"{month_label}_계_총인구수"])
            frame = pd.DataFrame(
                {
                    "base_month": pd.to_datetime(month, format="%Y%m"),
                    "region_code": sigungu_codes.to_numpy(),
                    "region_name_raw": sigungu[area_col].str.replace(CODE_RE, "", regex=True).str.strip().to_numpy(),
                    "total_population": total.to_numpy(),
                    "population_65_plus": elderly_65.to_numpy(),
                    "population_75_plus": elderly_75.to_numpy(),
                    "population_85_plus": elderly_85.to_numpy(),
                }
            )
            frame["share_65_plus_pct"] = frame["population_65_plus"] / frame["total_population"] * 100
            frames.append(frame)

        file_audit.append(
            {
                "file": path.name,
                "rows_raw": len(raw),
                "sigungu_rows": int(sigungu_mask.sum()),
                "months": "|".join(months),
            }
        )

    panel = pd.concat(frames, ignore_index=True)
    panel = panel.sort_values(["base_month", "region_code"]).reset_index(drop=True)
    observed_months = pd.DatetimeIndex(panel["base_month"].drop_duplicates().sort_values())
    expected_months = pd.date_range(observed_months.min(), observed_months.max(), freq="MS")
    missing_months = expected_months.difference(observed_months)
    duplicate_keys = int(panel.duplicated(["base_month", "region_code"]).sum())
    invalid_counts = int(
        (
            (panel["population_85_plus"] > panel["population_75_plus"])
            | (panel["population_75_plus"] > panel["population_65_plus"])
            | (panel["population_65_plus"] > panel["total_population"])
        ).sum()
    )

    audit = {
        "source_files": len(files),
        "observed_month_count": len(observed_months),
        "period_start": observed_months.min().strftime("%Y-%m"),
        "period_end": observed_months.max().strftime("%Y-%m"),
        "missing_months": [value.strftime("%Y-%m") for value in missing_months],
        "panel_rows": len(panel),
        "unique_region_codes": int(panel["region_code"].nunique()),
        "duplicate_month_region_keys": duplicate_keys,
        "invalid_population_order_rows": invalid_counts,
        "null_counts": {column: int(value) for column, value in panel.isna().sum().items()},
        "pass": not missing_months.size and duplicate_keys == 0 and invalid_counts == 0,
    }
    if not audit["pass"]:
        raise RuntimeError(f"패널 검산 실패: {audit}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "monthly_elderly_population_sigungu_2016_2025.csv"
    panel.to_csv(output, index=False, encoding="utf-8-sig", date_format="%Y-%m")
    pd.DataFrame(file_audit).to_csv(
        AUDIT_DIR / "mois_monthly_population_file_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )
    (AUDIT_DIR / "mois_monthly_population_panel_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    print(f"output={output}")


if __name__ == "__main__":
    main()
