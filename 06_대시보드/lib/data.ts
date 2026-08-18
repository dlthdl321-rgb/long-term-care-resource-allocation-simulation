import type { DashboardRow } from "../types";

export const DASHBOARD_DATASETS = [
  "baseline",
  "regions",
  "stability",
  "access-regions",
  "access-metrics",
  "access-impact",
  "supply-trends",
  "workforce",
  "history",
  "allocation-strategies",
  "allocation-detail",
  "access-contributions",
  "quality",
  "portfolio-summary",
] as const;

export async function loadDashboardJson(name: string): Promise<DashboardRow[]> {
  const response = await fetch(`/data/${name}.json`);
  if (!response.ok) throw new Error(`${name} 데이터를 읽지 못했습니다.`);
  return response.json();
}

export function downloadCsv(rows: DashboardRow[], filename: string) {
  if (!rows.length) return;
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  const escape = (value: string | undefined) =>
    `"${String(value ?? "").replaceAll('"', '""')}"`;
  const body = [
    columns.map(escape).join(","),
    ...rows.map((row) => columns.map((column) => escape(row[column])).join(",")),
  ].join("\r\n");
  const blob = new Blob(["\ufeff", body], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
