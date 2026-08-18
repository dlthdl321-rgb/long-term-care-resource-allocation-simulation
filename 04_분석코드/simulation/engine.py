"""Q4-A 기준선, 배치전략, 성과평가와 불변조건 검증."""

from __future__ import annotations

import math
from typing import Callable

import numpy as np
import pandas as pd


STRATEGIES = (
    "demand_proportional",
    "shortage_priority",
    "zero_provider_priority",
    "vulnerability_priority",
)


def _require_columns(frame: pd.DataFrame, columns: set[str]) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {missing}")


def _zscore(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    std = numeric.std(ddof=0)
    if not np.isfinite(std) or math.isclose(std, 0):
        return pd.Series(0.0, index=values.index)
    return (numeric - numeric.mean()) / std


def build_baseline(
    frame: pd.DataFrame,
    *,
    target_scenario: str = "county_median",
    demand_scenario: str = "ltci_midpoint",
    aging_weight: float = 0.5,
    single_household_weight: float = 0.5,
    allocation_cap: int = 2,
) -> pd.DataFrame:
    """표준 입력에서 고정 목표와 필요량을 가진 불변 기준선을 만든다."""
    _require_columns(
        frame,
        {
            "region_code",
            "sido_name",
            "sigungu_name",
            "service",
            "resource_type",
            "demand_value",
            "current_resource",
            "aging_rate",
            "elderly_single_household_index",
        },
    )
    if allocation_cap < 0:
        raise ValueError("allocation_cap은 0 이상이어야 합니다.")
    if not math.isclose(aging_weight + single_household_weight, 1.0):
        raise ValueError("취약성 가중치 합은 1이어야 합니다.")

    baseline = frame.copy(deep=True)
    numeric_columns = [
        "demand_value",
        "current_resource",
        "aging_rate",
        "elderly_single_household_index",
    ]
    baseline[numeric_columns] = baseline[numeric_columns].apply(
        pd.to_numeric, errors="coerce"
    )
    if baseline["region_code"].duplicated().any():
        raise ValueError("기준선에는 지역코드가 중복될 수 없습니다.")
    if baseline["demand_value"].isna().any() or baseline["demand_value"].le(0).any():
        raise ValueError("수요값은 결측이 없는 양수여야 합니다.")
    if baseline["current_resource"].isna().any() or baseline[
        "current_resource"
    ].lt(0).any():
        raise ValueError("현재 공급량은 결측이 없는 0 이상 값이어야 합니다.")

    baseline["demand_scenario"] = demand_scenario
    baseline["current_supply_rate"] = (
        baseline["current_resource"] / baseline["demand_value"] * 1000
    )
    if target_scenario != "county_median":
        raise ValueError("MVP는 county_median 목표만 지원합니다.")
    target_rate = float(baseline["current_supply_rate"].median())
    baseline["target_scenario"] = target_scenario
    baseline["target_supply_rate"] = target_rate
    baseline["target_resource"] = (
        target_rate * baseline["demand_value"] / 1000
    )
    baseline["continuous_gap"] = (
        baseline["target_resource"] - baseline["current_resource"]
    ).clip(lower=0)
    baseline["integer_need"] = (
        np.ceil(baseline["target_resource"]) - baseline["current_resource"]
    ).clip(lower=0).astype(int)
    baseline["provider_missing"] = baseline["current_resource"].eq(0)
    baseline["eligible_for_allocation"] = baseline["integer_need"].gt(0)
    baseline["allocation_cap"] = int(allocation_cap)
    baseline["vulnerability_score"] = (
        aging_weight * _zscore(baseline["aging_rate"])
        + single_household_weight
        * _zscore(baseline["elderly_single_household_index"])
    )
    return baseline.sort_values("region_code").reset_index(drop=True)


def _initial_state(baseline: pd.DataFrame) -> pd.DataFrame:
    state = baseline.copy(deep=True)
    state["allocated_resource"] = 0
    state["remaining_need"] = state["integer_need"].astype(int)
    state["remaining_cap"] = state["allocation_cap"].astype(int)
    state["allocation_order"] = ""
    state["allocation_reason"] = ""
    return state


def _eligible(state: pd.DataFrame) -> pd.DataFrame:
    return state.loc[
        state["eligible_for_allocation"]
        & state["remaining_need"].gt(0)
        & state["remaining_cap"].gt(0)
    ]


def _apply(
    state: pd.DataFrame,
    allocation: pd.Series,
    reason: str,
    next_order: int,
) -> int:
    positive = allocation[allocation.gt(0)].astype(int)
    for index, units in positive.items():
        state.loc[index, "allocated_resource"] += units
        state.loc[index, "remaining_need"] -= units
        state.loc[index, "remaining_cap"] -= units
        orders = list(range(next_order, next_order + units))
        existing_orders = str(state.loc[index, "allocation_order"])
        new_orders = ",".join(map(str, orders))
        state.loc[index, "allocation_order"] = ",".join(
            value for value in [existing_orders, new_orders] if value
        )
        existing_reason = str(state.loc[index, "allocation_reason"])
        if reason not in existing_reason.split(" | "):
            state.loc[index, "allocation_reason"] = " | ".join(
                value for value in [existing_reason, reason] if value
            )
        next_order += units
    return next_order


def _demand_proportional(
    state: pd.DataFrame, remaining: int, next_order: int
) -> tuple[int, int]:
    while remaining > 0:
        candidates = _eligible(state)
        if candidates.empty:
            break
        batch = min(remaining, int(candidates["remaining_need"].clip(
            upper=candidates["remaining_cap"]
        ).sum()))
        if batch <= 0:
            break
        shares = candidates["demand_value"] / candidates["demand_value"].sum()
        quotas = shares * batch
        capacity = candidates[["remaining_need", "remaining_cap"]].min(axis=1)
        allocation = np.floor(quotas).astype(int).clip(upper=capacity)
        left = batch - int(allocation.sum())
        order = (
            candidates.assign(fraction=quotas - np.floor(quotas))
            .sort_values(
                ["fraction", "demand_value", "region_code"],
                ascending=[False, False, True],
            )
            .index
        )
        while left > 0:
            changed = False
            for index in order:
                if allocation.loc[index] < capacity.loc[index] and left > 0:
                    allocation.loc[index] += 1
                    left -= 1
                    changed = True
            if not changed:
                break
        placed = int(allocation.sum())
        if placed == 0:
            break
        next_order = _apply(
            state, allocation, "수요비례 최대잔여·재배분", next_order
        )
        remaining -= placed
    return remaining, next_order


def _allocate_one_by_order(
    state: pd.DataFrame,
    remaining: int,
    next_order: int,
    columns: list[str],
    ascending: list[bool],
    reason: str,
) -> tuple[int, int]:
    while remaining > 0:
        candidates = _eligible(state)
        if candidates.empty:
            break
        selected = candidates.sort_values(columns, ascending=ascending).index[0]
        allocation = pd.Series(0, index=state.index, dtype=int)
        allocation.loc[selected] = 1
        next_order = _apply(state, allocation, reason, next_order)
        remaining -= 1
    return remaining, next_order


def _shortage_priority(
    state: pd.DataFrame, remaining: int, next_order: int
) -> tuple[int, int]:
    return _allocate_one_by_order(
        state,
        remaining,
        next_order,
        ["remaining_need", "demand_value", "region_code"],
        [False, False, True],
        "잔여 정수형 필요량 최대",
    )


def _zero_provider_priority(
    state: pd.DataFrame, remaining: int, next_order: int
) -> tuple[int, int]:
    while remaining > 0:
        candidates = _eligible(state)
        zero = candidates.loc[
            (candidates["current_resource"] + candidates["allocated_resource"]).eq(0)
        ]
        if zero.empty:
            break
        selected = zero.sort_values(
            ["demand_value", "region_code"], ascending=[False, True]
        ).index[0]
        allocation = pd.Series(0, index=state.index, dtype=int)
        allocation.loc[selected] = 1
        next_order = _apply(state, allocation, "기관 미관측 우선", next_order)
        remaining -= 1
    return _shortage_priority(state, remaining, next_order)


def _vulnerability_priority(
    state: pd.DataFrame, remaining: int, next_order: int
) -> tuple[int, int]:
    return _allocate_one_by_order(
        state,
        remaining,
        next_order,
        ["vulnerability_score", "demand_value", "region_code"],
        [False, False, True],
        "취약성 점수 우선",
    )


_RUNNERS: dict[str, Callable[[pd.DataFrame, int, int], tuple[int, int]]] = {
    "demand_proportional": _demand_proportional,
    "shortage_priority": _shortage_priority,
    "zero_provider_priority": _zero_provider_priority,
    "vulnerability_priority": _vulnerability_priority,
}


def run_strategy(
    baseline: pd.DataFrame, strategy: str, resource_budget: int
) -> tuple[pd.DataFrame, int]:
    """기준선 사본에서 한 전략을 실행하고 지역별 전후 상태를 반환한다."""
    if strategy not in _RUNNERS:
        raise ValueError(f"지원하지 않는 전략입니다: {strategy}")
    if resource_budget < 0:
        raise ValueError("resource_budget은 0 이상이어야 합니다.")
    state = _initial_state(baseline)
    unallocated, _ = _RUNNERS[strategy](state, int(resource_budget), 1)
    state["strategy"] = strategy
    state["baseline_resource"] = state["current_resource"]
    state["after_resource"] = (
        state["baseline_resource"] + state["allocated_resource"]
    )
    state["after_supply_rate"] = (
        state["after_resource"] / state["demand_value"] * 1000
    )
    state["after_gap"] = (
        state["target_resource"] - state["after_resource"]
    ).clip(lower=0)
    state["after_integer_need"] = (
        np.ceil(state["target_resource"]) - state["after_resource"]
    ).clip(lower=0).astype(int)
    state["after_target_deficit"] = state["after_gap"].gt(0)
    state["after_provider_missing"] = state["after_resource"].eq(0)
    validate_run(baseline, state, resource_budget, unallocated)
    return state, int(unallocated)


def gini(values: pd.Series) -> float:
    array = np.sort(pd.to_numeric(values, errors="coerce").dropna().to_numpy())
    if len(array) == 0 or math.isclose(float(array.sum()), 0):
        return math.nan
    ranks = np.arange(1, len(array) + 1)
    return float(
        np.sum((2 * ranks - len(array) - 1) * array)
        / (len(array) * array.sum())
    )


def evaluate_run(
    baseline: pd.DataFrame,
    after: pd.DataFrame,
    resource_budget: int,
    unallocated: int,
) -> dict[str, float | int | str]:
    lower_count = max(1, math.ceil(len(after) * 0.1))
    before_lower = baseline["current_supply_rate"].nsmallest(lower_count).mean()
    after_lower = after["after_supply_rate"].nsmallest(lower_count).mean()
    allocated = int(after["allocated_resource"].sum())
    benefited = int(
        after.loc[after["allocated_resource"].gt(0), "demand_value"].sum()
    )
    continuous_reduction = float(
        baseline["continuous_gap"].sum() - after["after_gap"].sum()
    )
    return {
        "strategy": str(after["strategy"].iloc[0]),
        "resource_budget": int(resource_budget),
        "allocated_resource": allocated,
        "unallocated_resource": int(unallocated),
        "continuous_gap_before": float(baseline["continuous_gap"].sum()),
        "continuous_gap_after": float(after["after_gap"].sum()),
        "continuous_gap_reduction": continuous_reduction,
        "integer_need_reduction": int(
            baseline["integer_need"].sum() - after["after_integer_need"].sum()
        ),
        "target_deficit_regions_reduced": int(
            baseline["continuous_gap"].gt(0).sum()
            - after["after_target_deficit"].sum()
        ),
        "zero_provider_regions_reduced": int(
            baseline["provider_missing"].sum()
            - after["after_provider_missing"].sum()
        ),
        "lower_10pct_mean_before": float(before_lower),
        "lower_10pct_mean_after": float(after_lower),
        "lower_10pct_mean_increase": float(after_lower - before_lower),
        "benefited_demand": benefited,
        "minimum_supply_after": float(after["after_supply_rate"].min()),
        "q1_supply_after": float(after["after_supply_rate"].quantile(0.25)),
        "iqr_supply_after": float(
            after["after_supply_rate"].quantile(0.75)
            - after["after_supply_rate"].quantile(0.25)
        ),
        "gini_after": gini(after["after_supply_rate"]),
        "continuous_gap_reduction_per_unit": (
            continuous_reduction / allocated if allocated else math.nan
        ),
    }


def validate_run(
    baseline: pd.DataFrame,
    after: pd.DataFrame,
    resource_budget: int,
    unallocated: int,
) -> None:
    """모든 전략이 지켜야 하는 공통 불변조건을 검사한다."""
    allocated = after["allocated_resource"]
    checks = {
        "자원총량 보존": int(allocated.sum()) + int(unallocated)
        == int(resource_budget),
        "배치량 비음수": allocated.ge(0).all(),
        "배치후 등식": np.allclose(
            after["after_resource"],
            baseline["current_resource"] + allocated,
        ),
        "필요량 상한": allocated.le(baseline["integer_need"]).all(),
        "지역 배치상한": allocated.le(baseline["allocation_cap"]).all(),
        "배치후 필요량 비음수": after["after_integer_need"].ge(0).all(),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AssertionError(f"시뮬레이션 불변조건 실패: {failed}")
