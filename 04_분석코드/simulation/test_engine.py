"""작은 인공 데이터로 Q4-A 배치 엔진을 검증한다."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import STRATEGIES, build_baseline, evaluate_run, run_strategy


def toy_baseline(cap: int = 3) -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            {
                "region_code": "A",
                "sido_name": "테스트도",
                "sigungu_name": "가군",
                "service": "visit_care",
                "resource_type": "institution",
                "demand_value": 100,
                "current_resource": 0,
                "aging_rate": 20,
                "elderly_single_household_index": 10,
            },
            {
                "region_code": "B",
                "sido_name": "테스트도",
                "sigungu_name": "나군",
                "service": "visit_care",
                "resource_type": "institution",
                "demand_value": 200,
                "current_resource": 1,
                "aging_rate": 40,
                "elderly_single_household_index": 30,
            },
            {
                "region_code": "C",
                "sido_name": "테스트도",
                "sigungu_name": "다군",
                "service": "visit_care",
                "resource_type": "institution",
                "demand_value": 50,
                "current_resource": 1,
                "aging_rate": 30,
                "elderly_single_household_index": 20,
            },
            {
                "region_code": "D",
                "sido_name": "테스트도",
                "sigungu_name": "라군",
                "service": "visit_care",
                "resource_type": "institution",
                "demand_value": 300,
                "current_resource": 6,
                "aging_rate": 10,
                "elderly_single_household_index": 5,
            },
        ]
    )
    return build_baseline(frame, allocation_cap=cap)


class EngineTest(unittest.TestCase):
    def test_all_strategies_preserve_invariants(self) -> None:
        baseline = toy_baseline()
        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy):
                result, unallocated = run_strategy(baseline, strategy, 5)
                self.assertEqual(
                    int(result["allocated_resource"].sum()) + unallocated, 5
                )
                self.assertTrue(
                    result["allocated_resource"].le(
                        baseline["integer_need"]
                    ).all()
                )
                self.assertTrue(
                    result["allocated_resource"].le(
                        baseline["allocation_cap"]
                    ).all()
                )

    def test_zero_provider_is_allocated_first(self) -> None:
        baseline = toy_baseline()
        result, _ = run_strategy(baseline, "zero_provider_priority", 1)
        selected = result.loc[result["allocated_resource"].eq(1)]
        self.assertEqual(selected.iloc[0]["region_code"], "A")
        self.assertEqual(selected.iloc[0]["allocation_reason"], "기관 미관측 우선")

    def test_shortage_priority_tie_breaks_by_demand(self) -> None:
        baseline = toy_baseline()
        result, _ = run_strategy(baseline, "shortage_priority", 1)
        expected = (
            baseline.loc[baseline["integer_need"].gt(0)]
            .sort_values(
                ["integer_need", "demand_value", "region_code"],
                ascending=[False, False, True],
            )
            .iloc[0]["region_code"]
        )
        selected = result.loc[result["allocated_resource"].eq(1)].iloc[0]
        self.assertEqual(selected["region_code"], expected)

    def test_vulnerability_priority_uses_score(self) -> None:
        baseline = toy_baseline()
        result, _ = run_strategy(baseline, "vulnerability_priority", 1)
        expected = (
            baseline.loc[baseline["integer_need"].gt(0)]
            .sort_values(
                ["vulnerability_score", "demand_value", "region_code"],
                ascending=[False, False, True],
            )
            .iloc[0]["region_code"]
        )
        selected = result.loc[result["allocated_resource"].eq(1)].iloc[0]
        self.assertEqual(selected["region_code"], expected)

    def test_demand_proportional_reallocates_and_records_unallocated(self) -> None:
        baseline = toy_baseline(cap=1)
        result, unallocated = run_strategy(
            baseline, "demand_proportional", 20
        )
        self.assertEqual(
            int(result["allocated_resource"].sum()) + unallocated, 20
        )
        self.assertTrue(result["allocated_resource"].le(1).all())
        self.assertGreater(unallocated, 0)

    def test_evaluator_returns_primary_metrics(self) -> None:
        baseline = toy_baseline()
        result, unallocated = run_strategy(
            baseline, "shortage_priority", 3
        )
        metrics = evaluate_run(baseline, result, 3, unallocated)
        self.assertIn("continuous_gap_reduction", metrics)
        self.assertIn("lower_10pct_mean_increase", metrics)
        self.assertEqual(metrics["allocated_resource"] + unallocated, 3)

    def test_repeated_allocation_keeps_all_order_numbers(self) -> None:
        baseline = toy_baseline(cap=3)
        result, _ = run_strategy(baseline, "shortage_priority", 3)
        recorded = result.loc[
            result["allocated_resource"].gt(0), "allocation_order"
        ].str.split(",").explode()
        self.assertEqual(
            sorted(int(value) for value in recorded if value), [1, 2, 3]
        )


if __name__ == "__main__":
    unittest.main()
