import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loading } from "../components/Bits";
import { Page } from "../components/Shell";
import { api, post } from "../lib/api";
import { ago } from "../lib/format";
import { useT, type Key } from "../lib/i18n";
import type { AlertItem } from "../lib/types";

export function AlertsPage() {
  const { t } = useT();
  const [data, setData] = useState<{ unread: number; alerts: AlertItem[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api<{ unread: number; alerts: AlertItem[] }>("/api/alerts?limit=100").then(setData).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const changed = () => {
    window.dispatchEvent(new Event("vayu:alerts-changed"));
    load();
  };

  const markAll = async () => {
    await post("/api/alerts/read-all");
    changed();
  };

  const open = async (a: AlertItem) => {
    if (a.read) return;
    await post(`/api/alerts/${a.id}/read`);
    changed();
  };

  const brief = async () => {
    try {
      await post("/api/alerts/brief-now");
      changed();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <Page title={t("nav.alerts")} subtitle={t("alerts.subtitle")}
      actions={
        <>
          <button className="btn light" type="button" onClick={brief}>{t("alerts.brief_now")}</button>
          {data && data.unread > 0 && <button className="btn" type="button" onClick={markAll}>{t("alerts.mark_all")}</button>}
        </>
      }>
      {error && <p className="form-error" style={{ marginBottom: 12 }}>{error}</p>}
      <div className="section">
        {!data ? (
          <div className="card"><Loading /></div>
        ) : data.alerts.length === 0 ? (
          <div className="empty">
            <p>{t("alerts.empty")}</p>
            <Link className="btn secondary" to="/settings">{t("alerts.settings")}</Link>
          </div>
        ) : (
          <ul className="list">
            {data.alerts.map((a) => (
              <li key={a.id} className={`alert-row${a.read ? "" : " unread"}`} onClick={() => open(a)}>
                <span className={`sev ${a.severity}`} aria-hidden="true" />
                <div>
                  <p className="alert-kind">{t(`kind.${a.kind}` as Key)}</p>
                  <h3>{a.title}</h3>
                  <p>{a.body}</p>
                  {a.kind === "trip_advisory" && <Link className="small" to="/trips">{t("nav.trips")}</Link>}
                </div>
                <span className="tiny">{ago(a.created_at, t)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Page>
  );
}
