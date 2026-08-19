import { fmt } from "../lib/format";
import type { TimelinePoint } from "../types";

type TimelineValueKey =
  | "baselineResource"
  | "scenarioResource"
  | "baselineGap"
  | "scenarioGap"
  | "baselineShortage"
  | "scenarioShortage";

export function TimelineChart({
  points,
  baselineKey,
  scenarioKey,
  title,
  baselineLabel,
  scenarioLabel,
  unit,
  takeaway,
}: {
  points: TimelinePoint[];
  baselineKey: TimelineValueKey;
  scenarioKey: TimelineValueKey;
  title: string;
  baselineLabel: string;
  scenarioLabel: string;
  unit: string;
  takeaway: string;
}) {
  const width = 760;
  const height = 280;
  const pad = { left: 52, right: 20, top: 24, bottom: 36 };
  const maxValue = Math.max(
    ...points.flatMap((point) => [point[baselineKey], point[scenarioKey]]),
    1,
  );
  const x = (index: number) =>
    pad.left +
    (index / Math.max(points.length - 1, 1)) *
      (width - pad.left - pad.right);
  const y = (value: number) =>
    pad.top +
    (1 - value / maxValue) * (height - pad.top - pad.bottom);
  const line = (key: TimelineValueKey) =>
    points
      .map((point, index) => `${index ? "L" : "M"} ${x(index)} ${y(point[key])}`)
      .join(" ");
  const last = points[points.length - 1];

  return (
    <div className="timeline-chart">
      <h3>{title}</h3>
      <p className="chart-takeaway">{takeaway}</p>
      <div className="chart-end-values">
        <span>변경 없음 <b>{fmt(last?.[baselineKey] || 0, 1)}{unit}</b></span>
        <span>변경 후 <b>{fmt(last?.[scenarioKey] || 0, 1)}{unit}</b></span>
      </div>
      <div className="chart-legend">
        <span><i className="legend-line baseline" />{baselineLabel}</span>
        <span><i className="legend-line scenario" />{scenarioLabel}</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
        {[0, 0.5, 1].map((ratio) => {
          const value = maxValue * ratio;
          return (
            <g key={ratio}>
              <line
                x1={pad.left}
                x2={width - pad.right}
                y1={y(value)}
                y2={y(value)}
                className="grid-line"
              />
              <text x={pad.left - 9} y={y(value) + 4} textAnchor="end">
                {fmt(value, 0)}
              </text>
            </g>
          );
        })}
        <path d={line(baselineKey)} className="forecast-line baseline" />
        <path d={line(scenarioKey)} className="forecast-line scenario" />
        {points.map((point, index) => (
          <text key={point.year} x={x(index)} y={height - 12} textAnchor="middle">
            {point.year}
          </text>
        ))}
      </svg>
    </div>
  );
}
