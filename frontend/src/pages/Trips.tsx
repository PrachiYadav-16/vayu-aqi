import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CatChip, Loading } from "../components/Bits";
import { Icon } from "../components/Icon";
import { api, del, post } from "../lib/api";
import { WEEKDAYS, dayLabel, timeLabel } from "../lib/format";
import type { Trip } from "../lib/types";

const MODE_LABEL: Record<string, string> = {
  two_wheeler: "Two-wheeler", driving: "Car", auto: "Auto", bus: "Bus", cycling: "Cycle", walking: "Walk",
};

function schedule(t: Trip) {
  const time = timeLabel(t.depart_at);
  if (!t.repeat_weekdays.length) return `${dayLabel(t.depart_at)}, ${time}`;
  if (t.repeat_weekdays.length === 5 && t.repeat_weekdays.every((d) => d < 5)) return `Weekdays, ${time}`;
  if (t.repeat_weekdays.length === 7) return `Every day, ${time}`;
  return `${t.repeat_weekdays.map((d) => WEEKDAYS[d]).join(", ")}, ${time}`;
}

export function TripsPage() {
  const [trips, setTrips] = useState<Trip[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const load = () => api<Trip[]>("/api/trips").then(setTrips).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const remove = async (t: Trip) => {
    if (!window.confirm(`Delete "${t.label || t.dest_name}"? You will stop getting advisories for it.`)) return;
    await del(`/api/trips/${t.id}`);
    load();
  };

  const checkNow = async () => {
    setChecking(true);
    try {
      await post("/api/alerts/check-now");
      window.dispatchEvent(new Event("vayu:alerts-changed"));
      await load();
    } finally {
      setChecking(false);
    }
  };

  const href = (t: Trip) =>
    `/plan?o=${encodeURIComponent(`${t.origin_name}|${t.origin_lat}|${t.origin_lon}`)}&d=${encodeURIComponent(`${t.dest_name}|${t.dest_lat}|${t.dest_lon}`)}&m=${t.mode}`;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Saved trips</h1>
          <p>Vayu checks each trip up to 3 hours before you leave and alerts you if the air is bad or a cleaner option exists.</p>
        </div>
        {trips && trips.length > 0 && (
          <button className="btn secondary" type="button" onClick={checkNow} disabled={checking}>
            {checking ? "Checking..." : "Check all trips now"}
          </button>
        )}
      </div>
      {error && <p className="form-error">{error}</p>}
      <section className="panel">
        {!trips ? (
          <div className="panel-pad"><Loading what="trips" /></div>
        ) : trips.length === 0 ? (
          <div className="empty">
            <p>No saved trips yet. Plan a trip and save it to get advisories before you leave.</p>
            <Link className="btn" to="/plan">Plan a trip</Link>
          </div>
        ) : (
          <ul className="list">
            {trips.map((t) => {
              const a = t.last_assessment;
              const best = a?.routes?.find((r) => r.id === a.recommended_route_id);
              return (
                <li key={t.id} className="trip-row">
                  <div>
                    <h3>{t.label || `${t.origin_name.split(",")[0]} to ${t.dest_name.split(",")[0]}`}</h3>
                    <p className="route-line">{t.origin_name.split(",")[0]} to {t.dest_name.split(",")[0]}, {MODE_LABEL[t.mode] ?? t.mode}</p>
                    <p className="small muted">{schedule(t)}</p>
                    {best && (
                      <p className="small" style={{ marginTop: 6, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                        Last check: peak AQI {best.peak_aqi} on {best.summary} <CatChip aqi={best.avg_aqi} />
                      </p>
                    )}
                    {a?.suggestions?.[0] && <p className="small muted">{a.suggestions[0].text}</p>}
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <Link className="btn secondary small" to={href(t)}>Check again</Link>
                    <button className="btn danger small" type="button" onClick={() => remove(t)} aria-label={`Delete ${t.label || "trip"}`}>
                      <Icon name="trash" size={16} />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </>
  );
}
