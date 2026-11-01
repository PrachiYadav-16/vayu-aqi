import { useEffect, useState } from "react";
import { Page } from "../components/Shell";
import { api, del, patch, post } from "../lib/api";
import { LANGS, useT, type Key, type Lang } from "../lib/i18n";
import { enablePush, fcmConfigured, notificationsSupported } from "../lib/push";
import { useSession } from "../lib/session";
import type { Profile } from "../lib/types";
import { timeLabel } from "../lib/format";

interface Group {
  key: string;
  threshold: number;
}

function hourOption(h: number) {
  // Any date works; only the IST hour matters for the label.
  const d = new Date(Date.UTC(2026, 0, 1, h, 0) - 5.5 * 3600 * 1000);
  return timeLabel(d.toISOString()).replace(":00", "");
}

export function SettingsPage() {
  const { user, setUser, logout, position, locateOnce } = useSession();
  const { t, setLang } = useT();
  const [groups, setGroups] = useState<Group[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [pushState, setPushState] = useState<string | null>(null);
  const [homeName, setHomeName] = useState<string | null>(null);

  useEffect(() => {
    api<Group[]>("/api/me/sensitivity-groups").then(setGroups).catch(() => undefined);
  }, []);

  useEffect(() => {
    setHomeName(null);
    if (user?.home_lat == null || user.home_lon == null) return;
    api<{ name: string | null }>(`/api/air/place-name?lat=${user.home_lat}&lon=${user.home_lon}`)
      .then((r) => setHomeName(r.name)).catch(() => undefined);
  }, [user?.home_lat, user?.home_lon]);

  if (!user) return null;

  const flash = (m: string) => {
    setMsg(m);
    window.setTimeout(() => setMsg(null), 3000);
  };

  const save = async (data: Partial<Profile> & { clear_custom_threshold?: boolean }, note?: string) => {
    try {
      setUser(await patch<Profile>("/api/me", data));
      flash(note ?? t("common.saved"));
    } catch (e) {
      flash((e as Error).message);
    }
  };

  const toggleGroup = (k: string, on: boolean) =>
    save({ sensitivity: on ? [...user.sensitivity, k] : user.sensitivity.filter((s) => s !== k) });

  const chooseLang = (l: Lang) => {
    setLang(l);
    save({ language: l });
  };

  const push = async () => {
    const r = await enablePush();
    setPushState(t(r === "enabled" ? "push.enabled" : r === "local-only" ? "push.local" : r === "denied" ? "push.denied" : "push.unsupported"));
  };

  const sendBrief = async () => {
    try {
      const q = position ? `?lat=${position.lat}&lon=${position.lon}` : "";
      const r = await post<{ created: unknown[] }>(`/api/alerts/brief-now${q}`);
      window.dispatchEvent(new Event("vayu:alerts-changed"));
      flash(r.created.length ? t("set.brief_sent") : t("set.brief_none"));
    } catch (e) {
      flash((e as Error).message);
    }
  };

  const deleteAccount = async () => {
    if (!window.confirm(t("set.delete_confirm"))) return;
    try {
      await del("/api/me");
      logout();
    } catch (e) {
      flash((e as Error).message);
    }
  };

  return (
    <Page title={t("nav.settings")} subtitle={`${user.name}, ${user.email}`}
      actions={<button className="btn light small" type="button" onClick={logout}>{t("common.sign_out")}</button>}>
      {msg && <div className="toast" role="status">{msg}</div>}
      <div className="section" style={{ maxWidth: 860, margin: "0 auto" }}>
        <div className="stack">
          <section className="card" aria-labelledby="lang-h">
            <h2 id="lang-h" style={{ fontSize: "1.5rem" }}>{t("common.language")}</h2>
            <p className="small muted" style={{ margin: "4px 0 12px" }}>{t("set.language_help")}</p>
            <div className="lang-cards" role="radiogroup" aria-labelledby="lang-h">
              {LANGS.map((l) => (
                <label key={l.code}>
                  <input type="radio" name="lang" checked={user.language === l.code} onChange={() => chooseLang(l.code)} />
                  <span lang={l.code}>{l.name}</span>
                </label>
              ))}
            </div>
          </section>

          <section className="card" aria-labelledby="health-h">
            <div className="section-head" style={{ margin: "0 0 6px" }}>
              <h2 id="health-h" style={{ fontSize: "1.5rem" }}>{t("set.health")}</h2>
              <span className="hint">{t("common.alerts_above", { n: user.threshold })}</span>
            </div>
            <p className="small muted" style={{ marginBottom: 12 }}>{t("set.health_help")}</p>
            <div className="groups">
              {groups.map((g) => (
                <label key={g.key} className="check">
                  <input type="checkbox" checked={user.sensitivity.includes(g.key)} onChange={(e) => toggleGroup(g.key, e.target.checked)} />
                  <span>{t(`grp.${g.key}` as Key)}<small>{t("common.alerts_above", { n: g.threshold })}</small></span>
                </label>
              ))}
            </div>
            <label className="field" style={{ maxWidth: 340, marginTop: 14 }}>
              <span>{t("set.own_level")}</span>
              <select className="select" value={user.custom_threshold ?? ""}
                onChange={(e) => (e.target.value ? save({ custom_threshold: Number(e.target.value) }) : save({ clear_custom_threshold: true }))}>
                <option value="">{t("set.use_profile", { t: user.custom_threshold ? "-" : user.threshold })}</option>
                {[50, 75, 100, 125, 150, 200, 250, 300].map((v) => <option key={v} value={v}>AQI {v}</option>)}
              </select>
              <span className="help">{t("set.own_help")}</span>
            </label>
          </section>

          <section className="card" aria-labelledby="loc-h">
            <h2 id="loc-h" style={{ fontSize: "1.5rem", marginBottom: 12 }}>{t("set.location")}</h2>
            <div className="switch-row">
              <div><strong>{t("set.share")}</strong><p>{t("set.share_help")}</p></div>
              <input className="toggle" type="checkbox" aria-label={t("set.share")} checked={user.location_consent}
                onChange={(e) => {
                  if (!e.target.checked && !window.confirm(t("set.confirm_off"))) return;
                  save({ location_consent: e.target.checked }, e.target.checked ? t("set.share_on") : t("set.share_off"));
                  if (e.target.checked) locateOnce();
                }} />
            </div>
            <div className="switch-row">
              <div>
                <strong>{t("set.home")}</strong>
                <p>{user.home_lat == null ? t("set.home_unset")
                  : homeName ? t("set.home_named", { name: homeName })
                  : t("set.home_set", { lat: user.home_lat.toFixed(3), lon: user.home_lon?.toFixed(3) ?? "" })}</p>
              </div>
              <button className="btn secondary small" type="button" disabled={!position}
                onClick={() => position && save({ home_lat: position.lat, home_lon: position.lon }, t("set.home_saved"))}>
                {position ? t("set.home_here") : t("set.home_wait")}
              </button>
            </div>
            <div className="switch-row">
              <div><strong>{t("set.history")}</strong><p>{t("set.history_help")}</p></div>
              <button className="btn danger small" type="button"
                onClick={async () => {
                  if (!window.confirm(t("set.history_confirm"))) return;
                  await del("/api/me/location");
                  flash(t("set.history_done"));
                }}>
                {t("set.history_delete")}
              </button>
            </div>
          </section>

          <section className="card" aria-labelledby="notif-h">
            <h2 id="notif-h" style={{ fontSize: "1.5rem", marginBottom: 12 }}>{t("set.notifications")}</h2>
            <div className="switch-row">
              <div><strong>{t("set.brief")}</strong><p>{t("set.brief_help")}</p></div>
              <input className="toggle" type="checkbox" aria-label={t("set.brief")} checked={user.notify_daily_brief}
                onChange={(e) => save({ notify_daily_brief: e.target.checked })} />
            </div>
            {user.notify_daily_brief && (
              <div className="switch-row">
                <label className="field inline-controls" style={{ flexDirection: "row", gap: 10 }}>
                  <span>{t("set.brief_at")}</span>
                  <select className="select" value={user.brief_hour}
                    onChange={(e) => save({ brief_hour: Number(e.target.value) })}>
                    {[5, 6, 7, 8, 9, 10].map((h) => <option key={h} value={h}>{hourOption(h)}</option>)}
                  </select>
                </label>
                <button className="btn secondary small" type="button" onClick={sendBrief}>{t("alerts.brief_now")}</button>
              </div>
            )}
            <div className="switch-row">
              <div><strong>{t("set.push")}</strong><p>{t("set.push_help")}{!fcmConfigured && t("set.push_local")}</p></div>
              <input className="toggle" type="checkbox" aria-label={t("set.push")} checked={user.notify_push}
                onChange={(e) => save({ notify_push: e.target.checked })} />
            </div>
            {user.notify_push && notificationsSupported() && (
              <div className="switch-row">
                <div>
                  <strong>{t("set.device")}</strong>
                  <p>{pushState ?? (Notification.permission === "granted" ? t("set.allowed") : t("set.not_allowed"))}</p>
                </div>
                <button className="btn secondary small" type="button" onClick={push}>{t("set.allow")}</button>
              </div>
            )}
            <div className="switch-row">
              <div><strong>{t("set.trip_adv")}</strong><p>{t("set.trip_adv_help")}</p></div>
              <input className="toggle" type="checkbox" aria-label={t("set.trip_adv")} checked={user.notify_trip_advisories}
                onChange={(e) => save({ notify_trip_advisories: e.target.checked })} />
            </div>
            <div className="switch-row">
              <div><strong>{t("set.quiet")}</strong><p>{t("set.quiet_help")}</p></div>
              <div className="inline-controls">
                <select className="select" aria-label={t("set.quiet")} value={user.quiet_start_hour ?? ""}
                  onChange={(e) => save({ quiet_start_hour: e.target.value === "" ? null : Number(e.target.value), quiet_end_hour: user.quiet_end_hour ?? 7 })}>
                  <option value="">{t("set.off")}</option>
                  {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{hourOption(h)}</option>)}
                </select>
                <span>{t("set.to")}</span>
                <select className="select" aria-label={t("set.quiet")} value={user.quiet_end_hour ?? ""}
                  disabled={user.quiet_start_hour == null} onChange={(e) => save({ quiet_end_hour: Number(e.target.value) })}>
                  <option value="">-</option>
                  {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{hourOption(h)}</option>)}
                </select>
              </div>
            </div>
          </section>

          <section className="card" aria-labelledby="acct-h">
            <h2 id="acct-h" style={{ fontSize: "1.5rem", marginBottom: 12 }}>{t("set.account")}</h2>
            <div className="switch-row">
              <div><strong>{t("set.delete")}</strong><p>{t("set.delete_help")}</p></div>
              <button className="btn danger small" type="button" onClick={deleteAccount}>{t("set.delete")}</button>
            </div>
          </section>
        </div>
      </div>
    </Page>
  );
}
