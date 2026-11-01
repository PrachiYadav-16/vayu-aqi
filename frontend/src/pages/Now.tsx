import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { DataNote, Legend, Loading, useCatLabel } from "../components/Bits";
import { ForecastChart } from "../components/ForecastChart";
import { Icon } from "../components/Icon";
import { MapView } from "../components/MapView";
import { Page } from "../components/Shell";
import { api } from "../lib/api";
import { POLLUTANT_NAMES, POLLUTANT_UNITS, catFor } from "../lib/aqi";
import { axisLabel, formatCigs, hourLabel } from "../lib/format";
import { useT } from "../lib/i18n";
import { useSession } from "../lib/session";
import type { Budget, Explanation, HomeAdvice, HourForecast, Here, StationRow } from "../lib/types";

function BudgetCard({ b }: { b: Budget }) {
  const { t } = useT();
  const full = Math.floor(b.cigarettes_projected);
  const part = b.cigarettes_projected - full;
  const shown = Math.min(full, 12);
  const scale = Math.max(100, b.projected_pct) * 1.05;
  const times = b.projected_ug / b.budget_ug;
  return (
    <section className="card" aria-labelledby="budget-h">
      <div className="card-head"><Icon name="lungs" /><h3 id="budget-h">{t("budget.title")}</h3></div>
      <div className="big-figure">
        <b>{formatCigs(b.cigarettes_projected)}</b>
        <span>{t("budget.cigs_label")}</span>
      </div>
      <div className="cigs" aria-hidden="true">
        {Array.from({ length: shown }, (_, i) => <span key={i} className="cig" />)}
        {full < 12 && part > 0.05 && <span className="cig part" style={{ ["--p" as string]: `${Math.round(part * 100)}%` }} />}
        {full > 12 && <span className="tiny">+{full - 12}</span>}
      </div>
      <div className="meter" role="img" aria-label={`${t("budget.used", { pct: b.used_pct })}. ${t("budget.projected", { pct: b.projected_pct })}`}>
        <span className="proj" style={{ width: `${Math.min(100, (b.projected_pct / scale) * 100)}%` }} />
        <span className="used" style={{ width: `${Math.min(100, (b.used_pct / scale) * 100)}%` }} />
        <span className="limit" style={{ left: `${(100 / scale) * 100}%` }} title={t("budget.limit")} />
      </div>
      <div className="meter-labels"><span>0</span><span>{t("budget.limit")}</span></div>
      <p className="small" style={{ marginTop: 10 }}>{t("budget.used", { pct: b.used_pct })}. {t("budget.projected", { pct: b.projected_pct })}.</p>
      <p className="small muted">{times > 1.05 ? t("budget.over", { x: times.toFixed(1) }) : t("budget.within")}</p>
      {b.estimated && <p className="tiny" style={{ marginTop: 6 }}>{t("budget.estimated")}</p>}
      <p className="tiny" style={{ marginTop: 8 }}>{t("budget.note")}</p>
    </section>
  );
}

function WhyCard({ e }: { e: Explanation | null }) {
  const { t } = useT();
  return (
    <section className="card" aria-labelledby="why-h">
      <div className="card-head"><Icon name="wind" /><h3 id="why-h">{t("why.title")}</h3></div>
      {!e ? (
        <p className="muted small">{t("why.unavailable")}</p>
      ) : (
        <>
          <p className="trend">
            <span aria-hidden="true">{e.trend === "up" ? "↗" : e.trend === "down" ? "↘" : "→"}</span>
            {e.summary}
          </p>
          {e.factors.length === 0 ? (
            <p className="small muted" style={{ marginTop: 8 }}>{t("why.none")}</p>
          ) : (
            <ul className="factors">
              {e.factors.map((f) => (
                <li key={f.factor}>
                  <span className={`dir ${f.direction}`} aria-hidden="true">{f.direction === "up" ? "+" : "−"}</span>
                  <span>
                    {f.text}
                    <small>{f.direction === "up" ? t("why.adds", { n: Math.abs(f.effect) }) : t("why.removes", { n: Math.abs(f.effect) })} AQI</small>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="tiny" style={{ marginTop: 12 }}>{t("why.note")}</p>
        </>
      )}
    </section>
  );
}

function HomeCard({ h, hours }: { h: HomeAdvice; hours: HourForecast[] }) {
  const { t } = useT();
  const inWin = (ts: string, from?: string, to?: string) =>
    !!from && !!to && new Date(ts) >= new Date(from) && new Date(ts) < new Date(to);
  return (
    <section className="card" aria-labelledby="home-h">
      <div className="card-head"><Icon name="window" /><h3 id="home-h">{t("home.title")}</h3></div>
      <div className="home-row">
        <span className="home-icon"><Icon name="window" /></span>
        <div><b className="small">{t("home.windows")}</b><p className="small muted">{h.windows.text}</p></div>
      </div>
      <div className="home-row">
        <span className="home-icon"><Icon name="purifier" /></span>
        <div><b className="small">{t("home.purifier")}</b><p className="small muted">{h.purifier.text}</p></div>
      </div>
      <div className="hours-band" aria-hidden="true">
        {hours.map((x) => (
          <span key={x.ts} style={{ background: catFor(x.aqi).color }}
            className={[
              h.windows.action !== "closed" && inWin(x.ts, h.windows.from, h.windows.to) ? "win" : "",
              h.purifier.action === "run" && inWin(x.ts, h.purifier.from, h.purifier.to) ? "pur" : "",
            ].join(" ")} />
        ))}
      </div>
      <div className="hours-axis" aria-hidden="true">
        {[0, 6, 12, 18, 23].map((i) => hours[i] && <span key={i}>{axisLabel(hours[i].ts)}</span>)}
      </div>
      <div className="hours-legend" aria-hidden="true">
        {h.windows.action !== "closed" && <span><i style={{ boxShadow: "inset 0 0 0 2px #1f262d" }} />{t("home.legend_open")}</span>}
        {h.purifier.action === "run" && <span><i style={{ background: "#e2702b", height: 3 }} />{t("home.legend_purifier")}</span>}
      </div>
    </section>
  );
}

const CITY_CENTERS: [number, number] = [12.9716, 77.5946];

export function NowPage() {
  const { user, position, positionError, locateOnce, meta } = useSession();
  const { t, lang } = useT();
  const catLabel = useCatLabel();
  const [stations, setStations] = useState<StationRow[]>([]);
  const [hour, setHour] = useState(0);
  const [surface, setSurface] = useState(true);
  const [picked, setPicked] = useState<{ lat: number; lon: number; label: string } | null>(null);
  const [here, setHere] = useState<Here | null>(null);
  const [error, setError] = useState<string | null>(null);

  const target = useMemo(() => {
    if (picked) return picked;
    if (position) return { lat: position.lat, lon: position.lon, label: t("now.place_here") };
    if (user?.home_lat != null && user.home_lon != null) return { lat: user.home_lat, lon: user.home_lon, label: t("now.place_home") };
    return { lat: CITY_CENTERS[0], lon: CITY_CENTERS[1], label: t("now.place_city") };
  }, [picked, position, user?.home_lat, user?.home_lon, t]);

  useEffect(() => {
    api<{ stations: StationRow[] }>(`/api/air/stations?hour=${hour}`)
      .then((r) => setStations(r.stations))
      .catch((e) => setError(e.message));
  }, [hour]);

  useEffect(() => {
    let live = true;
    api<Here>(`/api/me/here?lat=${target.lat}&lon=${target.lon}`)
      .then((r) => live && setHere(r))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [target.lat, target.lon, lang]);

  const pick = useCallback((lat: number, lon: number) => setPicked({ lat, lon, label: t("now.place_pick") }), [t]);
  const onStation = useCallback((s: StationRow) => setPicked({ lat: s.lat, lon: s.lon, label: `${s.name}, ${s.city}` }), []);

  const cat = here ? catFor(here.current_aqi) : null;
  // Far from every station the interpolated number would be a guess; do not show one.
  const outside = here?.coverage === "outside";
  const hourText = hour === 0 ? t("map.now") : here?.hours[hour - 1] ? hourLabel(here.hours[hour - 1].ts) : `+${hour}`;

  return (
    <Page title={t("now.title")} subtitle={t("now.subtitle", { t: user?.threshold ?? 200 })} note={<DataNote />}>
      {error && <p className="form-error" style={{ marginBottom: 12 }}>{error}</p>}

      <div className="section">
        <div className="grid-2">
          <section className="card" aria-labelledby="reading-h">
            {!here || !cat ? (
              <Loading />
            ) : outside ? (
              <div className="reading">
                <div className="reading-top">
                  <div className="reading-num" style={{ background: "var(--line-2)", color: "var(--ink-2)" }}>
                    <span className="n">-</span>
                    <span className="l">AQI</span>
                  </div>
                  <div className="reading-text">
                    <h2 id="reading-h">{t("now.outside_title")}</h2>
                    <p>{target.label}</p>
                    <p className="small">{t("now.outside")}</p>
                    {meta?.cities?.length ? <p className="tiny">{t("map.cities", { c: meta.cities.join(", ") })}</p> : null}
                  </div>
                </div>
                <div className="row-actions">
                  <button className="btn dark small" type="button" onClick={() => { setPicked(null); locateOnce(); }}>
                    <Icon name="locate" size={16} /> {t("now.use_location")}
                  </button>
                </div>
              </div>
            ) : (
              <div className="reading">
                <div className="reading-top">
                  <div className="reading-num" style={{ background: cat.color, color: cat.ink }}>
                    <span className="n">{here.current_aqi}</span>
                    <span className="l">AQI</span>
                  </div>
                  <div className="reading-text">
                    <h2 id="reading-h">{catLabel(here.current_aqi)}</h2>
                    <p>{target.label}</p>
                    {here.dominant_pollutant && <p>{t("now.main_pollutant", { p: POLLUTANT_NAMES[here.dominant_pollutant] })}</p>}
                    <p className="tiny">{t("now.nearest", { km: here.nearest_station_km })}</p>
                  </div>
                </div>
                <div className={`advice ${here.advice.level}`}>
                  <strong>{here.advice.headline}</strong>
                  {here.advice.next_breach && here.current_aqi <= here.advice.threshold && (
                    <p className="small muted">{t("now.next_breach", { time: hourLabel(here.advice.next_breach.ts), aqi: here.advice.next_breach.aqi })}</p>
                  )}
                  <p className="small muted">{t("now.cleanest", { time: hourLabel(here.advice.cleanest_hour.ts), aqi: here.advice.cleanest_hour.aqi })}</p>
                  {here.advice.actions.length > 0 && <ul>{here.advice.actions.map((a) => <li key={a}>{a}</li>)}</ul>}
                </div>
                <div className="row-actions">
                  <button className="btn dark small" type="button" onClick={() => { setPicked(null); locateOnce(); }}>
                    <Icon name="locate" size={16} /> {t("now.use_location")}
                  </button>
                  <Link className="btn quiet small" to="/plan">{t("now.plan_from_here")}</Link>
                </div>
                {positionError && <p className="tiny">{positionError}</p>}
              </div>
            )}
          </section>

          <section className="card map-card" aria-label="Map">
            <MapView center={[target.lat, target.lon]} zoom={12} stations={stations}
              you={position ? [position.lat, position.lon] : null} surfaceHour={surface ? hour : null}
              onPick={pick} onStation={onStation} />
            <div className="map-tools">
              <div className="hour-slider">
                <label htmlFor="hour">{t("map.time")}</label>
                <input id="hour" type="range" min={0} max={24} step={1} value={hour}
                  onChange={(e) => setHour(Number(e.target.value))} aria-valuetext={hourText} />
                <output htmlFor="hour">{hourText}</output>
              </div>
              <label>
                <input type="checkbox" checked={surface} onChange={(e) => setSurface(e.target.checked)} />
                {t("map.surface")}
              </label>
              <Legend />
            </div>
            <p className="tiny map-help">
              {t("map.help")}{meta?.cities?.length ? ` ${t("map.cities", { c: meta.cities.join(", ") })}` : ""}
            </p>
          </section>
        </div>
      </div>

      {here && !outside && (
        <div className="section">
          <div className="section-head"><h2>{t("now.today_for_you")}</h2></div>
          <div className="grid-3">
            <BudgetCard b={here.budget} />
            <WhyCard e={here.explain} />
            {here.home && <HomeCard h={here.home} hours={here.hours} />}
          </div>
        </div>
      )}

      {here && !outside && (
        <div className="section">
          <div className="grid-2 wide-left">
            <section className="card">
              <h3 style={{ marginBottom: 8 }}>{t("now.next24")}</h3>
              <ForecastChart current={here.current_aqi} hours={here.hours} threshold={here.advice.threshold} />
            </section>
            <section className="card">
              <h3 style={{ marginBottom: 8 }}>{t("now.pollutants")}</h3>
              <table className="pollutants">
                <thead>
                  <tr><th>{t("table.pollutant")}</th><th className="num">{t("table.reading")}</th><th style={{ width: "36%", paddingLeft: 12 }}>{t("table.subindex")}</th></tr>
                </thead>
                <tbody>
                  {Object.entries(here.pollutants).map(([k, v]) => {
                    const si = here.sub_indices[k] ?? 0;
                    return (
                      <tr key={k}>
                        <td>{POLLUTANT_NAMES[k] ?? k}</td>
                        <td className="num">{k === "co" ? v.toFixed(2) : Math.round(v)} <span className="tiny">{POLLUTANT_UNITS[k]}</span></td>
                        <td style={{ paddingLeft: 12 }}>
                          <div className="si">
                            <div className="bar" aria-hidden="true">
                              <i style={{ width: `${Math.min(100, si / 5)}%`, background: catFor(si).color }} />
                            </div>
                            <span>{si}</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="tiny" style={{ marginTop: 8 }}>{t("table.avg_note")}</p>
            </section>
          </div>
        </div>
      )}
    </Page>
  );
}
