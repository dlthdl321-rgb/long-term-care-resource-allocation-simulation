import type { ResourceType } from "../types.ts";

export function parseNumber(value: unknown): number | null {
  if (
    value === null ||
    value === undefined ||
    (typeof value === "string" && value.trim() === "")
  ) return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function numberOrZero(value: unknown): number {
  return parseNumber(value) ?? 0;
}

export function requireNumber(value: unknown, field: string): number {
  const parsed = parseNumber(value);
  if (parsed === null) throw new Error(`${field} 값이 없거나 숫자가 아닙니다.`);
  return parsed;
}

export const fmt = (value: number, digits = 1) =>
  new Intl.NumberFormat("ko-KR", { maximumFractionDigits: digits }).format(value);

export const pct = (value: number) => `${fmt(value * 100, 1)}%`;

export const resourceUnit = (resourceType: ResourceType | string) =>
  resourceType === "기관" ? "개소" : "명";

export const formatResourceAmount = (
  value: number,
  resourceType: ResourceType | string,
  digits = 0,
) => `${fmt(value, digits)}${resourceUnit(resourceType)}`;
