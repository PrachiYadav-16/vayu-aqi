import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { DataNote, Legend, Loading } from "../components/Bits";
import { ForecastChart } from "../components/ForecastChart";
import { Icon } from "../components/Icon";
import { MapView } from "../components/MapView";
import { api } from "../lib/api";
import { POLLUTANT_NAMES, POLLUTANT_UNITS, catFor } from "../lib/aqi";
import { hourLabel } from "../lib/format";
import { useSession } from "../lib/session";
import type { PointForecast, StationRow } from "../lib/types";

interface Here extends PointForecast {
  advice: {
    level: "ok" | "caution" | "avoid";
    headline: string;
    actions: string[];
    threshold: number;
    next_breach: { ts: string; aqi: number } | null;
    cleanest_hour: { ts: string; aqi: number };
  };
}

const CITY_CENTERS: Record<string, [number, number]> = {
  Bengaluru: [12.9716, 77.5946],
  Delhi: [28.6139, 77.209],
  Mumbai: [19.076, 72.8777],
  Mysuru: [12.3052, 76.6552],
};

export function NowPage() {
  const { user, position, positionError, locateOnce, meta } = useSession();
  const [stations, setStations] = useState<StationRow[]>([]);
  const [hour, setHour] = useState(0);
  const [surface, setSurface] = useState(true);
  const [picked, setPicked] = useState<{ lat: number; lon: number; label: string } | null>(null);
  const [here, setHere] = useState<Here | null>(null);
  const [error, setError] = useState<string | null>(null);

  const target = useMemo(() => {
    if (picked) return picked;
    if (position) return { lat: position.lat, lon: position.lon, label: "Where you are" };
    if (user?.home_lat != null && user.home_lon != null) return { lat: user.home_lat, lon: user.home_lon, label: "Home" };
    return { lat: CITY_CENTERS.Bengaluru[0], lon: CITY_CENTERS.Bengaluru[1], label: "Bengaluru city centre" };
  }, [picked, position, user?.home_lat, user?.home_lon]);

  useEffect(() => {
    api<{ stations: StationRow[] }>(`/api/air/stations?hour=${hour}`)
      .then((r) => setStations(r.stations))
      .catch((e) => setError(e.message));
  }, [hour]);

  useEffect(() => {
    setHere(null);
    api<Here>(`/api/me/here?lat=${target.lat}&lon=${target.lon}`)
      .then(setHere)
      .catch((e) => setError(e.message));
  }, [target.lat, target.lon]);

  const pick = useCallback((lat: number, lon: number) => setPicked({ lat, lon, label: "Spot you picked on the map" }), []);
  const onStation = useCallback((s: StationRow) => setPicked({ lat: s.lat, lon: s.lon, label: `${s.name}, ${s.city}` }), []);

  const cat = here ? catFor(here.current_aqi) : null;
  const hourText = hour === 0 ? "Now" : here?.hours[hour - 1] ? hourLabel(here.hours[hour - 1].ts) : `+${hour} h`;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Air now</h1>
          <p>Current air quality and the next 24 hours, set to your alert level of {user?.threshold}.</p>
        </div>
        <DataNote />
      </div>
      {error && <p className="form-error">{error}</p>}

      <div className="now-grid">
        <section className="panel" aria-labelledby="reading-h">
          {!here || !cat ? (
            <div className="panel-pad"><Loading what="air quality" /></div>
          ) : (
            <div className="now-reading">
              <div className="reading-top">
                <div className="reading-num" style={{ background: cat.color, color: cat.ink }}>
                  <span className="n">{here.current_aqi}</span>
                  <span className="l">AQI</span>
                </div>
                <div className="reading-text">
                  <h2 id="reading-h">{cat.label}</h2>
                  <p>{target.label}</p>
                  {here.dominant_pollutant && (
                    <p>Main pollutant: {POLLUTANT_NAMES[here.dominant_pollutant]}</p>
                  )}
                  {here.coverage === "outside" ? (
                    <p><b>No monitoring station within 45 km.</b> This estimate is unreliable.</p>
                  ) : (
                    <p className="tiny">Nearest station {here.nearest_station_km} km away</p>
                  )}
                </div>
              </div>

              <div className={`advice ${here.advice.level}`}>
                <strong>{here.advice.headline}</strong>
                {here.advice.next_breach && here.current_aqi <= here.advice.threshold && (
                  <p className="small muted">
                    Expected to cross your alert level around {hourLabel(here.advice.next_breach.ts)} (AQI {here.advice.next_breach.aqi}).
                  </p>
                )}
                {here.advice.cleanest_hour && (
                  <p className="small muted">
                    Cleanest time in the next 12 hours: {hourLabel(here.advice.cleanest_hour.ts)}, AQI {here.advice.cleanest_hour.aqi}.
                  </p>
                )}
                {here.advice.actions.length > 0 && (
                  <ul>{here.advice.actions.map((a) => <li key={a}>{a}</li>)}</ul>
                )}
              </div>

              <div>
                <h3 style={{ marginBottom: 6 }}>Next 24 hours</h3>
                <ForecastChart current={here.current_aqi} hours={here.hours} threshold={here.advice.threshold} />
              </div>

              <table className="pollutants">
                <caption className="sr-only">Pollutant readings</caption>
                <thead>
                  <tr><th>Pollutant</th><th className="num">Reading</th><th style={{ width: "34%", paddingLeft: 12 }}>Sub-index</th></tr>
                </thead>
                <tbody>
                  {Object.entries(here.pollutants).map(([k, v]) => {
                    const si = here.sub_indices[k] ?? 0;
                    return (
                      <tr key={k}>
                        <td>{POLLUTANT_NAMES[k] ?? k}</td>
                        <td className="num">{k === "co" ? v.toFixed(2) : Math.round(v)} <span className="tiny">{POLLUTANT_UNITS[k]}</span></td>
                        <td style={{ paddingLeft: 12 }}>
                          <div className="bar" title={`Sub-index ${si}`}><i style={{ width: `${Math.min(100, si / 5)}%`, background: catFor(si).color }} /></div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="btn secondary small" type="button" onClick={() => { setPicked(null); locateOnce(); }}>
                  <Icon name="locate" size={16} /> Use my location
                </button>
                <Link className="btn quiet small" to="/plan">Plan a trip from here</Link>
              </div>
              {positionError && <p className="tiny">{positionError}</p>}
            </div>
          )}
        </section>

        <section className="panel map-panel" aria-label="Map">
          <MapView
            center={[target.lat, target.lon]}
            zoom={12}
            stations={stations}
            you={position ? [position.lat, position.lon] : null}
            surfaceHour={surface ? hour : null}
            onPick={pick}
            onStation={onStation}
          />
          <div className="map-tools">
            <div className="hour-slider">
              <label htmlFor="hour">Time</label>
              <input id="hour" type="range" min={0} max={24} step={1} value={hour}
                onChange={(e) => setHour(Number(e.target.value))} aria-valuetext={hourText} />
              <output htmlFor="hour">{hourText}</output>
            </div>
            <label>
              <input type="checkbox" checked={surface} onChange={(e) => setSurface(e.target.checked)} />
              Pollution surface
            </label>
            <Legend />
          </div>
          <p className="tiny" style={{ padding: "0 16px 12px" }}>
            Tap the map to check any spot. Squares are monitoring stations; the shaded surface is estimated between them.
            {meta?.cities?.length ? ` Covered cities: ${meta.cities.join(", ")}.` : ""}
          </p>
        </section>
      </div>
    </>
  );
}
