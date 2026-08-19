import type { BaselineRow, TimelinePoint } from "../types";
import { requireNumber } from "./format";

export function buildTimelineScenario({
  baseline,
  horizon,
  demandGrowth,
  demandAcceleration,
  supplyGrowth,
  initialResourceChange,
  annualResourceChange,
}: {
  baseline?: BaselineRow;
  horizon: number;
  demandGrowth: number;
  demandAcceleration: number;
  supplyGrowth: number;
  initialResourceChange: number;
  annualResourceChange: number;
}): TimelinePoint[] {
  if (!baseline) return [];
  let projectedDemand = requireNumber(baseline.demand_value, "demand_value");
  if (projectedDemand <= 0) throw new Error("demand_value는 양수여야 합니다.");
  const currentResource = requireNumber(baseline.current_resource, "current_resource");
  const targetSupplyLevel = requireNumber(
    baseline.target_supply_level,
    "target_supply_level",
  );

  return Array.from({ length: horizon + 1 }, (_, yearIndex) => {
    const demandGrowthRate =
      yearIndex === 0
        ? 0
        : demandGrowth + demandAcceleration * (yearIndex - 1);
    if (yearIndex > 0) projectedDemand *= 1 + demandGrowthRate / 100;

    const baselineResource =
      currentResource *
      Math.pow(1 + supplyGrowth / 100, yearIndex);
    const scenarioResource = Math.max(
      0,
      baselineResource +
        initialResourceChange +
        annualResourceChange * yearIndex,
    );
    const targetResource = (targetSupplyLevel * projectedDemand) / 1000;
    const baselineGap = Math.max(0, targetResource - baselineResource);
    const scenarioGap = Math.max(0, targetResource - scenarioResource);
    const baselineSupplyLevel = (baselineResource / projectedDemand) * 1000;
    const scenarioSupplyLevel = (scenarioResource / projectedDemand) * 1000;
    const shortage = (supplyLevel: number) =>
      targetSupplyLevel > 0
        ? 1 - Math.min(1, supplyLevel / targetSupplyLevel)
        : 0;

    return {
      year: 2026 + yearIndex,
      demand: projectedDemand,
      demandGrowthRate,
      baselineResource,
      scenarioResource,
      baselineGap,
      scenarioGap,
      baselineShortage: shortage(baselineSupplyLevel),
      scenarioShortage: shortage(scenarioSupplyLevel),
    };
  });
}
