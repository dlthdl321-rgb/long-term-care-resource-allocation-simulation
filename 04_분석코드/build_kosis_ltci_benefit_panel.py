"""KOSIS 원본 CSV에서 시군구×연도×급여종류 결과 패널을 만든다."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from project_paths import ANALYSIS_READY_DIR, OUTPUTS_DIR, RAW_DIR

SOURCE_DIR = RAW_DIR / "causal_panel" / "kosis_ltci_benefit" / "csv"
OUTPUT = ANALYSIS_READY_DIR / "annual_ltci_benefit_sigungu_2013_2024.csv"
AUDIT = OUTPUTS_DIR / "data_quality" / "kosis_ltci_benefit_panel_audit.json"


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def main() -> None:
    frames: list[pd.DataFrame] = []
    for path in sorted(SOURCE_DIR.glob("*.csv")):
        raw = pd.read_csv(path, encoding="cp949", skiprows=2, dtype=str)
        raw["is_sigungu"] = raw["시·군·구별"].str.startswith(" ", na=False)
        raw["province"] = raw["시·군·구별"].where(~raw["is_sigungu"]).ffill().str.strip()
        selected = raw.loc[
            raw["is_sigungu"]
            & raw["등급별"].eq("계")
            & raw["성별"].eq("계")
        ].copy()
        selected["sigungu"] = selected["시·군·구별"].str.strip()
        selected["year"] = pd.to_numeric(selected["시점"], errors="raise").astype(int)
        frames.append(
            pd.DataFrame(
                {
                    "year": selected["year"],
                    "province": selected["province"],
                    "sigungu": selected["sigungu"],
                    "kosis_region_code": selected["C시·군·구별"].str.lstrip("'"),
                    "service_type": selected["급여종류별"],
                    "benefit_users": numeric(selected["급여이용수급자 (명)"]),
                    "provider_count_used": numeric(selected["급여제공기관 (개)"]),
                    "service_days": numeric(selected["급여제공일수 (일)"]),
                    "benefit_cost_thousand_krw": numeric(selected["급여비용 (천원)"]),
                    "nhis_payment_thousand_krw": numeric(selected["공단부담금 (천원)"]),
                }
            )
        )

    panel = pd.concat(frames, ignore_index=True)
    panel = panel.sort_values(["year", "province", "sigungu", "service_type"]).reset_index(drop=True)
    duplicates = int(panel.duplicated(["year", "kosis_region_code", "service_type"]).sum())
    years = sorted(panel["year"].unique().tolist())
    audit = {
        "source_files": len(frames),
        "years": years,
        "continuous_years": years == list(range(min(years), max(years) + 1)),
        "rows": len(panel),
        "unique_region_codes": int(panel["kosis_region_code"].nunique()),
        "service_types": sorted(panel["service_type"].dropna().unique().tolist()),
        "duplicate_year_region_service": duplicates,
        "null_counts": {column: int(value) for column, value in panel.isna().sum().items()},
    }
    if not audit["continuous_years"] or duplicates:
        raise RuntimeError(f"패널 검산 실패: {audit}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    print(f"output={OUTPUT}")


if __name__ == "__main__":
    main()
