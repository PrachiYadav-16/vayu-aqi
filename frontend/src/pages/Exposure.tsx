import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loading } from "../components/Bits";
import { Page } from "../components/Shell";
import { api } from "../lib/api";
import { catFor } from "../lib/aqi";
import { dayLabel, formatCigs } from "../lib/format";
import { useT } from "../lib/i18n";
import { useSession } from "../lib/session";

interface Day {
  date: string;
  avg_aqi: number | null;
  peak_aqi: number;
  tracked_minutes: number;
  minutes_above_threshold: number;
  dose_ug: number;
  cigarettes: number;
  budget_pct: number;
}
interface Resp {
  threshold: number;
  days: Day[];
  pings: number;
  budget_ug: number;
  ug_per_cigarette: number;
}

function Chart({ days, limit }: { days: Day[]; limit: number }) {
  const W = 720;
  const H = 230;
  const pad = { l: 34, r: 8, t: 16, b: 28 };
  const top = Math.max(limit * 1.3, ...days.map((d) => d.cigarettes)) * 1.12;
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / top);
  const bw = (W - pad.l - pad.r) / days.length;
  const ticks = [0, top / 2, top];
  return (
    <svg className="hist" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Cigarettes per day">
      {ticks.map((v, i) => (
        <g key={i}>
          <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="#efe8e2" />
          <text x={pad.l - 6} y={y(v) + 4} textAnchor="end">{v.toFixed(1)}</text>
        </g>
      ))}
      {days.map((d, i) => {
        const x = pad.l + i * bw;
        return (
          <g key={d.date}>
            <rect x={x + bw * 0.18} y={y(d.cigarettes)} width={bw * 0.64} height={y(0) - y(d.cigarettes)} rx={5}
              fill={catFor(d.avg_aqi ?? 0).color}>
              <title>{`${dayLabel(d.date)}: ${formatCigs(d.cigarettes)}, AQI ${d.avg_aqi}`}</title>
            </rect>
            <text x={x + bw / 2} y={H - 10} textAnchor="middle">{d.date.slice(8)}</text>
          </g>
        );
      })}
      <line x1={pad.l} x2={W - pad.r} y1={y(limit)} y2={y(limit)} stroke="#1f262d" strokeDasharray="5 4" />
      <text x={W - pad.r} y={y(limit) - 6} textAnchor="end" style={{ fill: "#1f262d", fontWeight: 700 }}>WHO</text>
    </svg>
  );
}

export function ExposurePage() {
  const { user } = useSession();
  const { t } = useT();
  const [data, setData] = useState<Resp | null>(null);
  useEffect(() => {
    api<Resp>("/api/me/exposure?days=14").then(setData).catch(() => setData(null));
  }, []);

  const tracked = data?.days.filter((d) => d.avg_aqi != null) ?? [];
  const minutes = tracked.reduce((a, d) => a + d.tracked_minutes, 0);
  const avg = tracked.length ? Math.round(tracked.reduce((a, d) => a + (d.avg_aqi ?? 0) * d.tracked_minutes, 0) / Math.max(1, minutes)) : null;
  const cigs = tracked.reduce((a, d) => a + d.cigarettes, 0);
  const over = tracked.filter((d) => d.budget_pct > 100).length;
  const worst = tracked.reduce<Day | null>((a, d) => (!a || (d.avg_aqi ?? 0) > (a.avg_aqi ?? 0) ? d : a), null);
  const limit = data ? data.budget_ug / data.ug_per_cigarette : 0.68;

  return (
    <Page title={t("nav.exposure")} subtitle={t("exp.subtitle")}>
      <div className="section">
        {!data ? (
          <div className="card"><Loading /></div>
        ) : !user?.location_consent && data.pings === 0 ? (
          <div className="empty">
            <p>{t("exp.need_consent")}</p>
            <Link className="btn" to="/settings">{t("exp.open_settings")}</Link>
          </div>
        ) : tracked.length === 0 ? (
          <div className="empty"><p>{t("exp.no_history")}</p></div>
        ) : (
          <div className="stack">
            <div className="kpis">
              <div><b>{avg}</b><span>{t("exp.kpi_avg")}</span></div>
              <div><b>{formatCigs(cigs)}</b><span>{t("exp.kpi_cigs", { n: tracked.length })}</span></div>
              <div><b>{over}/{tracked.length}</b><span>{t("exp.kpi_over")}</span></div>
              <div><b>{worst ? dayLabel(worst.date) : "-"}</b><span>{t("exp.kpi_worst", { aqi: worst?.avg_aqi ?? "-" })}</span></div>
            </div>
            <section className="card">
              <div className="section-head" style={{ margin: "0 0 8px" }}>
                <h2>{t("exp.chart_title")}</h2>
                <span className="hint">{t("exp.chart_hint")}</span>
              </div>
              <Chart days={tracked} limit={limit} />
            </section>
            <p className="tiny">{t("exp.retention")}</p>
          </div>
        )}
      </div>
    </Page>
  );
}
