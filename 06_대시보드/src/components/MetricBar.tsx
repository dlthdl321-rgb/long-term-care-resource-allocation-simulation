import { fmt } from "../lib/format";

export function MetricBar({ value, max, tone = "primary" }: {
  value: number; max: number; tone?: "primary" | "warm" | "cool";
}) {
  return <span className="bar-track" aria-label={`${fmt(value)} / ${fmt(max)}`}>
    <span className={`bar-fill ${tone}`} style={{ width: `${Math.max(2, Math.min(100, (value / max) * 100))}%` }} />
  </span>;
}
