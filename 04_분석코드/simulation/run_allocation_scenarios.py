"""설정파일로 선택한 서비스의 기관 5개 대표 최소 시뮬레이션 실행기."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import STRATEGIES, build_baseline, evaluate_run, run_strategy


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METRICS = (
    PROJECT_ROOT / "03_데이터" / "outputs" / "analysis"
    / "current_region_service_metrics.csv"
)
DEFAULT_CONFIG = (
    PROJECT_ROOT / "03_데이터" / "config" / "representative_allocation_scenario.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "03_데이터" / "outputs" / "representative_visit_nursing_allocation"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_version() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_service_counties(metrics_path: Path, config: dict) -> pd.DataFrame:
    metrics = pd.read_csv(metrics_path)
    service_codes = set(config["service_codes"])
    county_rows = metrics.loc[
        metrics["분석_시도명"].astype(str).str.endswith("도")
        & metrics["분석_시군구명"].astype(str).str.endswith("군")
    ].copy()
    if county_rows.empty:
        raise ValueError("도 소속 군 기준틀을 만들 자료가 없습니다.")
    county_base = (
        county_rows.groupby(
            ["지역키", "분석_시도명", "분석_시군구명", "시설_지역코드"],
            as_index=False,
        )
        .agg(
            demand_value=("인정자_추정중앙", "first"),
            total_population=("총인구", "first"),
            elderly_population=("65세이상인구", "first"),
            elderly_single_households=("65세이상1인세대", "first"),
        )
    )
    if len(county_base) != 76:
        raise ValueError(
            f"도 소속 군 기준틀이 76개가 아닙니다: {len(county_base)}개"
        )

    service_rows = county_rows.loc[
        county_rows["기관유형코드"].astype(str).isin(service_codes)
    ]
    if service_rows.empty:
        raise ValueError(
            f"도 소속 군의 {config['service']} 자료가 없습니다."
        )
    service_supply = (
        service_rows.groupby("지역키", as_index=False)
        .agg(current_resource=("기관수", "sum"))
    )
    grouped = county_base.merge(
        service_supply,
        on="지역키",
        how="left",
        validate="one_to_one",
    )
    grouped["current_resource"] = grouped["current_resource"].fillna(0)
    if grouped["current_resource"].lt(0).any():
        raise ValueError("기관 수는 음수가 될 수 없습니다.")
    grouped["aging_rate"] = (
        grouped["elderly_population"] / grouped["total_population"] * 100
    )
    grouped["elderly_single_household_index"] = (
        grouped["elderly_single_households"]
        / grouped["elderly_population"]
        * 100
    )
    return grouped.rename(
        columns={
            "시설_지역코드": "region_code",
            "분석_시도명": "sido_name",
            "분석_시군구명": "sigungu_name",
        }
    ).assign(
        service=config["service"],
        resource_type=config["resource_type"],
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    source = load_service_counties(args.metrics, config)
    weights = config["vulnerability_weights"]
    baseline = build_baseline(
        source,
        target_scenario=config["target_scenario"],
        demand_scenario=config["demand_scenario"],
        aging_weight=weights["aging_rate"],
        single_household_weight=weights["elderly_single_household_index"],
        allocation_cap=config["allocation_cap"],
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    baseline.to_csv(
        args.output_dir / "baseline_diagnosis.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(
        [
            {
                "region_count": len(baseline),
                "service": config["service"],
                "resource_type": config["resource_type"],
                "target_supply_rate": baseline["target_supply_rate"].iloc[0],
                "current_resource_total": baseline["current_resource"].sum(),
                "continuous_gap_total": baseline["continuous_gap"].sum(),
                "integer_need_total": baseline["integer_need"].sum(),
                "target_deficit_regions": baseline["continuous_gap"].gt(0).sum(),
                "provider_missing_regions": baseline["provider_missing"].sum(),
            }
        ]
    ).to_csv(
        args.output_dir / "baseline_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    run_id_prefix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifests: list[dict] = []
    details: list[pd.DataFrame] = []
    metrics: list[dict] = []
    unallocated_rows: list[dict] = []
    for strategy in STRATEGIES:
        run_id = f"{run_id_prefix}_{config['service']}_institution_{strategy}"
        result, unallocated = run_strategy(
            baseline, strategy, int(config["resource_budget"])
        )
        result.insert(0, "run_id", run_id)
        details.append(result)
        metrics.append(
            {"run_id": run_id, **evaluate_run(
                baseline,
                result,
                int(config["resource_budget"]),
                unallocated,
            )}
        )
        unallocated_rows.append(
            {
                "run_id": run_id,
                "strategy": strategy,
                "unallocated_resource": unallocated,
            }
        )
        manifests.append(
            {
                "run_id": run_id,
                "created_at_utc": run_id_prefix,
                "region_scope": config["region_scope"],
                "service": config["service"],
                "resource_type": config["resource_type"],
                "strategy": strategy,
                "demand_scenario": config["demand_scenario"],
                "target_scenario": config["target_scenario"],
                "target_value": float(baseline["target_supply_rate"].iloc[0]),
                "resource_budget": config["resource_budget"],
                "allocation_cap": config["allocation_cap"],
                "vulnerability_weights": json.dumps(
                    weights, ensure_ascii=False, sort_keys=True
                ),
                "random_seed": config["random_seed"],
                "code_version": git_version(),
                "input_sha256": sha256(args.metrics),
                "config_sha256": sha256(args.config),
            }
        )

    all_details = pd.concat(details, ignore_index=True)
    all_details.to_csv(
        args.output_dir / "allocation_detail.csv",
        index=False,
        encoding="utf-8-sig",
    )
    before_after_columns = [
        "run_id",
        "region_code",
        "sido_name",
        "sigungu_name",
        "service",
        "resource_type",
        "strategy",
        "demand_value",
        "baseline_resource",
        "allocated_resource",
        "after_resource",
        "current_supply_rate",
        "after_supply_rate",
        "continuous_gap",
        "after_gap",
        "integer_need",
        "after_integer_need",
        "provider_missing",
        "after_provider_missing",
        "allocation_order",
        "allocation_reason",
    ]
    all_details[before_after_columns].to_csv(
        args.output_dir / "region_before_after.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(metrics).to_csv(
        args.output_dir / "scenario_metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(manifests).to_csv(
        args.output_dir / "run_manifest.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(unallocated_rows).to_csv(
        args.output_dir / "unallocated_resources.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print(f"baseline_rows={len(baseline)}")
    print(f"target_rate={baseline['target_supply_rate'].iloc[0]:.6f}")
    print(f"output_dir={args.output_dir}")


if __name__ == "__main__":
    main()
