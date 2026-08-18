import type { BaselineRow, RegionRow } from "../types";
import { num } from "./format";

export type AllocationResult = {
  strategy: string;
  items: { row: BaselineRow; allocated: number }[];
  allocated: number;
  remaining: number;
  improvedRegions: number;
  gapReduction: number;
};

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
  service: string;
  resourceType: string;
}): AllocationResult[] {
  const strategies = [
    "수요규모 우선",
    "공급부족량 우선",
    ...(resourceType === "기관" ? ["기관 미관측 우선"] : []),
    "지역취약성 우선",
    "종합 탐색점수 우선",
  ];
  const visibleRegionCodes = new Set(
    visibleRegionRows.map((region) => region.region_code),
  );
  const candidates = baselineRows.filter((row) => {
    if (
      row.service !== service ||
      row.resource_type !== resourceType ||
      num(row.integer_need) <= 0 ||
      !visibleRegionCodes.has(row.region_code)
    ) {
      return false;
    }
    if (resourceType === "기관") return true;
    return (
      num(
        baselineRows.find(
          (providerRow) =>
            providerRow.region_code === row.region_code &&
            providerRow.service === service &&
            providerRow.resource_type === "기관",
        )?.current_resource,
      ) > 0
    );
  });
  const regionByCode = new Map(
    regionRows.map((region) => [region.region_code, region]),
  );
  const score = (strategy: string, row: BaselineRow) => {
    const region = regionByCode.get(row.region_code);
    if (strategy === "수요규모 우선") return num(row.demand_value);
    if (strategy === "공급부족량 우선") return num(row.integer_need);
    if (strategy === "기관 미관측 우선")
      return row.provider_missing === "True" ? 1 : 0;
    if (strategy === "지역취약성 우선")
      return num(region?.vulnerability_percentile);
    return 1000 - num(region?.urgency_rank);
  };

  return strategies.map((strategy) => {
    let remaining = budget;
    const items: AllocationResult["items"] = [];
    [...candidates]
      .sort((left, right) => score(strategy, right) - score(strategy, left))
      .forEach((row) => {
        if (remaining <= 0) return;
        const allocated = Math.min(
          remaining,
          capPerRegion,
          Math.ceil(num(row.integer_need)),
        );
        if (allocated > 0) {
          items.push({ row, allocated });
          remaining -= allocated;
        }
      });

    return {
      strategy,
      items,
      allocated: budget - remaining,
      remaining,
      improvedRegions: items.length,
      gapReduction: items.reduce(
        (sum, item) =>
          sum + Math.min(item.allocated, num(item.row.continuous_gap)),
        0,
      ),
    };
  });
}
