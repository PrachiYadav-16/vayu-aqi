import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CatChip } from "../components/Bits";
import { ExposureStrip } from "../components/ExposureStrip";
import { Icon } from "../components/Icon";
import { MapView } from "../components/MapView";
import { PlaceInput } from "../components/PlaceInput";
import { post } from "../lib/api";
import { catFor } from "../lib/aqi";
import { WEEKDAYS, formatDose, fromLocalInput, timeLabel, toLocalInput } from "../lib/format";
import { useSession } from "../lib/session";
import type { Assessment, Place, Trip } from "../lib/types";

const MODES = [
  { key: "two_wheeler", label: "Two-wheeler" },
  { key: "driving", label: "Car" },
  { key: "auto", label: "Auto" },
  { key: "bus", label: "Bus" },
  { key: "cycling", label: "Cycle" },
  { key: "walking", label: "Walk" },
];

function nextQuarter(): Date {
  const d = new Date(Date.now() + 15 * 60000);
  d.setMinutes(Math.ceil(d.getMinutes() / 15) * 15, 0, 0);
  return d;
}

function ScanChart({ scan, current }: { scan: Assessment["departure_scan"]; current: string }) {
  if (scan.length < 2) return null;
  const W = 640;
  const H = 150;
  const pad = { l: 8, r: 8, t: 14, b: 26 };
  const max = Math.max(...scan.map((s) => s.dose_ug)) * 1.1;
  const bw = (W - pad.l - pad.r) / scan.length;
  const best = scan.reduce((a, b) => (b.dose_ug < a.dose_ug ? b : a));
  return (
    <svg className="scan-chart" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Pollution inhaled by departure time. Lowest when leaving at ${timeLabel(best.depart_at)}.`}>
      {scan.map((s, i) => {
        const h = ((H - pad.t - pad.b) * s.dose_ug) / max;
        const x = pad.l + i * bw;
        const isNow = s.depart_at === current || s.shift_min === 0;
        return (
          <g key={s.shift_min}>
            <rect x={x + 2} y={H - pad.b - h} width={bw - 4} height={h} fill={catFor(s.avg_aqi).color}
              stroke={s === best ? "#15211F" : isNow ? "#0B5E6B" : "none"} strokeWidth={2}>
              <title>{`${timeLabel(s.depart_at)}: ${formatDose(s.dose_ug)}, average AQI ${s.avg_aqi}`}</title>
            </rect>
            {(i % 2 === 0 || s === best) && (
              <text x={x + bw / 2} y={H - 8} textAnchor="middle" style={s === best ? { fontWeight: 700, fill: "#15211F" } : undefined}>
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
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [origin, setOrigin] = useState<Place | null>(null);
  const [dest, setDest] = useState<Place | null>(null);
  const [when, setWhen] = useState(toLocalInput(nextQuarter()));
  const [mode, setMode] = useState("two_wheeler");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Assessment | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [label, setLabel] = useState("");
  const [days, setDays] = useState<number[]>([]);
  const [saved, setSaved] = useState<Trip | null>(null);

  const here: Place | null = position ? { name: "My current location", lat: position.lat, lon: position.lon, source: "device" } : null;

  // Prefill from a saved trip (Saved trips > "Check again").
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

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!origin || !dest) {
      setError("Choose both a starting point and a destination from the suggestions.");
      return;
    }
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      const r = await post<Assessment>("/api/trips/assess", {
        origin, destination: dest, depart_at: fromLocalInput(when), mode,
      });
      setResult(r);
      setSelected(r.recommended_route_id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!origin || !dest || !result) return;
    try {
      const t = await post<Trip>("/api/trips", {
        origin, destination: dest, depart_at: result.depart_at, mode, label, repeat_weekdays: days,
      });
      setSaved(t);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const sel = result?.routes.find((r) => r.id === selected) ?? null;
  const fit = useMemo(() => (result ? result.routes.flatMap((r) => r.geometry) : null), [result]);
  const center: [number, number] = origin ? [origin.lat, origin.lon] : position ? [position.lat, position.lon] : [12.9716, 77.5946];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Plan a trip</h1>
          <p>See how much polluted air each route and departure time puts you in.</p>
        </div>
      </div>

      <div className="plan-grid">
        <div className="stack">
          <form className="panel panel-pad stack" onSubmit={submit} aria-label="Trip details">
            <PlaceInput label="From" value={origin} onChange={setOrigin} near={position} currentLocation={here} />
            <button type="button" className="btn quiet small swap" onClick={() => { setOrigin(dest); setDest(origin); }}>
              <Icon name="swap" size={16} /> Swap
            </button>
            <PlaceInput label="To" value={dest} onChange={setDest} near={origin ?? position} currentLocation={here} />
            <label className="field">
              <span>Leaving at</span>
              <input className="input" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
              <span className="help">Indian Standard Time. Forecasts reach 24 hours ahead.</span>
            </label>
            <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
              <span>How you travel</span>
              <div className="segmented">
                {MODES.map((m) => (
                  <label key={m.key}>
                    <input type="radio" name="mode" value={m.key} checked={mode === m.key} onChange={() => setMode(m.key)} />
                    <span>{m.label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="btn" type="submit" disabled={busy}>{busy ? "Checking routes..." : "Check routes"}</button>
          </form>

          {result && (
            <section className="panel" aria-labelledby="verdict-h">
              <div className={`verdict ${result.verdict}`}>
                <h2 id="verdict-h">
                  {result.verdict === "go" ? "Good to go" : result.verdict === "caution" ? "Go with care" : "Think about changing plans"}
                </h2>
                <p className="muted">{result.headline}</p>
                {result.actions.length > 0 && <ul>{result.actions.map((a) => <li key={a}>{a}</li>)}</ul>}
              </div>
              {result.suggestions.length > 0 && (
                <div className="stack" style={{ padding: "0 20px 16px" }}>
                  {result.suggestions.map((s, i) => (
                    <div className="suggestion" key={i}>
                      {s.dose_reduction_pct != null && <b>-{s.dose_reduction_pct}%</b>}
                      <div>
                        <p>{s.text}</p>
                        {s.type === "route" && s.route_id != null && (
                          <button type="button" className="btn quiet small" onClick={() => setSelected(s.route_id!)}>Show this route</button>
                        )}
                        {s.type === "departure" && s.depart_at && (
                          <button type="button" className="btn quiet small" onClick={() => setWhen(toLocalInput(new Date(s.depart_at!)))}>
                            Use {timeLabel(s.depart_at)}
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <div className="save-box">
                <h3>Save this trip</h3>
                {saved ? (
                  <p>
                    Saved. You will get an advisory up to 3 hours before each departure.{" "}
                    <button type="button" className="btn quiet small" onClick={() => nav("/trips")}>Go to saved trips</button>
                  </p>
                ) : (
                  <>
                    <label className="field">
                      <span>Name</span>
                      <input className="input" value={label} placeholder="For example, office commute" onChange={(e) => setLabel(e.target.value)} />
                    </label>
                    <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
                      <span>Repeat on</span>
                      <div className="days">
                        {WEEKDAYS.map((d, i) => (
                          <label key={d}>
                            <input type="checkbox" checked={days.includes(i)}
                              onChange={(e) => setDays(e.target.checked ? [...days, i] : days.filter((x) => x !== i))} />
                            <span>{d}</span>
                          </label>
                        ))}
                      </div>
                      <span className="help">Leave empty for a one-time trip.</span>
                    </fieldset>
                    <button type="button" className="btn secondary" onClick={save}>Save trip</button>
                  </>
                )}
              </div>
            </section>
          )}
        </div>

        <div className="stack">
          <section className="panel map-panel">
            <MapView center={center} zoom={12} routes={result?.routes} selectedRoute={selected} fitTo={fit}
              you={position ? [position.lat, position.lon] : null} />
            {result?.approximate_geometry && (
              <p className="tiny" style={{ padding: "10px 16px" }}>
                No routing service was reachable, so routes are drawn as approximate corridors between the two points.
              </p>
            )}
          </section>

          {result && (
            <section className="panel" aria-labelledby="routes-h">
              <div className="panel-head">
                <h2 id="routes-h">Routes</h2>
                <span className="hint">Leaving {timeLabel(result.depart_at)}, {result.mode_label.toLowerCase()}</span>
              </div>
              <div className="panel-pad routes">
                {result.routes.map((r) => (
                  <button key={r.id} type="button" className="route" aria-pressed={r.id === selected} onClick={() => setSelected(r.id)}>
                    <div className="route-top">
                      <span className="route-name">{r.summary}</span>
                      <span className="route-tags">
                        {r.is_cleanest && <span className="chip">Least pollution</span>}
                        {r.is_fastest && <span className="chip">Fastest</span>}
                        <CatChip aqi={r.avg_aqi} />
                      </span>
                    </div>
                    <ExposureStrip points={r.strip} totalMin={r.duration_min} threshold={result.threshold} big={r.id === selected} label={r.summary} />
                    <div className="route-stats">
                      <span><b>{r.duration_min} min</b>{r.distance_km} km</span>
                      <span><b>{r.avg_aqi}</b>average AQI</span>
                      <span><b>{r.peak_aqi}</b>peak AQI</span>
                      <span><b>{formatDose(r.dose_ug)}</b>PM2.5 inhaled</span>
                    </div>
                    {r.minutes_above_threshold > 0 && (
                      <p className="small">{r.minutes_above_threshold} min above your alert level of {result.threshold} (hatched).</p>
                    )}
                  </button>
                ))}
              </div>
              {sel && result.departure_scan.length > 1 && (
                <div className="panel-pad" style={{ borderTop: "1px solid var(--line-2)" }}>
                  <h3>When to leave on {sel.summary}</h3>
                  <p className="tiny" style={{ margin: "2px 0 8px" }}>Each bar is the PM2.5 you would inhale if you left at that time. Outlined bar is the lowest.</p>
                  <ScanChart scan={result.departure_scan} current={result.depart_at} />
                </div>
              )}
              <p className="tiny" style={{ padding: "0 20px 16px" }}>
                Inhaled amount is estimated from forecast PM2.5, your breathing rate for this way of travel, and how much road air gets inside the vehicle.
                {user?.sensitivity?.length ? "" : " Add health conditions in Settings for stricter advice."}
              </p>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
