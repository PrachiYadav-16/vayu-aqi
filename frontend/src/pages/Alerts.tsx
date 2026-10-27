import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loading } from "../components/Bits";
import { api, post } from "../lib/api";
import { ago } from "../lib/format";
import type { AlertItem } from "../lib/types";

export function AlertsPage() {
  const [data, setData] = useState<{ unread: number; alerts: AlertItem[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api<{ unread: number; alerts: AlertItem[] }>("/api/alerts?limit=100").then(setData).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const markAll = async () => {
    await post("/api/alerts/read-all");
    window.dispatchEvent(new Event("vayu:alerts-changed"));
    load();
  };

  const open = async (a: AlertItem) => {
    if (a.read) return;
    await post(`/api/alerts/${a.id}/read`);
    window.dispatchEvent(new Event("vayu:alerts-changed"));
    load();
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Alerts</h1>
          <p>Warnings when air where you are, or on a saved trip, crosses your alert level.</p>
        </div>
        {data && data.unread > 0 && <button className="btn secondary" type="button" onClick={markAll}>Mark all as read</button>}
      </div>
      {error && <p className="form-error">{error}</p>}
      <section className="panel">
        {!data ? (
          <div className="panel-pad"><Loading what="alerts" /></div>
        ) : data.alerts.length === 0 ? (
          <div className="empty">
            <p>No alerts so far. They appear here when the air crosses your alert level, and on your phone if notifications are on.</p>
            <Link className="btn secondary" to="/settings">Notification settings</Link>
          </div>
        ) : (
          <ul className="list">
            {data.alerts.map((a) => (
              <li key={a.id} className={`alert-row${a.read ? "" : " unread"}`} onClick={() => open(a)}>
                <span className={`sev ${a.severity}`} aria-hidden="true" />
                <div>
                  <h3>{a.title}</h3>
                  <p>{a.body}</p>
                  {a.kind === "trip_advisory" && <Link className="small" to="/trips">View saved trips</Link>}
                </div>
                <span className="tiny">{ago(a.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
