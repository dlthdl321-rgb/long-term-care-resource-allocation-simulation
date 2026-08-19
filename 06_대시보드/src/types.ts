export type ServiceType = "방문요양" | "방문간호" | "주야간보호";
export type ResourceType = "기관" | "핵심인력" | "정원";
export type CoreStrategy =
  | "수요규모 우선"
  | "공급부족량 우선"
  | "기관 미관측 우선"
  | "지역취약성 우선";

export type DashboardRow = Record<string, string>;

export interface RegionRow extends DashboardRow {
  region_code: string;
  sido_name: string;
  sigungu_name: string;
  aging_rate: string;
  elderly_single_household_burden: string;
  urgency_rank: string;
  urgency_score: string;
  vulnerability_percentile: string;
}

export interface BaselineRow extends DashboardRow {
  region_code: string;
  service: ServiceType;
  resource_type: ResourceType;
  demand_value: string;
  current_resource: string;
  target_resource: string;
  continuous_gap: string;
  integer_need: string;
  provider_missing: "True" | "False";
}

export interface NormalizedBaselineRow {
  source: BaselineRow;
  regionCode: string;
  service: ServiceType;
  resourceType: ResourceType;
  demandValue: number;
  currentResource: number;
  targetResource: number;
  continuousGap: number;
  integerNeed: number;
  providerMissing: boolean;
  allocationVulnerabilityScore: number;
}

export interface AllocationItem {
  row: BaselineRow;
  allocated: number;
}

export interface AllocationResult {
  strategy: CoreStrategy;
  items: AllocationItem[];
  allocated: number;
  remaining: number;
  improvedRegions: number;
  gapReduction: number;
  providerMissingReduced: number;
  targetDeficitRegionsReduced: number;
}

export interface QualityRow extends DashboardRow {
  check_name: string;
  status: string;
}

export type TimelinePoint = {
  year: number;
  demand: number;
  demandGrowthRate: number;
  baselineResource: number;
  scenarioResource: number;
  baselineGap: number;
  scenarioGap: number;
  baselineShortage: number;
  scenarioShortage: number;
};
