import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CatChip } from "../components/Bits";
import { ExposureStrip } from "../components/ExposureStrip";
import { Icon } from "../components/Icon";
import { MapView } from "../components/MapView";
import { PlaceInput } from "../components/PlaceInput";
import { Page } from "../components/Shell";
import { post } from "../lib/api";
import { catFor } from "../lib/aqi";
import { formatCigs, formatDose, fromLocalInput, timeLabel, toLocalInput } from "../lib/format";
import { useT, type Key } from "../lib/i18n";
import { useSession } from "../lib/session";
import type { Assessment, Place, Trip } from "../lib/types";

const MODES = ["two_wheeler", "driving", "auto", "bus", "cycling", "walking"] as const;
const OFFLINE_NAMES: Record<string, Key> = {
  "Direct corridor": "route.direct",
  "Northern corridor": "route.north",
  "Southern corridor": "route.south",
};

export function useRouteName() {
  const { t } = useT();
  return (name: string) => (OFFLINE_NAMES[name] ? t(OFFLINE_NAMES[name]) : name);
}

function nextQuarter(): Date {
  const d = new Date(Date.now() + 15 * 60000);
  d.setMinutes(Math.ceil(d.getMinutes() / 15) * 15, 0, 0);
  return d;
}

function ScanChart({ scan }: { scan: Assessment["departure_scan"] }) {
  if (scan.length < 2) return null;
  const W = 640;
  const H = 160;
  const pad = { l: 8, r: 8, t: 18, b: 26 };
  const max = Math.max(...scan.map((s) => s.dose_ug)) * 1.12;
  const bw = (W - pad.l - pad.r) / scan.length;
  const best = scan.reduce((a, b) => (b.dose_ug < a.dose_ug ? b : a));
  return (
    <svg className="scan-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${timeLabel(best.depart_at)}: ${formatDose(best.dose_ug)}`}>
      {scan.map((s, i) => {
        const h = ((H - pad.t - pad.b) * s.dose_ug) / max;
        const x = pad.l + i * bw;
        const isBest = s === best;
        return (
          <g key={s.shift_min}>
            <rect x={x + 3} y={H - pad.b - h} width={bw - 6} height={h} rx={4} fill={catFor(s.avg_aqi).color}
              stroke={isBest ? "#1f262d" : s.shift_min === 0 ? "#e2702b" : "none"} strokeWidth={2.5}>
              <title>{`${timeLabel(s.depart_at)}: ${formatDose(s.dose_ug)}, AQI ${s.avg_aqi}`}</title>
            </rect>
            {isBest && <text x={x + bw / 2} y={H - pad.b - h - 5} textAnchor="middle" style={{ fill: "#1f262d", fontWeight: 700 }}>{formatDose(s.dose_ug)}</text>}
            {(i % 2 === 0 || isBest) && (
              <text x={x + bw / 2} y={H - 8} textAnchor="middle" style={isBest ? { fontWeight: 700, fill: "#1f262d" } : undefined}>
                {timeLabel(s.depart_at).replace(":00", "")}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export function PlanPage() {
  const { position, user } = useSession();
  const { t, lang } = useT();
  const routeName = useRouteName();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [origin, setOrigin] = useState<Place | null>(null);
  const [dest, setDest] = useState<Place | null>(null);
  const [when, setWhen] = useState(toLocalInput(nextQuarter()));
  const [mode, setMode] = useState<string>("two_wheeler");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Assessment | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [label, setLabel] = useState("");
  const [days, setDays] = useState<number[]>([]);
  const [saved, setSaved] = useState<Trip | null>(null);

  const here: Place | null = position ? { name: t("plan.my_location"), lat: position.lat, lon: position.lon, source: "device" } : null;

  useEffect(() => {
    const o = params.get("o");
    const d = params.get("d");
    if (o && d) {
      const [on, ola, olo] = o.split("|");
      const [dn, dla, dlo] = d.split("|");
      setOrigin({ name: on, lat: +ola, lon: +olo });
      setDest({ name: dn, lat: +dla, lon: +dlo });
      if (params.get("m")) setMode(params.get("m")!);
    }
  }, [params]);

  const run = async () => {
    if (!origin || !dest) {
      setError(t("plan.need_places"));
      return;
    }
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      const r = await post<Assessment>("/api/trips/assess", { origin, destination: dest, depart_at: fromLocalInput(when), mode });
      setResult(r);
      setSelected(r.recommended_route_id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    run();
  };

  // Re-run in the new language so server-written advice matches the UI.
  useEffect(() => {
    if (result) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  const save = async () => {
    if (!origin || !dest || !result) return;
    try {
      setSaved(await post<Trip>("/api/trips", { origin, destination: dest, depart_at: result.depart_at, mode, label, repeat_weekdays: days }));
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const sel = result?.routes.find((r) => r.id === selected) ?? null;
  const fit = useMemo(() => (result ? result.routes.flatMap((r) => r.geometry) : null), [result]);
  const center: [number, number] = origin ? [origin.lat, origin.lon] : position ? [position.lat, position.lon] : [12.9716, 77.5946];
  const verdictKey: Record<Assessment["verdict"], Key> = { go: "verdict.go", caution: "verdict.caution", reconsider: "verdict.reconsider" };

  return (
    <Page title={t("nav.plan")} subtitle={t("plan.subtitle")}>
      <div className="section">
        <div className="grid-2">
          <div className="stack">
            <form className="card stack" onSubmit={submit} aria-label={t("nav.plan")}>
              <PlaceInput label={t("plan.from")} value={origin} onChange={setOrigin} near={position} currentLocation={here} />
              <button type="button" className="btn quiet small swap" onClick={() => { setOrigin(dest); setDest(origin); }}>
                <Icon name="swap" size={16} /> {t("plan.swap")}
              </button>
              <PlaceInput label={t("plan.to")} value={dest} onChange={setDest} near={origin ?? position} currentLocation={here} />
              <label className="field">
                <span>{t("plan.leaving")}</span>
                <input className="input" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
                <span className="help">{t("plan.leaving_help")}</span>
              </label>
              <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
                <span>{t("plan.how")}</span>
                <div className="segmented">
                  {MODES.map((m) => (
                    <label key={m}>
                      <input type="radio" name="mode" value={m} checked={mode === m} onChange={() => setMode(m)} />
                      <span>{t(`mode.${m}` as Key)}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              {error && <p className="form-error" role="alert">{error}</p>}
              <button className="btn" type="submit" disabled={busy}>{busy ? t("plan.checking") : t("plan.check")}</button>
            </form>

            {result && (
              <section className={`card verdict ${result.verdict}`} aria-labelledby="verdict-h">
                <h2 id="verdict-h">{t(verdictKey[result.verdict])}</h2>
                <p className="muted" style={{ marginTop: 4 }}>{result.headline}</p>
                {result.actions.length > 0 && <ul>{result.actions.map((a) => <li key={a}>{a}</li>)}</ul>}
                {result.suggestions.length > 0 && (
                  <div className="stack" style={{ marginTop: 14, gap: 10 }}>
                    {result.suggestions.map((s, i) => (
                      <div className="suggestion" key={i}>
                        {s.dose_reduction_pct != null && <b>&minus;{s.dose_reduction_pct}%</b>}
                        <div>
                          <p>{s.text}</p>
                          {s.type === "route" && s.route_id != null && (
                            <button type="button" className="btn quiet small" onClick={() => setSelected(s.route_id!)}>{t("plan.show_route")}</button>
                          )}
                          {s.type === "departure" && s.depart_at && (
                            <button type="button" className="btn quiet small" onClick={() => setWhen(toLocalInput(new Date(s.depart_at!)))}>
                              {t("plan.use_time", { time: timeLabel(s.depart_at) })}
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            )}

            {result && (
              <section className="card stack" aria-labelledby="save-h">
                <h3 id="save-h">{t("plan.save_title")}</h3>
                {saved ? (
                  <p>
                    {t("plan.saved")}{" "}
                    <button type="button" className="btn quiet small" onClick={() => nav("/trips")}>{t("plan.go_saved")}</button>
                  </p>
                ) : (
                  <>
                    <label className="field">
                      <span>{t("plan.name")}</span>
                      <input className="input" value={label} placeholder={t("plan.name_ph")} onChange={(e) => setLabel(e.target.value)} />
                    </label>
                    <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
                      <span>{t("plan.repeat")}</span>
                      <div className="days">
                        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
                          <label key={i}>
                            <input type="checkbox" checked={days.includes(i)}
                              onChange={(e) => setDays(e.target.checked ? [...days, i] : days.filter((x) => x !== i))} />
                            <span>{t(`day.${i}` as Key)}</span>
                          </label>
                        ))}
                      </div>
                      <span className="help">{t("plan.repeat_help")}</span>
                    </fieldset>
                    <button type="button" className="btn dark" onClick={save}>{t("plan.save")}</button>
                  </>
                )}
              </section>
            )}
          </div>

          <div className="stack">
            <section className="card map-card">
              <MapView center={center} zoom={12} routes={result?.routes} selectedRoute={selected} fitTo={fit}
                you={position ? [position.lat, position.lon] : null} />
              {result?.approximate_geometry && <p className="tiny" style={{ padding: "10px 16px" }}>{t("plan.approx")}</p>}
            </section>

            {result && (
              <section className="card" aria-labelledby="routes-h">
                <div className="section-head" style={{ margin: "0 0 12px" }}>
                  <h2 id="routes-h">{t("plan.routes")}</h2>
                  <span className="hint">{t("plan.leaving_hint", { time: timeLabel(result.depart_at), mode: t(`mode.${result.mode}` as Key) })}</span>
                </div>
                <div className="routes">
                  {result.routes.map((r) => (
                    <button key={r.id} type="button" className="route" style={{ background: "var(--blush)" }}
                      aria-pressed={r.id === selected} onClick={() => setSelected(r.id)}>
                      <div className="route-top">
                        <span className="route-name">{routeName(r.summary)}</span>
                        <span className="route-tags">
                          {r.is_cleanest && <span className="chip dark">{t("route.cleanest")}</span>}
                          {r.is_fastest && <span className="chip" style={{ background: "#fff" }}>{t("route.fastest")}</span>}
                          <CatChip aqi={r.avg_aqi} />
                        </span>
                      </div>
                      <ExposureStrip points={r.strip} totalMin={r.duration_min} threshold={result.threshold} big={r.id === selected} label={routeName(r.summary)} />
                      <div className="route-stats">
                        <span><b>{t("route.min", { n: r.duration_min })}</b>{t("route.km", { n: r.distance_km })}</span>
                        <span><b>{r.avg_aqi}</b>{t("route.avg")}</span>
                        <span><b>{r.peak_aqi}</b>{t("route.peak")}</span>
                        <span><b>{formatCigs(r.cigarettes)}</b>{t("route.cigs")}</span>
                      </div>
                      <p className="tiny">{t("route.dose", { d: formatDose(r.dose_ug) })}</p>
                      {r.minutes_above_threshold > 0 && (
                        <p className="small">{t("route.above", { n: r.minutes_above_threshold, t: result.threshold })}</p>
                      )}
                    </button>
                  ))}
                </div>
                {sel && result.departure_scan.length > 1 && (
                  <div style={{ marginTop: 18 }}>
                    <h3>{t("plan.when_title", { route: routeName(sel.summary) })}</h3>
                    <p className="tiny" style={{ margin: "2px 0 8px" }}>{t("plan.when_help")}</p>
                    <ScanChart scan={result.departure_scan} />
                  </div>
                )}
                <p className="tiny" style={{ marginTop: 12 }}>{t("plan.dose_note")}</p>
                {!user?.sensitivity?.length && <p className="tiny">{t("set.health_help")}</p>}
              </section>
            )}
          </div>
        </div>
      </div>
    </Page>
  );
}
