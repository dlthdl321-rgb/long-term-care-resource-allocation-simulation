import assert from "node:assert/strict";
import test from "node:test";

import {
  actionGuidance,
  comparePreset,
  targetTiers,
} from "../src/lib/field-support.ts";

test("observed zero and missing provider values remain distinct", () => {
  const selected = { resource_type: "기관", relative_shortage_score: "0" };
  const observedZero = actionGuidance(
    selected,
    { provider_missing: "False", current_resource: "0" },
    0,
  );
  assert.ok(observedZero.some(({ signal }) => signal === "관측 기관수 0"));
  assert.ok(!observedZero.some(({ signal }) => signal === "지역 내부 기관 미관측"));

  const missingValue = actionGuidance(
    selected,
    { provider_missing: "False", current_resource: "" },
    0,
  );
  assert.ok(missingValue.some(({ signal }) => signal === "기관 관측값 확인 필요"));
  assert.ok(!missingValue.some(({ signal }) => signal === "관측 기관수 0"));
});

test("target tiers exclude missing values instead of converting them to zero", () => {
  const rows = [
    { service: "방문간호", resource_type: "기관", current_supply_level: "" },
    { service: "방문간호", resource_type: "기관", current_supply_level: "2" },
  ];
  const tiers = targetTiers(rows, rows[1]);
  assert.deepEqual(tiers.map(({ value }) => value), [2, 2, 2]);
});

test("scenario comparison rejects missing required numeric inputs", () => {
  assert.throws(
    () =>
      comparePreset(
        {
          current_resource: "",
          demand_value: "100",
          target_resource: "2",
          target_supply_level: "20",
        },
        1,
      ),
    /current_resource/,
  );
});
