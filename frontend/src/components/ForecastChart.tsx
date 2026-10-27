import { useState } from "react";
import { catFor } from "../lib/aqi";
import { hourLabel } from "../lib/format";
import type { HourForecast } from "../lib/types";

interface Props {
  current: number;
  hours: HourForecast[];
  threshold?: number;
}

/** 24 hourly columns coloured by CPCB category, with the 80% band as a whisker. */
export function ForecastChart({ current, hours, threshold }: Props) {
  const [focus, setFocus] = useState<number | null>(null);
  const W = 420;
  const H = 190;
  const pad = { l: 28, r: 4, t: 14, b: 22 };
  const cols = [{ ts: "", aqi: current, low: current, high: current, category: catFor(current).key }, ...hours];
  const top = Math.max(120, ...cols.map((c) => c.high), threshold ?? 0) * 1.08;
  const ceil = Math.ceil(top / 50) * 50;
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / ceil);
  const cw = (W - pad.l - pad.r) / cols.length;
  const ticks = [0, ceil / 2, ceil].map((v) => Math.round(v));
  const f = focus == null ? null : cols[focus];

  return (
    <div>
      <svg className="fchart" viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`AQI now ${current}, peak in the next 24 hours ${Math.max(...hours.map((h) => h.aqi))}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="#e1e7e5" />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end">{t}</text>
          </g>
        ))}
        {cols.map((c, i) => {
          const x = pad.l + i * cw;
          const cat = catFor(c.aqi);
          return (
            <g key={i}>
              <rect className="col" x={x + 1.5} y={y(c.aqi)} width={cw - 3} height={y(0) - y(c.aqi)}
                fill={cat.color} opacity={focus == null || focus === i ? 1 : 0.55} tabIndex={0}
                onMouseEnter={() => setFocus(i)} onMouseLeave={() => setFocus(null)}
                onFocus={() => setFocus(i)} onBlur={() => setFocus(null)}
                aria-label={`${i === 0 ? "Now" : hourLabel(c.ts)}: AQI ${c.aqi}`} />
              {i > 0 && (
                <line className="whisker" x1={x + cw / 2} x2={x + cw / 2} y1={y(c.high)} y2={y(c.low)} />
              )}
              {(i === 0 || i % 6 === 0) && (
                <text x={x + cw / 2} y={H - 8} textAnchor="middle">{i === 0 ? "Now" : hourLabel(c.ts)}</text>
              )}
            </g>
          );
        })}
        {threshold != null && threshold < ceil && (
          <g>
            <line className="thr" x1={pad.l} x2={W - pad.r} y1={y(threshold)} y2={y(threshold)} />
            <text className="thr-label" x={W - pad.r - 2} y={y(threshold) - 5} textAnchor="end">
              Alert level {threshold}
            </text>
          </g>
        )}
      </svg>
      <p className="fchart-readout" aria-live="polite">
        {f ? (
          <>
            <b>{focus === 0 ? "Now" : hourLabel(f.ts)}</b>: AQI {f.aqi} ({catFor(f.aqi).label})
            {focus !== 0 && <span className="muted">, likely between {f.low} and {f.high}</span>}
          </>
        ) : (
          <span className="tiny">Bars show the most likely AQI each hour. Thin lines show the range it will probably fall in.</span>
        )}
      </p>
    </div>
  );
}
