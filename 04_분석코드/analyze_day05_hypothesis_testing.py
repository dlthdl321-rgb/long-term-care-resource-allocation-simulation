"""Day 5 가설검정 과제용 농촌 군×3개 재가서비스 분석."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from project_paths import ANALYSIS_READY_DIR, OUTPUTS_DIR


OUTPUT_DIR = OUTPUTS_DIR / "day05_hypothesis_testing"
SERVICE_CODES = {
    "방문요양": ["B01", "C01"],
    "방문간호": ["B05", "C05"],
    "주야간보호": ["B03", "C03"],
}


def bh_adjust(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg 방식으로 여러 검정의 p값을 보정한다."""
    values = np.asarray(p_values, dtype=float)
    order = np.argsort(values)
    ranked = values[order]
    adjusted = ranked * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.clip(adjusted, 0, 1)
    return result.tolist()


def bootstrap_spearman_ci(
    x: np.ndarray, y: np.ndarray, *, iterations: int = 3_000, seed: int = 20260724
) -> tuple[float, float]:
    """지역을 복원추출하여 Spearman rho의 백분위 신뢰구간을 구한다."""
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    n = len(x)
    for _ in range(iterations):
        index = rng.integers(0, n, n)
        rho = stats.spearmanr(x[index], y[index]).statistic
        if np.isfinite(rho):
            estimates.append(float(rho))
    return tuple(np.quantile(estimates, [0.025, 0.975]))


def load_panel() -> pd.DataFrame:
    population = pd.read_csv(
        ANALYSIS_READY_DIR / "elderly_population_sigungu_202606.csv",
        encoding="utf-8-sig",
    )
    households = pd.read_csv(
        ANALYSIS_READY_DIR
        / "elderly_single_person_households_sigungu_202606.csv",
        encoding="utf-8-sig",
    )
    demand = pd.read_csv(
        ANALYSIS_READY_DIR / "ltci_demand_sigungu_bounds_202605.csv",
        encoding="utf-8-sig",
    ).rename(columns={"시도": "시도명", "시군구": "시군구명"})
    demand["시도명"] = demand["시도명"].replace(
        {
            "강원도": "강원특별자치도",
            "강원": "강원특별자치도",
            "전라북도": "전북특별자치도",
            "전북": "전북특별자치도",
        }
    )
    supply = pd.read_csv(
        ANALYSIS_READY_DIR / "ltci_supply_sigungu_service_type_20260610.csv",
        encoding="utf-8-sig",
    )

    county_selection = population.loc[
        population["시군구명"].str.endswith("군", na=False),
        ["시도명", "시군구명"],
    ].copy()
    county_selection["선정여부"] = county_selection["시도명"].str.endswith(
        "도", na=False
    )
    county_selection["선정기준"] = np.where(
        county_selection["선정여부"],
        "도 소속 군",
        "광역시 소속 군으로 제외",
    )
    county_selection.to_csv(
        OUTPUT_DIR / "county_selection_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )

    rural = population.loc[
        population["시도명"].str.endswith("도", na=False)
        & population["시군구명"].str.endswith("군", na=False)
    ].copy()
    rural = rural.merge(
        households[["시도명", "시군구명", "65세이상1인세대"]],
        on=["시도명", "시군구명"],
        how="inner",
        validate="one_to_one",
    )
    rural = rural.merge(
        demand[
            [
                "시도명",
                "시군구명",
                "인정자_추정하한",
                "인정자_추정상한",
            ]
        ],
        on=["시도명", "시군구명"],
        how="inner",
        validate="one_to_one",
    )
    if len(rural) != 76:
        raise ValueError(f"도 소속 군 결합 결과가 76개가 아닙니다: {len(rural)}개")
    rural["인정자_추정중앙"] = (
        rural["인정자_추정하한"] + rural["인정자_추정상한"]
    ) / 2
    rural["고령1인세대부담지표"] = (
        rural["65세이상1인세대"] / rural["65세이상인구"] * 100
    )

    frames: list[pd.DataFrame] = []
    for service, codes in SERVICE_CODES.items():
        current = supply.loc[supply["기관유형코드"].isin(codes)].copy()
        grouped = (
            current.groupby(["시도명", "시군구명"], as_index=False)[
                ["기관수", "정원", "간호사", "간호조무사", "요양보호사"]
            ]
            .sum()
        )
        grouped["서비스"] = service
        frames.append(grouped)
    service_supply = pd.concat(frames, ignore_index=True)

    regions = rural[
        [
            "시도명",
            "시군구명",
            "총인구",
            "65세이상인구",
            "고령화율",
            "65세이상1인세대",
            "고령1인세대부담지표",
            "인정자_추정중앙",
        ]
    ]
    grid = regions.assign(_key=1).merge(
        pd.DataFrame({"서비스": list(SERVICE_CODES)}).assign(_key=1),
        on="_key",
    ).drop(columns="_key")
    panel = grid.merge(
        service_supply,
        on=["시도명", "시군구명", "서비스"],
        how="left",
        validate="one_to_one",
    )
    supply_columns = ["기관수", "정원", "간호사", "간호조무사", "요양보호사"]
    panel[supply_columns] = panel[supply_columns].fillna(0)
    panel["핵심인력"] = np.select(
        [
            panel["서비스"].eq("방문간호"),
            panel["서비스"].isin(["방문요양", "주야간보호"]),
        ],
        [
            panel["간호사"] + panel["간호조무사"],
            panel["요양보호사"],
        ],
        default=np.nan,
    )
    panel["인정자1000명당기관수"] = (
        panel["기관수"] / panel["인정자_추정중앙"] * 1000
    )
    panel["인정자1000명당핵심인력"] = (
        panel["핵심인력"] / panel["인정자_추정중앙"] * 1000
    )
    return panel


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    panel = load_panel()
    county_selection = pd.read_csv(
        OUTPUT_DIR / "county_selection_audit.csv",
        encoding="utf-8-sig",
    )
    panel.to_csv(OUTPUT_DIR / "rural_county_service_panel.csv", index=False, encoding="utf-8-sig")

    q1_rows: list[dict[str, object]] = []
    for service, current in panel.groupby("서비스", sort=False):
        for predictor in ["고령화율", "고령1인세대부담지표"]:
            for outcome in ["인정자1000명당기관수", "인정자1000명당핵심인력"]:
                x = current[predictor].to_numpy(float)
                y = current[outcome].to_numpy(float)
                result = stats.spearmanr(x, y)
                ci_low, ci_high = bootstrap_spearman_ci(x, y)
                q1_rows.append(
                    {
                        "서비스": service,
                        "취약성지표": predictor,
                        "공급지표": outcome,
                        "n": len(current),
                        "spearman_rho": float(result.statistic),
                        "p_value": float(result.pvalue),
                        "rho_ci95_low": ci_low,
                        "rho_ci95_high": ci_high,
                    }
                )
    q1_results = pd.DataFrame(q1_rows)
    q1_results["fdr_p_value"] = bh_adjust(q1_results["p_value"].tolist())
    q1_results["fdr_reject_0_05"] = q1_results["fdr_p_value"] < 0.05
    q1_results.to_csv(
        OUTPUT_DIR / "q1_vulnerability_supply_spearman.csv",
        index=False,
        encoding="utf-8-sig",
    )

    market_rows: list[dict[str, object]] = []
    for service, current in panel.groupby("서비스", sort=False):
        x = current["인정자_추정중앙"].to_numpy(float)
        y = current["기관수"].to_numpy(float)
        result = stats.spearmanr(x, y)
        ci_low, ci_high = bootstrap_spearman_ci(x, y)
        market_rows.append(
            {
                "서비스": service,
                "n": len(current),
                "spearman_rho": float(result.statistic),
                "p_value": float(result.pvalue),
                "rho_ci95_low": ci_low,
                "rho_ci95_high": ci_high,
                "기관0군수": int(current["기관수"].eq(0).sum()),
                "기관0군_인정자중앙값": float(
                    current.loc[current["기관수"].eq(0), "인정자_추정중앙"].median()
                ),
                "기관존재군_인정자중앙값": float(
                    current.loc[current["기관수"].gt(0), "인정자_추정중앙"].median()
                ),
            }
        )
    market_results = pd.DataFrame(market_rows)
    market_results["fdr_p_value"] = bh_adjust(market_results["p_value"].tolist())
    market_results["fdr_reject_0_05"] = market_results["fdr_p_value"] < 0.05
    market_results.to_csv(
        OUTPUT_DIR / "q1_market_size_institutions_spearman.csv",
        index=False,
        encoding="utf-8-sig",
    )

    q2_rows: list[dict[str, object]] = []
    for service, current in panel.groupby("서비스", sort=False):
        comparisons = [("핵심인력 공급률", current["인정자1000명당핵심인력"])]
        if service == "주야간보호":
            comparisons.append(
                ("정원 공급률", current["정원"] / current["인정자_추정중앙"] * 1000)
            )
        for capacity_name, capacity in comparisons:
            x = current["인정자1000명당기관수"].to_numpy(float)
            y = capacity.to_numpy(float)
            result = stats.spearmanr(x, y)
            ci_low, ci_high = bootstrap_spearman_ci(x, y)
            q2_rows.append(
                {
                    "서비스": service,
                    "제공역량지표": capacity_name,
                    "n": len(current),
                    "spearman_rho": float(result.statistic),
                    "p_value": float(result.pvalue),
                    "rho_ci95_low": ci_low,
                    "rho_ci95_high": ci_high,
                }
            )
    q2_results = pd.DataFrame(q2_rows)
    q2_results["fdr_p_value"] = bh_adjust(q2_results["p_value"].tolist())
    q2_results["fdr_reject_0_05"] = q2_results["fdr_p_value"] < 0.05
    q2_results.to_csv(
        OUTPUT_DIR / "q2_institution_capacity_spearman.csv",
        index=False,
        encoding="utf-8-sig",
    )

    nursing = panel.loc[panel["서비스"].eq("방문간호")].copy()

    visit_nursing = nursing["인정자1000명당기관수"].to_numpy(float)
    n = len(visit_nursing)
    mean = float(np.mean(visit_nursing))
    std = float(np.std(visit_nursing, ddof=1))
    se = float(stats.sem(visit_nursing))
    t_ci = stats.t.interval(0.95, df=n - 1, loc=mean, scale=se)
    normal_ci = stats.norm.interval(0.95, loc=mean, scale=se)
    quartile_1, quartile_3 = np.quantile(visit_nursing, [0.25, 0.75])
    iqr = quartile_3 - quartile_1
    outlier_count = int(
        ((visit_nursing < quartile_1 - 1.5 * iqr) | (visit_nursing > quartile_3 + 1.5 * iqr)).sum()
    )

    summary = {
        "panel": {
            "all_administrative_counties": int(len(county_selection)),
            "rural_counties": int(panel[["시도명", "시군구명"]].drop_duplicates().shape[0]),
            "excluded_metropolitan_counties": int((~county_selection["선정여부"]).sum()),
            "operational_definition": "시도명이 '도'로 끝나고 시군구명이 '군'으로 끝나는 지역",
            "services": int(panel["서비스"].nunique()),
            "rows": int(len(panel)),
        },
        "q1_vulnerability_supply": q1_results.to_dict(orient="records"),
        "q1_market_size_institutions": market_results.to_dict(orient="records"),
        "q2_institution_capacity": q2_results.to_dict(orient="records"),
        "q3_similar_institution_supply": {
            "status": "추가 계산 필요",
            "planned_method": "기관 공급률 차이 5%·10%·20% 이내 군 쌍의 서비스별 제공역량 절대차이 기술통계",
        },
        "q4_resource_allocation": {
            "status": "기술적 시나리오 계산 질문",
            "inference_test": False,
            "reason": "현재 결과는 반복표본이 아니라 정해진 입력과 규칙에 따른 결정론적 계산값",
        },
        "visit_nursing_mean_estimation": {
            "n": n,
            "mean": mean,
            "median": float(np.median(visit_nursing)),
            "std": std,
            "se": se,
            "skewness": float(stats.skew(visit_nursing, bias=False)),
            "outlier_count_1_5_iqr": outlier_count,
            "t_ci95": list(map(float, t_ci)),
            "normal_ci95": list(map(float, normal_ci)),
        },
    }
    (OUTPUT_DIR / "day05_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    fig, axis = plt.subplots(figsize=(8, 5))
    axis.hist(visit_nursing, bins="auto", color="#4C78A8", edgecolor="white")
    axis.axvline(mean, color="#E45756", linestyle="--", label=f"mean={mean:.2f}")
    axis.axvline(np.median(visit_nursing), color="#54A24B", linestyle="-.", label=f"median={np.median(visit_nursing):.2f}")
    axis.set_title("Visit nursing institutions per 1,000 LTCI-recognized people")
    axis.set_xlabel("Institutions per 1,000 recognized people")
    axis.set_ylabel("Rural counties")
    axis.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "visit_nursing_supply_histogram.png", dpi=160)
    plt.close(fig)

    print(q1_results.to_string(index=False))
    print(market_results.to_string(index=False))
    print(q2_results.to_string(index=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
