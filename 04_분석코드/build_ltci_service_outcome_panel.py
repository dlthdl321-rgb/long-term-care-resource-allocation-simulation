"""장기요양 급여 패널에서 재가·시설 서비스 결과지표를 파생한다.

이 자료의 이용자 수는 연간 해당 급여 이용자이며 신규 시설입소자나 대기자가 아니다.
서비스 간 중복 이용이 가능하므로 서비스별 이용자 합계를 고유 이용자로 해석하지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from project_paths import ANALYSIS_READY_DIR, OUTPUTS_DIR

SOURCE = ANALYSIS_READY_DIR / "annual_ltci_benefit_sigungu_2013_2024.csv"
OUTPUT = ANALYSIS_READY_DIR / "annual_ltci_service_outcomes_sigungu_2013_2024.csv"
AUDIT = OUTPUTS_DIR / "data_quality" / "ltci_service_outcome_panel_audit.json"

HOME_SERVICES = ["방문요양", "방문목욕", "방문간호", "주야간보호", "단기보호", "복지용구", "통합재가서비스"]
FACILITY_SERVICES = [
    "노인요양시설",
    "노인요양공동생활가정",
    "노인요양시설(구법)",
    "노인전문요양시설(구법)",
    "노인요양시설(단기보호전환)",
]


def main() -> None:
    source = pd.read_csv(SOURCE, encoding="utf-8-sig")
    keys = ["year", "province", "sigungu", "kosis_region_code"]

    total = (
        source.loc[source["service_type"].eq("계"), keys + ["benefit_users"]]
        .rename(columns={"benefit_users": "unique_benefit_users_total"})
        .copy()
    )
    home = (
        source.loc[source["service_type"].isin(HOME_SERVICES)]
        .groupby(keys, as_index=False)
        .agg(
            home_service_user_sum=("benefit_users", "sum"),
            home_service_days=("service_days", "sum"),
            home_provider_count_sum=("provider_count_used", "sum"),
        )
    )
    facility = (
        source.loc[source["service_type"].isin(FACILITY_SERVICES)]
        .groupby(keys, as_index=False)
        .agg(
            facility_service_user_sum=("benefit_users", "sum"),
            facility_service_days=("service_days", "sum"),
            facility_provider_count_sum=("provider_count_used", "sum"),
        )
    )
    panel = total.merge(home, on=keys, how="outer").merge(facility, on=keys, how="outer")
    panel["facility_user_share_proxy_pct"] = (
        panel["facility_service_user_sum"] / panel["unique_benefit_users_total"] * 100
    )
    panel["home_user_share_proxy_pct"] = (
        panel["home_service_user_sum"] / panel["unique_benefit_users_total"] * 100
    )
    panel = panel.sort_values(["year", "province", "sigungu"]).reset_index(drop=True)

    audit = {
        "rows": len(panel),
        "years": sorted(panel["year"].dropna().astype(int).unique().tolist()),
        "unique_region_codes": int(panel["kosis_region_code"].nunique()),
        "duplicate_year_region": int(panel.duplicated(["year", "kosis_region_code"]).sum()),
        "warning": (
            "서비스별 이용자는 중복될 수 있으므로 home/facility user sum은 고유 인원이 아니다. "
            "facility_user_share_proxy_pct는 시설 신규입소율이 아닌 연간 시설급여 이용자 비중 대체지표다."
        ),
    }
    if audit["duplicate_year_region"]:
        raise RuntimeError(f"패널 키 중복: {audit}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    print(f"output={OUTPUT}")


if __name__ == "__main__":
    main()
