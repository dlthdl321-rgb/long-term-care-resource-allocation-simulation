import type {
  AllocationResult,
  BaselineRow,
  CoreStrategy,
  NormalizedBaselineRow,
  RegionRow,
  ResourceType,
  ServiceType,
} from "../types.ts";
import { requireNumber } from "./format.ts";

export const CORE_STRATEGIES: readonly CoreStrategy[] = [
  "수요규모 우선",
  "공급부족량 우선",
  "기관 미관측 우선",
  "지역취약성 우선",
];

function zScores(values: number[]): number[] {
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance =
    values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
  const standardDeviation = Math.sqrt(variance);
  if (!Number.isFinite(standardDeviation) || standardDeviation === 0) {
    return values.map(() => 0);
  }
  return values.map((value) => (value - mean) / standardDeviation);
}

function allocationVulnerabilityByRegion(regionRows: RegionRow[]) {
  const aging = regionRows.map((row) => requireNumber(row.aging_rate, "aging_rate"));
  const single = regionRows.map((row) =>
    requireNumber(
      row.elderly_single_household_burden,
      "elderly_single_household_burden",
    ),
  );
  const agingZ = zScores(aging);
  const singleZ = zScores(single);
  return new Map(
    regionRows.map((row, index) => [
      row.region_code,
      0.5 * agingZ[index] + 0.5 * singleZ[index],
    ]),
  );
}

function normalizeBaseline(
  row: BaselineRow,
  vulnerability: Map<string, number>,
): NormalizedBaselineRow {
  const demandValue = requireNumber(row.demand_value, "demand_value");
  if (demandValue <= 0) throw new Error("demand_value는 양수여야 합니다.");
  const currentResource = requireNumber(row.current_resource, "current_resource");
  const targetResource = requireNumber(row.target_resource, "target_resource");
  const continuousGap = requireNumber(row.continuous_gap, "continuous_gap");
  const integerNeed = requireNumber(row.integer_need, "integer_need");
  const allocationVulnerabilityScore = vulnerability.get(row.region_code);
  if (allocationVulnerabilityScore === undefined) {
    throw new Error(`${row.region_code}의 배치용 취약성 점수가 없습니다.`);
  }
  return {
    source: row,
    regionCode: row.region_code,
    service: row.service,
    resourceType: row.resource_type,
    demandValue,
    currentResource,
    targetResource,
    continuousGap,
    integerNeed,
    providerMissing: row.provider_missing === "True",
    allocationVulnerabilityScore,
  };
}

type AllocationState = NormalizedBaselineRow & {
  allocated: number;
  remainingNeed: number;
  remainingCap: number;
};

function eligible(states: AllocationState[]) {
  return states.filter((row) => row.remainingNeed > 0 && row.remainingCap > 0);
}

function apply(row: AllocationState, units: number) {
  row.allocated += units;
  row.remainingNeed -= units;
  row.remainingCap -= units;
}

function demandProportional(states: AllocationState[], budget: number) {
  let remaining = budget;
  while (remaining > 0) {
    const candidates = eligible(states);
    if (!candidates.length) break;
    const capacity = candidates.map((row) =>
      Math.min(row.remainingNeed, row.remainingCap),
    );
    const batch = Math.min(
      remaining,
      capacity.reduce((sum, value) => sum + value, 0),
    );
    if (batch <= 0) break;
    const totalDemand = candidates.reduce((sum, row) => sum + row.demandValue, 0);
    const quotas = candidates.map((row) => (row.demandValue / totalDemand) * batch);
    const allocations = quotas.map((quota, index) =>
      Math.min(Math.floor(quota), capacity[index]),
    );
    let left = batch - allocations.reduce((sum, value) => sum + value, 0);
    const order = candidates
      .map((row, index) => ({ row, index, fraction: quotas[index] - Math.floor(quotas[index]) }))
      .sort(
        (leftRow, rightRow) =>
          rightRow.fraction - leftRow.fraction ||
          rightRow.row.demandValue - leftRow.row.demandValue ||
          leftRow.row.regionCode.localeCompare(rightRow.row.regionCode),
      );
    while (left > 0) {
      let changed = false;
      for (const item of order) {
        if (left > 0 && allocations[item.index] < capacity[item.index]) {
          allocations[item.index] += 1;
          left -= 1;
          changed = true;
        }
      }
      if (!changed) break;
    }
    const placed = allocations.reduce((sum, value) => sum + value, 0);
    candidates.forEach((row, index) => apply(row, allocations[index]));
    if (!placed) break;
    remaining -= placed;
  }
  return remaining;
}

function allocateOneByOrder(
  states: AllocationState[],
  budget: number,
  compare: (left: AllocationState, right: AllocationState) => number,
) {
  let remaining = budget;
  while (remaining > 0) {
    const candidates = eligible(states).sort(compare);
    if (!candidates.length) break;
    apply(candidates[0], 1);
    remaining -= 1;
  }
  return remaining;
}

const shortageOrder = (left: AllocationState, right: AllocationState) =>
  right.remainingNeed - left.remainingNeed ||
  right.demandValue - left.demandValue ||
  left.regionCode.localeCompare(right.regionCode);

function runStrategy(
  baseline: NormalizedBaselineRow[],
  strategy: CoreStrategy,
  budget: number,
  capPerRegion: number,
) {
  const states: AllocationState[] = baseline.map((row) => ({
    ...row,
    allocated: 0,
    remainingNeed: row.integerNeed,
    remainingCap: capPerRegion,
  }));
  let remaining = budget;
  if (strategy === "수요규모 우선") {
    remaining = demandProportional(states, remaining);
  } else if (strategy === "공급부족량 우선") {
    remaining = allocateOneByOrder(states, remaining, shortageOrder);
  } else if (strategy === "기관 미관측 우선") {
    while (remaining > 0) {
      const zero = eligible(states)
        .filter((row) => row.currentResource + row.allocated === 0)
        .sort(
          (left, right) =>
            right.demandValue - left.demandValue ||
            left.regionCode.localeCompare(right.regionCode),
        );
      if (!zero.length) break;
      apply(zero[0], 1);
      remaining -= 1;
    }
    remaining = allocateOneByOrder(states, remaining, shortageOrder);
  } else {
    remaining = allocateOneByOrder(
      states,
      remaining,
      (left, right) =>
        right.allocationVulnerabilityScore - left.allocationVulnerabilityScore ||
        right.demandValue - left.demandValue ||
        left.regionCode.localeCompare(right.regionCode),
    );
  }
  return { states, remaining };
}

export function calculateAllocations({
  budget,
  capPerRegion,
  baselineRows,
  regionRows,
  visibleRegionRows,
  service,
  resourceType,
}: {
  budget: number;
  capPerRegion: number;
  baselineRows: BaselineRow[];
  regionRows: RegionRow[];
  visibleRegionRows: RegionRow[];
  service: ServiceType;
  resourceType: ResourceType;
}): AllocationResult[] {
  const visibleCodes = new Set(visibleRegionRows.map((row) => row.region_code));
  const vulnerability = allocationVulnerabilityByRegion(regionRows);
  const providerByRegion = new Map(
    baselineRows
      .filter((row) => row.service === service && row.resource_type === "기관")
      .map((row) => [row.region_code, requireNumber(row.current_resource, "provider current_resource")]),
  );
  const candidates = baselineRows
    .filter(
      (row) =>
        row.service === service &&
        row.resource_type === resourceType &&
        visibleCodes.has(row.region_code),
    )
    .map((row) => normalizeBaseline(row, vulnerability))
    .filter((row) => {
      if (row.integerNeed <= 0) return false;
      if (resourceType === "기관") return true;
      const providerCount = providerByRegion.get(row.regionCode);
      if (providerCount === undefined) {
        throw new Error(`${row.regionCode}의 기관 관측값이 없습니다.`);
      }
      return providerCount > 0;
    });
  const strategies = CORE_STRATEGIES.filter(
    (strategy) => resourceType === "기관" || strategy !== "기관 미관측 우선",
  );

  return strategies.map((strategy) => {
    const { states, remaining } = runStrategy(candidates, strategy, budget, capPerRegion);
    const changed = states.filter((row) => row.allocated > 0);
    return {
      strategy,
      items: changed.map((row) => ({ row: row.source, allocated: row.allocated })),
      allocated: budget - remaining,
      remaining,
      improvedRegions: changed.length,
      gapReduction: changed.reduce(
        (sum, row) => sum + Math.min(row.allocated, row.continuousGap),
        0,
      ),
      providerMissingReduced: changed.filter(
        (row) => row.providerMissing && row.currentResource + row.allocated > 0,
      ).length,
      targetDeficitRegionsReduced: changed.filter(
        (row) => row.continuousGap > 0 && row.targetResource - row.currentResource - row.allocated <= 0,
      ).length,
    };
  });
}
