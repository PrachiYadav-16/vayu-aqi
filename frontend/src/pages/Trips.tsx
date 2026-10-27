import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CatChip, Loading } from "../components/Bits";
import { Icon } from "../components/Icon";
import { Page } from "../components/Shell";
import { api, del, post } from "../lib/api";
import { dayLabel, timeLabel } from "../lib/format";
import { useT, type Key, type TFn } from "../lib/i18n";
import type { Trip } from "../lib/types";
import { useRouteName } from "./Plan";

function schedule(trip: Trip, t: TFn) {
  const time = timeLabel(trip.depart_at);
  const d = trip.repeat_weekdays;
  if (!d.length) return `${dayLabel(trip.depart_at)}, ${time}`;
  if (d.length === 5 && d.every((x) => x < 5)) return t("trips.weekdays", { time });
  if (d.length === 7) return t("trips.everyday", { time });
  return `${d.map((x) => t(`day.${x}` as Key)).join(", ")}, ${time}`;
}

export function TripsPage() {
  const { t } = useT();
  const routeName = useRouteName();
  const [trips, setTrips] = useState<Trip[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const load = () => api<Trip[]>("/api/trips").then(setTrips).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const name = (tr: Trip) => tr.label || t("trips.to", { a: tr.origin_name.split(",")[0], b: tr.dest_name.split(",")[0] });

  const remove = async (tr: Trip) => {
    if (!window.confirm(t("trips.confirm_delete", { name: name(tr) }))) return;
    await del(`/api/trips/${tr.id}`);
    load();
  };

  const checkNow = async () => {
    setChecking(true);
    try {
      await post("/api/alerts/check-now");
      window.dispatchEvent(new Event("vayu:alerts-changed"));
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setChecking(false);
    }
  };

  const href = (tr: Trip) =>
    `/plan?o=${encodeURIComponent(`${tr.origin_name}|${tr.origin_lat}|${tr.origin_lon}`)}&d=${encodeURIComponent(`${tr.dest_name}|${tr.dest_lat}|${tr.dest_lon}`)}&m=${tr.mode}`;

  return (
    <Page title={t("nav.trips")} subtitle={t("trips.subtitle")}
      actions={trips && trips.length > 0 ? (
        <button className="btn" type="button" onClick={checkNow} disabled={checking}>{checking ? t("trips.checking") : t("trips.check_all")}</button>
      ) : undefined}>
      {error && <p className="form-error" style={{ marginBottom: 12 }}>{error}</p>}
      <div className="section">
        {!trips ? (
          <div className="card"><Loading /></div>
        ) : trips.length === 0 ? (
          <div className="empty">
            <p>{t("trips.empty")}</p>
            <Link className="btn" to="/plan">{t("nav.plan")}</Link>
          </div>
        ) : (
          <ul className="list">
            {trips.map((tr) => {
              const a = tr.last_assessment;
              const best = a?.routes?.find((r) => r.id === a.recommended_route_id);
              return (
                <li key={tr.id} className="trip-row">
                  <div>
                    <h3>{name(tr)}</h3>
                    <p className="small muted">{t("trips.to", { a: tr.origin_name.split(",")[0], b: tr.dest_name.split(",")[0] })}, {t(`mode.${tr.mode}` as Key)}</p>
                    <p className="small muted">{schedule(tr, t)}</p>
                    {best && (
                      <p className="small" style={{ marginTop: 6, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                        {t("trips.last", { aqi: best.peak_aqi, route: routeName(best.summary) })} <CatChip aqi={best.avg_aqi} />
                      </p>
                    )}
                    {a?.suggestions?.[0] && <p className="small muted">{a.suggestions[0].text}</p>}
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <Link className="btn secondary small" to={href(tr)}>{t("trips.again")}</Link>
                    <button className="btn danger small" type="button" onClick={() => remove(tr)} aria-label={t("trips.delete", { name: name(tr) })}>
                      <Icon name="trash" size={16} />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Page>
  );
}
