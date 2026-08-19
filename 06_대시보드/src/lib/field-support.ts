import { parseNumber, requireNumber } from "./format.ts";

export type DataRow = Record<string, string>;

export const FIELD_SCENARIOS = [
  { label: "현재 상태 유지", delta: 0, note: "추가 조치 없이 기준선 유지" },
  { label: "기관 1곳 신설", delta: 1, resource: "기관", note: "설치·인력 확보 가능성 별도 확인" },
  { label: "기관 1곳 폐업", delta: -1, resource: "기관", note: "공급기반 공백과 간접 악화 점검" },
  { label: "제공인력 3명 확충", delta: 3, resource: "핵심인력", note: "기관 존재 여부를 먼저 확인" },
  { label: "제공인력 3명 유출", delta: -3, resource: "핵심인력", note: "탐색기준 미만 전환 위험 점검" },
  { label: "정원 10명 확충", delta: 10, resource: "정원", service: "주야간보호", note: "주야간보호기관 존재 필요" },
];

function quantile(values: number[], p: number) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = (sorted.length - 1) * p;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (index - lower);
}

export function targetTiers(rows: DataRow[], selected: DataRow | undefined) {
  if (!selected) return [];
  const levels = rows
    .filter(
      (row) =>
        row.service === selected.service &&
        row.resource_type === selected.resource_type,
    )
    .map((row) => parseNumber(row.current_supply_level))
    .filter((value): value is number => value !== null);
  return [
    {
      name: "하위 25% 경계",
      value: quantile(levels, 0.25),
      meaning: "76개 군 하위 25% 경계",
    },
    {
      name: "중앙값 탐색기준",
      value: quantile(levels, 0.5),
      meaning: "76개 군 중앙값",
    },
    {
      name: "상위 25% 참고선",
      value: quantile(levels, 0.75),
      meaning: "76개 군 상위 25% 경계",
    },
  ];
}

export function fieldSummary(
  region: DataRow | undefined,
  selected: DataRow | undefined,
  accessRelief: number,
) {
  if (!region || !selected) return [];
  const service = region.top_shortage_service || selected.service;
  const resource =
    region.top_shortage_resource_type === "핵심인력"
      ? "서비스 제공인력"
      : region.top_shortage_resource_type || selected.resource_type;
  const providerMissing = selected.provider_missing === "True";
  return [
    `${region.sigungu_name}에서 상대적으로 가장 부족한 항목은 ${service} ${resource}입니다.`,
    providerMissing
      ? "지역 내부 기관이 확인되지 않아 신규 설치 또는 외부지역 연계 가능성을 먼저 검토해야 합니다."
      : accessRelief > 0
        ? "같은 도의 계산상 외부공급을 반영하면 부족이 일부 완화되지만 실제 이용 가능성은 확인이 필요합니다."
        : "외부공급을 반영해도 뚜렷한 완충이 확인되지 않아 지역 내부 공급기반 검토가 우선입니다.",
    `현장검토 후보 순서는 76개 군 중 ${region.urgency_rank}번째이며, 이는 지원 확정순위가 아니라 확인을 시작할 탐색용 순서입니다.`,
  ];
}

export function actionGuidance(
  selected: DataRow | undefined,
  provider: DataRow | undefined,
  accessRelief: number,
) {
  if (!selected) return [];
  const items: { signal: string; action: string; tone: string }[] = [];
  if (selected.provider_missing === "True" || provider?.provider_missing === "True") {
    items.push({
      signal: "지역 내부 기관 미관측",
      action: "신규 설치 가능성 또는 인접·같은 도 연계 가능성을 우선 검토",
      tone: "danger",
    });
  }
  const providerResource = parseNumber(provider?.current_resource);
  if (provider && provider.provider_missing !== "True" && providerResource === 0) {
    items.push({
      signal: "관측 기관수 0",
      action: "원자료의 0 정의와 기관 운영상태를 별도로 확인",
      tone: "warn",
    });
  } else if (provider && providerResource === null) {
    items.push({
      signal: "기관 관측값 확인 필요",
      action: "기관수 원자료와 결합상태를 확인한 뒤 해석",
      tone: "warn",
    });
  }
  const relativeShortage = parseNumber(selected.relative_shortage_score);
  if (selected.resource_type === "핵심인력" && relativeShortage !== null && relativeShortage > 0) {
    items.push({
      signal: "서비스 제공인력 부족",
      action: "신규 기관보다 기존 기관의 인력확보 가능성을 먼저 검토",
      tone: "warn",
    });
  }
  if (selected.resource_type === "정원" && relativeShortage !== null && relativeShortage > 0) {
    items.push({
      signal: "주야간보호 정원 부족",
      action: "기존 기관의 정원 확대 가능성과 제공인력 동반 확보 여부 검토",
      tone: "warn",
    });
  }
  if (accessRelief > 0) {
    items.push({
      signal: "외부공급 완충 가능",
      action: "광역·인접지역 공동이용과 실제 이동·수용 가능성을 검토",
      tone: "good",
    });
  }
  if (!items.length) {
    items.push({
      signal: "중앙값 탐색기준 이상",
      action: "즉시 확충보다 공급 유지와 정기 모니터링을 우선 검토",
      tone: "good",
    });
  }
  return items;
}

export function reliabilityLabel(
  selected: DataRow | undefined,
  rankStable: boolean,
) {
  if (!selected) return { level: "확인 필요", reason: "지역을 선택하세요." };
  if (selected.provider_missing === "True")
    return {
      level: "제한적 해석",
      reason: "기관 미관측값을 0으로 처리한 결과가 포함됩니다.",
    };
  if (!rankStable)
    return {
      level: "민감도 주의",
      reason: "목표 또는 가중치 변화에 따라 우선순위가 달라질 수 있습니다.",
    };
  return {
    level: "비교 가능",
    reason: "필수 기준선 자료가 있으며 기본 비교에서 사용할 수 있습니다.",
  };
}

export function comparePreset(
  selected: DataRow | undefined,
  delta: number,
) {
  if (!selected) return null;
  const current = requireNumber(selected.current_resource, "current_resource");
  const demand = requireNumber(selected.demand_value, "demand_value");
  const target = requireNumber(selected.target_resource, "target_resource");
  const targetSupply = requireNumber(selected.target_supply_level, "target_supply_level");
  const after = Math.max(0, current + delta);
  const gapBefore = Math.max(0, target - current);
  const gapAfter = Math.max(0, target - after);
  if (demand <= 0) throw new Error("demand_value는 양수여야 합니다.");
  const supplyAfter = (after / demand) * 1000;
  const shortageAfter =
    targetSupply > 0
      ? 1 - Math.min(1, supplyAfter / targetSupply)
      : 0;
  return {
    after,
    gapAfter,
    gapChange: gapAfter - gapBefore,
    shortageAfter,
    stateAfter: gapAfter <= 1e-9 ? "탐색기준 이상" : "탐색기준 미만",
  };
}
