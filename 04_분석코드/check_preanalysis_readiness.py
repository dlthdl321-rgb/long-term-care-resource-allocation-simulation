"""분석 시작 전 데이터·전처리 준비상태를 Python으로 종합 점검한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import analyze_ltci_resource_allocation as analysis


OUTPUT_DIR = analysis.PROJECT_ROOT / "outputs" / "readiness"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(
    records: list[dict[str, object]],
    category: str,
    item: str,
    status: str,
    observed: object,
    criterion: str,
    action: str = "",
) -> None:
    records.append(
        {
            "범주": category,
            "점검항목": item,
            "상태": status,
            "관측값": observed,
            "판정기준": criterion,
            "필요조치": action,
        }
    )


def normalized_panel_coverage(
    frame: pd.DataFrame,
    province: str,
    district: str,
    source: str,
    expected_regions: set[str],
) -> pd.DataFrame:
    normalized = analysis.standardize_region_columns(
        frame, province, district, source, None
    )
    normalized["기준일"] = pd.to_datetime(normalized["기준일"], errors="coerce")
    coverage = (
        normalized.groupby("지역키", as_index=False)
        .agg(
            관측연도수=("기준일", lambda values: values.dt.year.nunique()),
            최초연도=("기준일", lambda values: values.dt.year.min()),
            최종연도=("기준일", lambda values: values.dt.year.max()),
        )
    )
    coverage = coverage.loc[coverage["지역키"].isin(expected_regions)].copy()
    missing = expected_regions - set(coverage["지역키"])
    if missing:
        coverage = pd.concat(
            [
                coverage,
                pd.DataFrame(
                    {
                        "지역키": sorted(missing),
                        "관측연도수": 0,
                        "최초연도": np.nan,
                        "최종연도": np.nan,
                    }
                ),
            ],
            ignore_index=True,
        )
    return coverage


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    manifest = []
    datasets: dict[str, pd.DataFrame] = {}

    for name, path in analysis.FILES.items():
        frame = analysis.coerce_numeric(analysis.read_csv(path))
        datasets[name] = frame
        audit = analysis.audit_dataset(name, path, frame)
        manifest.append(
            {
                "데이터셋": name,
                "파일": str(path.relative_to(analysis.PROJECT_ROOT)),
                "바이트": path.stat().st_size,
                "SHA256": sha256(path),
                "행": len(frame),
                "열": len(frame.columns),
                "기준일최소": audit.date_min,
                "기준일최대": audit.date_max,
            }
        )
        check(
            records,
            "파일·스키마",
            f"{name} 필수 컬럼",
            "PASS" if audit.status != "FAIL" else "BLOCK",
            audit.note or "필수 컬럼 확인",
            "필수 컬럼과 키가 모두 존재",
        )
        check(
            records,
            "파일·스키마",
            f"{name} 원본키 중복",
            "PASS" if audit.duplicate_keys == 0 else "BLOCK",
            audit.duplicate_keys,
            "중복키 0건",
        )

    pd.DataFrame(manifest).to_csv(
        OUTPUT_DIR / "input_file_manifest_sha256.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # 동일 입력으로 전처리를 두 번 실행하여 핵심 결과가 같은지 확인한다.
    run1_dir = OUTPUT_DIR / "run1"
    run2_dir = OUTPUT_DIR / "run2"
    run1_dir.mkdir(exist_ok=True)
    run2_dir.mkdir(exist_ok=True)
    metrics1 = analysis.prepare_current_metrics(datasets, None, 0.99, run1_dir)
    metrics2 = analysis.prepare_current_metrics(datasets, None, 0.99, run2_dir)
    sort_keys = ["지역키", "기관유형코드"]
    compare_columns = [
        "지역키",
        "기관유형코드",
        "기관수",
        "정원",
        "사회복지사",
        "간호사",
        "간호조무사",
        "요양보호사",
        "인정자_추정중앙",
    ]
    left = metrics1[compare_columns].sort_values(sort_keys).reset_index(drop=True)
    right = metrics2[compare_columns].sort_values(sort_keys).reset_index(drop=True)
    reproducible = left.equals(right)
    check(
        records,
        "재현성",
        "동일 입력 2회 전처리 결과",
        "PASS" if reproducible else "BLOCK",
        reproducible,
        "핵심 컬럼 완전 일치",
    )

    metrics = analysis.quantile_candidates(metrics1, 0.25)
    metrics.to_csv(
        OUTPUT_DIR / "readiness_metrics_snapshot.csv",
        index=False,
        encoding="utf-8-sig",
    )
    region_count = metrics["지역키"].nunique()
    service_count = metrics["기관유형코드"].nunique()
    duplicate_count = int(metrics.duplicated(sort_keys).sum())
    expected_rows = region_count * service_count
    check(
        records,
        "분석단위",
        "지역×서비스 완전격자",
        "PASS" if len(metrics) == expected_rows else "BLOCK",
        f"{len(metrics):,}/{expected_rows:,}행",
        "지역 수×서비스 수와 행 수 일치",
    )
    check(
        records,
        "분석단위",
        "전처리 후 지역×서비스 중복",
        "PASS" if duplicate_count == 0 else "BLOCK",
        duplicate_count,
        "중복 0건",
    )

    value_columns = [
        "기관수",
        "정원",
        "사회복지사",
        "간호사",
        "간호조무사",
        "물리치료사",
        "작업치료사",
        "요양보호사",
    ]
    total_differences = {}
    for column in value_columns:
        raw_total = pd.to_numeric(
            datasets["supply_current"][column], errors="coerce"
        ).fillna(0).sum()
        processed_total = pd.to_numeric(
            metrics[column], errors="coerce"
        ).fillna(0).sum()
        total_differences[column] = float(processed_total - raw_total)
    totals_preserved = all(
        np.isclose(difference, 0) for difference in total_differences.values()
    )
    check(
        records,
        "총량검산",
        "공급 집계 전후 총량",
        "PASS" if totals_preserved else "BLOCK",
        json.dumps(total_differences, ensure_ascii=False),
        "기관·정원·직종별 차이 0",
    )

    denominator_checks = {
        "인정자_추정중앙": int(metrics["인정자_추정중앙"].le(0).sum()),
        "75세이상인구": int(metrics["75세이상인구"].le(0).sum()),
        "65세이상1인세대": int(metrics["65세이상1인세대"].le(0).sum()),
    }
    check(
        records,
        "지표산식",
        "0 이하 분모",
        "PASS" if sum(denominator_checks.values()) == 0 else "BLOCK",
        json.dumps(denominator_checks, ensure_ascii=False),
        "모든 핵심 분모가 양수",
    )
    numeric_metrics = metrics.select_dtypes(include=[np.number])
    infinite_count = int(np.isinf(numeric_metrics.to_numpy()).sum())
    check(
        records,
        "지표산식",
        "무한값",
        "PASS" if infinite_count == 0 else "BLOCK",
        infinite_count,
        "무한값 0건",
    )

    demand = datasets["demand_current"]
    suppressed = int(demand["인정자_비공개셀수"].sum())
    total_lower = float(demand["인정자_추정하한"].sum())
    total_upper = float(demand["인정자_추정상한"].sum())
    uncertainty_width = total_upper - total_lower
    uncertainty_rate = uncertainty_width / ((total_lower + total_upper) / 2)
    check(
        records,
        "불확실성",
        "인정자 비공개값 범위",
        "WARN" if suppressed > 0 else "PASS",
        (
            f"비공개셀 {suppressed:,}개, 전국 하한 {total_lower:,.0f}, "
            f"상한 {total_upper:,.0f}, 범위폭/중앙 {uncertainty_rate:.2%}"
        ),
        "하한·중앙·상한 민감도 필수",
        "단일 인정자 값으로 확정하지 않음",
    )

    current_demand = analysis.standardize_region_columns(
        datasets["demand_current"], "시도", "시군구", "demand", None
    )
    current_demand = current_demand.loc[
        current_demand["인정자_추정상한"].gt(0)
        & ~current_demand["지역키"].isin(analysis.OBSOLETE_DEMAND_REGIONS)
    ]
    expected_regions = set(current_demand["지역키"])
    panels = {
        "demand": normalized_panel_coverage(
            datasets["demand_panel"], "시도", "시군구", "demand", expected_regions
        ),
        "population": normalized_panel_coverage(
            datasets["population_panel"],
            "시도명",
            "시군구명",
            "population",
            expected_regions,
        ),
        "single_household": normalized_panel_coverage(
            datasets["single_household_panel"],
            "시도명",
            "시군구명",
            "single_household",
            expected_regions,
        ),
    }
    for name, coverage in panels.items():
        incomplete = int(coverage["관측연도수"].ne(4).sum())
        check(
            records,
            "패널완전성",
            f"{name} 2022~2025 관측",
            "PASS" if incomplete == 0 else "WARN",
            f"4개년 미충족 지역 {incomplete}개",
            "각 분석지역 4개년",
            "행정구역 변경지역은 현행 시 단위 재집계",
        )

    current_dates = {
        "수요": pd.to_datetime(datasets["demand_current"]["자료기준"]).max(),
        "공급": pd.to_datetime(datasets["supply_current"]["자료기준"]).max(),
        "인구": pd.to_datetime(datasets["population_current"]["기준연월"]).max(),
        "1인세대": pd.to_datetime(
            datasets["single_household_current"]["기준연월"]
        ).max(),
    }
    date_span = (max(current_dates.values()) - min(current_dates.values())).days
    check(
        records,
        "시점정합성",
        "현재자료 기준일 차이",
        "PASS" if date_span <= 31 else "WARN",
        f"{date_span}일; " + ", ".join(
            f"{name}={date.date()}" for name, date in current_dates.items()
        ),
        "최대 31일 이내",
    )

    rules = pd.read_csv(run1_dir / "service_metric_rules.csv", encoding="utf-8-sig")
    conditional_services = int(
        rules["정원지표사용상태"].eq("조건부_정원자료부족").sum()
    )
    non_applicable_services = int(
        rules["정원지표사용상태"].eq("비적용").sum()
    )
    check(
        records,
        "서비스규칙",
        "정원지표 사용 제한",
        "WARN",
        (
            f"조건부 {conditional_services}개 유형, "
            f"정원 비적용 {non_applicable_services}개 유형"
        ),
        "서비스별 규칙 적용",
        "정원 사용가능 유형만 정원지표 계산",
    )

    missing_external = [
        "2026년 현재 현원",
        "대기자·이용거절",
        "고유 FTE·결원",
        "이동시간·송영권역",
        "지역별 비용·운영제약",
    ]
    check(
        records,
        "외부자료",
        "실제 부족·현실 배치 검증자료",
        "WARN",
        ", ".join(missing_external),
        "공개자료에 없는 항목",
        "현장검증 전 확정 배치·인과효과 표현 금지",
    )

    result = pd.DataFrame(records)
    result.to_csv(
        OUTPUT_DIR / "preanalysis_readiness_checks.csv",
        index=False,
        encoding="utf-8-sig",
    )
    summary = result["상태"].value_counts().to_dict()
    blocking = int((result["상태"] == "BLOCK").sum())
    summary_payload = {
        "검사수": len(result),
        "상태별": summary,
        "분석진행가능": blocking == 0,
        "주의": (
            "WARN은 데이터 삭제 사유가 아니라 민감도·사용 제한·추가 확인 항목이다."
        ),
    }
    (OUTPUT_DIR / "preanalysis_readiness_summary.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    warning_rows = result.loc[result["상태"].eq("WARN")]
    markdown_lines = [
        "# 분석 전 준비상태 자동 점검 결과",
        "",
        "- 실행 도구: `04_분석코드/check_preanalysis_readiness.py`",
        f"- 전체 검사: {len(result)}개",
        f"- 통과: {int((result['상태'] == 'PASS').sum())}개",
        f"- 주의: {int((result['상태'] == 'WARN').sum())}개",
        f"- 중단: {blocking}개",
        f"- 분석 진행 가능: {'예' if blocking == 0 else '아니오'}",
        "",
        "## 추가로 관리해야 할 주의사항",
        "",
        "| 점검항목 | 관측값 | 필요한 조치 |",
        "| --- | --- | --- |",
    ]
    for _, row in warning_rows.iterrows():
        markdown_lines.append(
            f"| {row['점검항목']} | {row['관측값']} | {row['필요조치']} |"
        )
    markdown_lines.extend(
        [
            "",
            "## 판정",
            "",
            "현재 데이터와 전처리 코드는 상대적 공급압력 지표와 조건부 "
            "자원배치 시뮬레이션을 시작할 준비가 됐다. 다만 비공개 인정자 값은 "
            "하한·중앙·상한 민감도로 계산하고, 정원지표는 사용가능 서비스에만 "
            "적용한다. 최신 현원·대기·FTE·이동·비용 자료가 없으므로 실제 부족과 "
            "현실의 최적 배치를 확정하지 않는다.",
            "",
        ]
    )
    (OUTPUT_DIR / "preanalysis_readiness_report.md").write_text(
        "\n".join(markdown_lines),
        encoding="utf-8",
    )
    print(result.to_string(index=False))
    print("\n", json.dumps(summary_payload, ensure_ascii=False, indent=2))
    return 0 if blocking == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
