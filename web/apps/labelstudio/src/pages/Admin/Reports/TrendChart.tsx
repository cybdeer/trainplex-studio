/**
 * TrendChart — minimal SVG line chart for the founder dashboard.
 *
 * Phase 1 Step 7. No external charting lib — keeps the bundle small and the
 * a11y story simple. The chart takes a list of (x-label, y-value) pairs,
 * normalises the y-axis to the data range, and renders a path + dots + axis
 * ticks.
 */

import styles from "./Reports.module.css";

export interface TrendChartPoint {
  label: string;
  value: number;
}

interface TrendChartProps {
  data: TrendChartPoint[];
  /** Optional formatter for the y-axis labels. Defaults to `value.toLocaleString()`. */
  formatY?: (value: number) => string;
  /** Optional stable test id. */
  testId?: string;
  /** Optional aria-label for screen readers (e.g. "Submissions over the past week"). */
  ariaLabel?: string;
}

export function TrendChart({ data, formatY, testId, ariaLabel }: TrendChartProps) {
  if (data.length === 0) {
    return (
      <div className={styles.errorBox} data-testid={testId ? `${testId}-empty` : undefined}>
        No data
      </div>
    );
  }

  // Padded viewBox so the path/dots don't touch the edges.
  const W = 600;
  const H = 220;
  const PAD_L = 48;
  const PAD_R = 16;
  const PAD_T = 16;
  const PAD_B = 36;

  const values = data.map((d) => d.value);
  const yMin = Math.min(...values, 0);
  const yMax = Math.max(...values, 1);
  const yRange = Math.max(1, yMax - yMin);

  const xStep = data.length > 1 ? (W - PAD_L - PAD_R) / (data.length - 1) : 0;

  const points = data.map((d, i) => {
    const x = PAD_L + i * xStep;
    const yNorm = (d.value - yMin) / yRange;
    const y = H - PAD_B - yNorm * (H - PAD_T - PAD_B);
    return { x, y, label: d.label, value: d.value };
  });

  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  // Area fill — close the path back to the baseline.
  const areaD = `${pathD} L ${points[points.length - 1].x.toFixed(1)} ${H - PAD_B} L ${PAD_L} ${H - PAD_B} Z`;
  const formatter = formatY ?? ((v: number) => v.toLocaleString());

  // 3 horizontal gridlines: min, mid, max.
  const gridYs = [0, 0.5, 1].map((frac) => H - PAD_B - frac * (H - PAD_T - PAD_B));
  const gridLabels = [yMin, yMin + yRange / 2, yMax];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={styles.trendChart}
      data-testid={testId}
      role="img"
      aria-label={ariaLabel}
    >
      {/* gridlines */}
      {gridYs.map((y, i) => (
        <line key={i} x1={PAD_L} y1={y} x2={W - PAD_R} y2={y} className={styles.trendAxis} />
      ))}
      {/* y-axis labels */}
      {gridLabels.map((v, i) => (
        <text key={`yl-${i}`} x={PAD_L - 8} y={gridYs[i] + 4} textAnchor="end" className={styles.trendLabel}>
          {formatter(Math.round(v))}
        </text>
      ))}
      {/* area + line */}
      <path d={areaD} className={styles.trendArea} />
      <path d={pathD} className={styles.trendPath} />
      {/* dots */}
      {points.map((p, i) => (
        <circle key={`dot-${i}`} cx={p.x} cy={p.y} r={3} className={styles.trendDot} />
      ))}
      {/* x-axis labels: show every Nth label so we don't crowd */}
      {points.map((p, i) => {
        const everyN = Math.max(1, Math.ceil(points.length / 7));
        if (i % everyN !== 0 && i !== points.length - 1) return null;
        return (
          <text key={`xl-${i}`} x={p.x} y={H - PAD_B + 18} textAnchor="middle" className={styles.trendLabel}>
            {p.label}
          </text>
        );
      })}
    </svg>
  );
}

export default TrendChart;
