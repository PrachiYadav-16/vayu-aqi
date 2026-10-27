import { catFor } from "../lib/aqi";
import type { StripPoint } from "../lib/types";

interface Props {
  points: StripPoint[];
  totalMin: number;
  threshold: number;
  big?: boolean;
  label?: string;
}

/**
 * The trip as one band: left is departure, right is arrival, each slice is the
 * AQI you are forecast to be in at that minute. Slices above your alert level
 * are hatched so the pattern still reads without colour.
 */
export function ExposureStrip({ points, totalMin, threshold, big, label }: Props) {
  if (!points.length) return null;
  const slices = points.map((p, i) => {
    const next = points[i + 1]?.minute ?? totalMin;
    return { ...p, span: Math.max(next - p.minute, 0.01) };
  });
  const sum = slices.reduce((a, s) => a + s.span, 0);
  const above = slices.filter((s) => s.aqi > threshold).reduce((a, s) => a + s.span, 0);
  const desc = `${label ?? "Route"}: ${Math.round(totalMin)} minutes, AQI from ${Math.min(...points.map((p) => p.aqi))} to ${Math.max(...points.map((p) => p.aqi))}${above > 0 ? `, ${Math.round((above / sum) * totalMin)} minutes above your alert level` : ""}`;
  const marks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * totalMin));

  return (
    <div className={`strip${big ? " big" : ""}`}>
      <div className="strip-band" role="img" aria-label={desc}>
        {slices.map((s, i) => (
          <span key={i} className={s.aqi > threshold ? "over" : undefined}
            style={{ width: `${(s.span / sum) * 100}%`, backgroundColor: catFor(s.aqi).color }}
            title={`${Math.round(s.minute)} min: AQI ${s.aqi}`} />
        ))}
      </div>
      <div className="strip-axis" aria-hidden="true">
        {marks.map((m, i) => (
          <span key={i}>{i === 0 ? "Start" : i === marks.length - 1 ? `${m} min` : `${m}`}</span>
        ))}
      </div>
    </div>
  );
}
