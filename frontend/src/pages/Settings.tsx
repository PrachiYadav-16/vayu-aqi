import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, del, patch } from "../lib/api";
import { enablePush, fcmConfigured, notificationsSupported } from "../lib/push";
import { useSession } from "../lib/session";
import type { Profile } from "../lib/types";

interface Group {
  key: string;
  label: string;
  threshold: number;
}

const HOURS = Array.from({ length: 24 }, (_, h) => ({ h, label: `${h % 12 || 12} ${h < 12 ? "am" : "pm"}` }));

export function SettingsPage() {
  const { user, setUser, logout, position, locateOnce } = useSession();
  const [groups, setGroups] = useState<Group[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [pushState, setPushState] = useState<string | null>(null);

  useEffect(() => {
    api<Group[]>("/api/me/sensitivity-groups").then(setGroups).catch(() => undefined);
  }, []);

  if (!user) return null;

  const save = async (data: Partial<Profile> & { clear_custom_threshold?: boolean }, note = "Saved.") => {
    try {
      setUser(await patch<Profile>("/api/me", data));
      setMsg(note);
      window.setTimeout(() => setMsg(null), 2500);
    } catch (e) {
      setMsg((e as Error).message);
    }
  };

  const toggleGroup = (k: string, on: boolean) =>
    save({ sensitivity: on ? [...user.sensitivity, k] : user.sensitivity.filter((s) => s !== k) });

  const push = async () => {
    const r = await enablePush();
    setPushState(
      r === "enabled" ? "Notifications are on for this device."
        : r === "local-only" ? "Notifications are on while Vayu is open. Background push needs Firebase configured on the server."
        : r === "denied" ? "Notifications are blocked. Allow them for this site in your browser settings."
        : "This browser does not support notifications."
    );
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p>{user.name}, {user.email}</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link className="btn secondary" to="/exposure">My exposure</Link>
          <button className="btn quiet" type="button" onClick={logout}>Sign out</button>
        </div>
      </div>
      {msg && <p className="data-note" role="status" style={{ marginBottom: 12 }}>{msg}</p>}

      <div className="stack" style={{ maxWidth: 760 }}>
        <section className="panel" aria-labelledby="health-h">
          <div className="panel-head">
            <h2 id="health-h">Health profile</h2>
            <span className="hint">Alerts above AQI {user.threshold}</span>
          </div>
          <div className="panel-pad stack">
            <p className="small muted">Pick anything that applies to you or someone you travel with. The strictest one sets your alert level.</p>
            <div className="groups">
              {groups.map((g) => (
                <label key={g.key} className="check">
                  <input type="checkbox" checked={user.sensitivity.includes(g.key)} onChange={(e) => toggleGroup(g.key, e.target.checked)} />
                  <span>
                    {g.label}
                    <small>Alerts above AQI {g.threshold}</small>
                  </span>
                </label>
              ))}
            </div>
            <label className="field" style={{ maxWidth: 320 }}>
              <span>Set your own alert level</span>
              <select className="select" value={user.custom_threshold ?? ""}
                onChange={(e) => (e.target.value ? save({ custom_threshold: Number(e.target.value) }) : save({ clear_custom_threshold: true }))}>
                <option value="">Use my health profile ({user.custom_threshold ? "off" : user.threshold})</option>
                {[50, 75, 100, 125, 150, 200, 250, 300].map((v) => <option key={v} value={v}>AQI {v}</option>)}
              </select>
              <span className="help">Overrides the level from your health profile.</span>
            </label>
          </div>
        </section>

        <section className="panel" aria-labelledby="loc-h">
          <div className="panel-head"><h2 id="loc-h">Location</h2></div>
          <div className="panel-pad">
            <div className="switch-row">
              <div>
                <strong>Share my location with Vayu</strong>
                <p>Used to warn you about the air where you are and to build your exposure history. Stored for 30 days.</p>
              </div>
              <input className="toggle" type="checkbox" aria-label="Share my location" checked={user.location_consent}
                onChange={(e) => {
                  if (!e.target.checked && !window.confirm("Turning this off deletes your stored location history. Continue?")) return;
                  save({ location_consent: e.target.checked }, e.target.checked ? "Location sharing is on." : "Location sharing is off and history is deleted.");
                  if (e.target.checked) locateOnce();
                }} />
            </div>
            <div className="switch-row">
              <div>
                <strong>Home location</strong>
                <p>{user.home_lat != null ? `Set (${user.home_lat.toFixed(3)}, ${user.home_lon?.toFixed(3)})` : "Not set. Used when your live location is unavailable."}</p>
              </div>
              <button className="btn secondary small" type="button" disabled={!position}
                onClick={() => position && save({ home_lat: position.lat, home_lon: position.lon }, "Home saved.")}>
                {position ? "Set to where I am" : "Waiting for location"}
              </button>
            </div>
            <div className="switch-row">
              <div>
                <strong>Location history</strong>
                <p>Remove every stored location point now.</p>
              </div>
              <button className="btn danger small" type="button"
                onClick={async () => {
                  if (!window.confirm("Delete all stored location history?")) return;
                  await del("/api/me/location");
                  setMsg("Location history deleted.");
                }}>
                Delete history
              </button>
            </div>
          </div>
        </section>

        <section className="panel" aria-labelledby="notif-h">
          <div className="panel-head"><h2 id="notif-h">Notifications</h2></div>
          <div className="panel-pad">
            <div className="switch-row">
              <div>
                <strong>Push notifications</strong>
                <p>Alerts reach this device when the air crosses your level.{!fcmConfigured && " Background push is not configured on this server, so alerts show while the app is open."}</p>
              </div>
              <input className="toggle" type="checkbox" aria-label="Push notifications" checked={user.notify_push}
                onChange={(e) => save({ notify_push: e.target.checked })} />
            </div>
            {user.notify_push && notificationsSupported() && (
              <div className="switch-row">
                <div>
                  <strong>This device</strong>
                  <p>{pushState ?? (Notification.permission === "granted" ? "Allowed." : "Not allowed yet.")}</p>
                </div>
                <button className="btn secondary small" type="button" onClick={push}>Allow on this device</button>
              </div>
            )}
            <div className="switch-row">
              <div>
                <strong>Trip advisories</strong>
                <p>Up to 3 hours before a saved trip, if the air is bad or a cleaner route or time exists.</p>
              </div>
              <input className="toggle" type="checkbox" aria-label="Trip advisories" checked={user.notify_trip_advisories}
                onChange={(e) => save({ notify_trip_advisories: e.target.checked })} />
            </div>
            <div className="switch-row">
              <div>
                <strong>Quiet hours</strong>
                <p>No push in this window. Alerts still appear in the Alerts list.</p>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <select className="select" aria-label="Quiet hours start" value={user.quiet_start_hour ?? ""} style={{ width: 96 }}
                  onChange={(e) => save({ quiet_start_hour: e.target.value === "" ? null : Number(e.target.value), quiet_end_hour: user.quiet_end_hour ?? 7 })}>
                  <option value="">Off</option>
                  {HOURS.map((h) => <option key={h.h} value={h.h}>{h.label}</option>)}
                </select>
                <span>to</span>
                <select className="select" aria-label="Quiet hours end" value={user.quiet_end_hour ?? ""} style={{ width: 96 }}
                  disabled={user.quiet_start_hour == null} onChange={(e) => save({ quiet_end_hour: Number(e.target.value) })}>
                  <option value="">-</option>
                  {HOURS.map((h) => <option key={h.h} value={h.h}>{h.label}</option>)}
                </select>
              </div>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
