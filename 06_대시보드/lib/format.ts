export const num = (value: string | undefined) => Number(value || 0);

export const fmt = (value: number, digits = 1) =>
  new Intl.NumberFormat("ko-KR", { maximumFractionDigits: digits }).format(value);

export const pct = (value: number) => `${fmt(value * 100, 1)}%`;

export const resourceUnit = (resourceType: string) =>
  resourceType === "기관" ? "개소" : "명";

export const formatResourceAmount = (
  value: number,
  resourceType: string,
  digits = 0,
) => `${fmt(value, digits)}${resourceUnit(resourceType)}`;
