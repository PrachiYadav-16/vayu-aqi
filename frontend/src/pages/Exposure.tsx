import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loading } from "../components/Bits";
import { api } from "../lib/api";
import { catFor } from "../lib/aqi";
import { useSession } from "../lib/session";

interface Day {
  date: string;
  avg_aqi: number | null;
  peak_aqi: number;
  tracked_minutes: number;
  minutes_above_threshold: number;
}

function Chart({ days, threshold }: { days: Day[]; threshold: number }) {
  const W = 720;
  const H = 220;
  const pad = { l: 34, r: 8, t: 12, b: 28 };
  const max = Math.ceil((Math.max(threshold, ...days.map((d) => d.peak_aqi)) * 1.1) / 50) * 50;
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / max);
  const bw = (W - pad.l - pad.r) / days.length;
  return (
    <svg className="hist" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Average and peak AQI you were in each day">
      {[0, max / 2, max].map((t) => (
        <g key={t}>
          <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="#e1e7e5" />
          <text x={pad.l - 6} y={y(t) + 4} textAnchor="end">{Math.round(t)}</text>
        </g>
      ))}
      {days.map((d, i) => {
        const x = pad.l + i * bw;
        const avg = d.avg_aqi ?? 0;
        return (
          <g key={d.date}>
            <line x1={x + bw / 2} x2={x + bw / 2} y1={y(d.peak_aqi)} y2={y(avg)} stroke="#15211F" strokeWidth={1.5} />
            <rect x={x + bw * 0.2} y={y(avg)} width={bw * 0.6} height={y(0) - y(avg)} fill={catFor(avg).color}>
              <title>{`${d.date}: average AQI ${avg}, peak ${d.peak_aqi}`}</title>
            </rect>
            <text x={x + bw / 2} y={H - 10} textAnchor="middle">{d.date.slice(8)}</text>
          </g>
        );
      })}
      <line x1={pad.l} x2={W - pad.r} y1={y(threshold)} y2={y(threshold)} stroke="#15211F" strokeDasharray="4 3" />
    </svg>
  );
}

export function ExposurePage() {
  const { user } = useSession();
  const [data, setData] = useState<{ threshold: number; days: Day[]; pings: number } | null>(null);
  useEffect(() => {
    api<{ threshold: number; days: Day[]; pings: number }>("/api/me/exposure?days=14").then(setData).catch(() => setData(null));
  }, []);

  const tracked = data?.days.filter((d) => d.avg_aqi != null) ?? [];
  const avg = tracked.length ? Math.round(tracked.reduce((a, d) => a + (d.avg_aqi ?? 0) * d.tracked_minutes, 0) / Math.max(1, tracked.reduce((a, d) => a + d.tracked_minutes, 0))) : null;
  const hoursAbove = Math.round((tracked.reduce((a, d) => a + d.minutes_above_threshold, 0) / 60) * 10) / 10;
  const worst = tracked.reduce<Day | null>((a, d) => (!a || (d.avg_aqi ?? 0) > (a.avg_aqi ?? 0) ? d : a), null);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>My exposure</h1>
          <p>Air quality where you have been over the last 14 days, from your shared location.</p>
        </div>
      </div>
      {!data ? (
        <Loading what="your history" />
      ) : !user?.location_consent && data.pings === 0 ? (
        <section className="panel empty">
          <p>Turn on location sharing to build a record of the air you breathe each day.</p>
          <Link className="btn" to="/settings">Open settings</Link>
        </section>
      ) : tracked.length === 0 ? (
        <section className="panel empty"><p>No location history yet. Keep Vayu open on your phone and it will fill in over the day.</p></section>
      ) : (
        <div className="stack">
          <section className="panel kpis" aria-label="Summary">
            <div><b>{avg}</b><span>average AQI around you</span></div>
            <div><b>{hoursAbove} h</b><span>above your alert level of {data.threshold}</span></div>
            <div><b>{worst ? new Date(worst.date).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" }) : "-"}</b><span>worst day, average AQI {worst?.avg_aqi}</span></div>
          </section>
          <section className="panel">
            <div className="panel-head"><h2>Daily average and peak</h2><span className="hint">Dashed line is your alert level</span></div>
            <div className="panel-pad"><Chart days={tracked} threshold={data.threshold} /></div>
          </section>
          <p className="tiny">Location history older than 30 days is deleted automatically. You can delete all of it in Settings.</p>
        </div>
      )}
    </>
  );
}
