"""통계 실행 전 환경·관측수·결측·변동성·민감도 준비상태를 검사한다."""

from __future__ import annotations

import importlib.metadata
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import analyze_ltci_resource_allocation as analysis


ROOT = analysis.PROJECT_ROOT
CONFIG_PATH = ROOT / "config" / "statistical_config.json"
OUTPUT_DIR = ROOT / "outputs" / "statistical_readiness"


def add_check(
    checks: list[dict[str, object]],
    item: str,
    status: str,
    observed: object,
    criterion: str,
    action: str = "",
) -> None:
    checks.append(
        {
            "점검항목": item,
            "상태": status,
            "관측값": observed,
            "판정기준": criterion,
            "필요조치": action,
        }
    )


def package_versions() -> dict[str, str]:
    packages = ["numpy", "pandas", "scipy", "matplotlib"]
    return {name: importlib.metadata.version(name) for name in packages}


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    checks: list[dict[str, object]] = []

    versions = {
        "python": platform.python_version(),
        **package_versions(),
    }
    (OUTPUT_DIR / "environment_versions.json").write_text(
        json.dumps(versions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    add_check(
        checks,
        "통계 패키지 로딩",
        "PASS",
        json.dumps(versions, ensure_ascii=False),
        "Python·NumPy·pandas·SciPy·Matplotlib 버전 기록",
    )

    datasets = {
        name: analysis.coerce_numeric(analysis.read_csv(path))
        for name, path in analysis.FILES.items()
    }
    metrics = analysis.prepare_current_metrics(
        datasets, None, 0.99, OUTPUT_DIR
    )
    metrics = analysis.quantile_candidates(metrics, 0.25)
    expected_regions = int(config["current_region_count"])
    region_count = metrics["지역키"].nunique()
    add_check(
        checks,
        "분석지역 수",
        "PASS" if region_count == expected_regions else "BLOCK",
        region_count,
        f"{expected_regions}개",
    )

    primary = config["primary_descriptive_metric"]
    lower, upper = config["sensitivity_metrics"]
    service_profiles = []
    for (code, name), group in metrics.groupby(
        ["기관유형코드", "기관유형명"], sort=True
    ):
        valid_primary = group[primary].replace([np.inf, -np.inf], np.nan).dropna()
        paired = group[[lower, upper]].replace([np.inf, -np.inf], np.nan).dropna()
        rank_correlation = (
            spearmanr(paired[lower], paired[upper]).statistic
            if len(paired) >= 2
            else np.nan
        )
        q1, q3 = valid_primary.quantile([0.25, 0.75])
        iqr = q3 - q1
        upper_fence = q3 + 1.5 * iqr
        lower_fence = q1 - 1.5 * iqr
        outlier_count = int(
            ((valid_primary < lower_fence) | (valid_primary > upper_fence)).sum()
        )
        tied_rate = (
            1 - valid_primary.nunique() / len(valid_primary)
            if len(valid_primary)
            else np.nan
        )
        service_profiles.append(
            {
                "기관유형코드": code,
                "기관유형명": name,
                "지역수": group["지역키"].nunique(),
                "핵심지표유효값수": len(valid_primary),
                "핵심지표결측률": group[primary].isna().mean(),
                "평균": valid_primary.mean(),
                "중앙값": valid_primary.median(),
                "표준편차": valid_primary.std(ddof=1),
                "1사분위수": q1,
                "3사분위수": q3,
                "사분위범위": iqr,
                "IQR이상치수": outlier_count,
                "동률비율": tied_rate,
                "하한상한순위상관": rank_correlation,
                "공급0지역수": int(group["기관수"].eq(0).sum()),
                "정원지표사용상태": group["정원지표사용상태"].iloc[0],
                "권장통계방법": (
                    "기술통계·공급0비율 중심"
                    if tied_rate
                    > float(config["maximum_tie_rate_for_rank_inference"])
                    else (
                        "하한·중앙·상한 별도 분석"
                        if rank_correlation
                        < float(config["minimum_sensitivity_rank_correlation"])
                        else "기술통계·민감도·탐색적 순위상관"
                    )
                ),
            }
        )
    profiles = pd.DataFrame(service_profiles)
    profiles.to_csv(
        OUTPUT_DIR / "service_statistical_profiles.csv",
        index=False,
        encoding="utf-8-sig",
    )

    incomplete_services = int(profiles["지역수"].ne(expected_regions).sum())
    zero_variance_services = int(profiles["표준편차"].fillna(0).eq(0).sum())
    insufficient_services = int(
        profiles["핵심지표유효값수"]
        .lt(int(config["minimum_complete_pairs"]))
        .sum()
    )
    unstable_services = int(
        profiles["하한상한순위상관"]
        .lt(float(config["minimum_sensitivity_rank_correlation"]))
        .sum()
    )
    high_tie_services = int(
        profiles["동률비율"]
        .gt(float(config["maximum_tie_rate_for_rank_inference"]))
        .sum()
    )

    add_check(
        checks,
        "서비스별 지역 관측 완전성",
        "PASS" if incomplete_services == 0 else "BLOCK",
        f"미충족 서비스 {incomplete_services}개",
        f"각 서비스 {expected_regions}개 지역",
    )
    add_check(
        checks,
        "핵심지표 분산",
        "PASS" if zero_variance_services == 0 else "BLOCK",
        f"분산 0 서비스 {zero_variance_services}개",
        "통계 비교 대상은 분산이 0보다 큼",
    )
    add_check(
        checks,
        "완전 관측쌍",
        "PASS" if insufficient_services == 0 else "WARN",
        f"{config['minimum_complete_pairs']}개 미만 서비스 {insufficient_services}개",
        f"서비스별 최소 {config['minimum_complete_pairs']}개",
        "부족한 서비스는 추론통계 제외",
    )
    add_check(
        checks,
        "수요 하한·상한 순위 안정성",
        "PASS" if unstable_services == 0 else "WARN",
        f"Spearman 0.95 미만 서비스 {unstable_services}개",
        "서비스별 하한·상한 지역순위 상관 ≥0.95",
        "불안정 서비스는 후보 확정 금지",
    )
    add_check(
        checks,
        "동률 비율",
        "WARN" if high_tie_services > 0 else "PASS",
        f"동률 50% 초과 서비스 {high_tie_services}개",
        "순위검정의 동률 정도 확인",
        "동률이 많은 희소서비스는 기술통계 중심",
    )

    service_tests = metrics["기관유형코드"].nunique()
    add_check(
        checks,
        "다중검정 계획",
        "PASS",
        f"최대 서비스별 검정 {service_tests}개",
        config["multiple_testing"],
        "보정 전·후 p값과 효과크기를 함께 저장",
    )
    add_check(
        checks,
        "추론통계 해석 범위",
        "PASS",
        config["inference_policy"],
        "행정자료는 기술통계·민감도 우선",
        "통계적 유의성을 인과효과로 표현 금지",
    )
    add_check(
        checks,
        "난수 재현성",
        "PASS",
        config["random_seed"],
        "부트스트랩·모의실험 난수 시드 고정",
    )

    result = pd.DataFrame(checks)
    result.to_csv(
        OUTPUT_DIR / "statistical_readiness_checks.csv",
        index=False,
        encoding="utf-8-sig",
    )
    blocked = int(result["상태"].eq("BLOCK").sum())
    summary = {
        "검사수": len(result),
        "PASS": int(result["상태"].eq("PASS").sum()),
        "WARN": int(result["상태"].eq("WARN").sum()),
        "BLOCK": blocked,
        "통계실행준비": blocked == 0,
        "추론통계실행여부": "미실행",
    }
    (OUTPUT_DIR / "statistical_readiness_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(result.to_string(index=False))
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if blocked == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
