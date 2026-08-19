import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { calculateAllocations, CORE_STRATEGIES } from "../src/lib/allocation.ts";
import { parseNumber, requireNumber } from "../src/lib/format.ts";

function parseCsv(source) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    if (character === '"' && quoted && source[index + 1] === '"') {
      field += '"';
      index += 1;
    } else if (character === '"') quoted = !quoted;
    else if (character === "," && !quoted) {
      row.push(field);
      field = "";
    } else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && source[index + 1] === "\n") index += 1;
      row.push(field);
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      field = "";
    } else field += character;
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  const [headers, ...values] = rows;
  return values.map((valuesRow) =>
    Object.fromEntries(headers.map((header, index) => [header, valuesRow[index] ?? ""])),
  );
}

const strategyNames = {
  demand_proportional: "수요규모 우선",
  shortage_priority: "공급부족량 우선",
  zero_provider_priority: "기관 미관측 우선",
  vulnerability_priority: "지역취약성 우선",
};

test("canonical Python representative scenario and TypeScript allocations stay identical", async () => {
  const [baseline, regions, allocationCsv, metricsCsv] = await Promise.all([
    readFile(new URL("../public/data/baseline.json", import.meta.url), "utf8").then(JSON.parse),
    readFile(new URL("../public/data/regions.json", import.meta.url), "utf8").then(JSON.parse),
    readFile(
      new URL(
        "../../03_데이터/outputs/representative_visit_nursing_allocation/allocation_detail.csv",
        import.meta.url,
      ),
      "utf8",
    ).then(parseCsv),
    readFile(
      new URL(
        "../../03_데이터/outputs/representative_visit_nursing_allocation/scenario_metrics.csv",
        import.meta.url,
      ),
      "utf8",
    ).then(parseCsv),
  ]);

  assert.deepEqual(CORE_STRATEGIES, Object.values(strategyNames));
  const actual = calculateAllocations({
    budget: 5,
    capPerRegion: 2,
    baselineRows: baseline,
    regionRows: regions,
    visibleRegionRows: regions,
    service: "방문간호",
    resourceType: "기관",
  });

  for (const metric of metricsCsv) {
    const label = strategyNames[metric.strategy];
    const result = actual.find((candidate) => candidate.strategy === label);
    assert.ok(result, `${label} 결과가 있어야 합니다.`);
    const expectedAllocations = new Map(
      allocationCsv
        .filter((row) => row.strategy === metric.strategy && Number(row.allocated_resource) > 0)
        .map((row) => [row.region_code, Number(row.allocated_resource)]),
    );
    assert.deepEqual(
      new Map(result.items.map((item) => [item.row.region_code, item.allocated])),
      expectedAllocations,
      `${label} 지역별 배치량`,
    );
    assert.equal(result.allocated, Number(metric.allocated_resource));
    assert.equal(result.remaining, Number(metric.unallocated_resource));
    assert.equal(result.providerMissingReduced, Number(metric.zero_provider_regions_reduced));
    assert.equal(result.targetDeficitRegionsReduced, Number(metric.target_deficit_regions_reduced));
    assert.equal(
      result.items.reduce((sum, item) => sum + Number(item.row.demand_value), 0),
      Number(metric.benefited_demand),
      `${label} 배치 대상지역 잠재수요 합계`,
    );
    assert.ok(
      Math.abs(result.gapReduction - Number(metric.continuous_gap_reduction)) < 1e-9,
      `${label} 연속 격차 감소량`,
    );
  }
});

test("published hypothesis result counts remain canonical", async () => {
  const summary = JSON.parse(
    (await readFile(
      new URL(
        "../../03_데이터/outputs/hypothesis_testing/hypothesis_summary.json",
        import.meta.url,
      ),
      "utf8",
    )).replace(/\bNaN\b/g, "null"),
  );
  assert.equal(summary.panel.rural_counties, 76);
  assert.equal(summary.q1_vulnerability_supply.length, 12);
  assert.equal(
    summary.q1_vulnerability_supply.filter((row) => row.fdr_reject_0_05).length,
    0,
  );
  assert.equal(summary.q2_institution_capacity.length, 4);
});

test("numeric parsing preserves missing values and real zero", () => {
  for (const value of [undefined, null, "", "  ", "invalid"]) {
    assert.equal(parseNumber(value), null);
  }
  assert.equal(parseNumber(0), 0);
  assert.equal(parseNumber("0"), 0);
  assert.throws(() => requireNumber(undefined, "target"), /target/);
});
