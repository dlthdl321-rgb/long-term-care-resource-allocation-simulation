export type DashboardRow = Record<string, string>;

export interface RegionRow extends DashboardRow {
  region_code: string;
  sido_name: string;
  sigungu_name: string;
  urgency_rank: string;
  urgency_score: string;
  vulnerability_percentile: string;
}

export interface BaselineRow extends DashboardRow {
  region_code: string;
  service: string;
  resource_type: string;
  current_resource: string;
  target_resource: string;
  integer_need: string;
  provider_missing: string;
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
