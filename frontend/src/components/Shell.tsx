import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../lib/api";
import { fcmConfigured, showLocal } from "../lib/push";
import { useSession } from "../lib/session";
import type { AlertItem } from "../lib/types";
import { BrandMark, Icon } from "./Icon";

const NAV = [
  { to: "/", label: "Air now", icon: "now", end: true },
  { to: "/plan", label: "Plan a trip", icon: "plan" },
  { to: "/trips", label: "Saved trips", icon: "trips" },
  { to: "/alerts", label: "Alerts", icon: "alerts" },
  { to: "/exposure", label: "My exposure", icon: "history" },
  { to: "/settings", label: "Settings", icon: "settings" },
];
const TABS = [
  { to: "/", label: "Now", icon: "now", end: true },
  { to: "/plan", label: "Plan", icon: "plan" },
  { to: "/trips", label: "Trips", icon: "trips" },
  { to: "/alerts", label: "Alerts", icon: "alerts" },
  { to: "/settings", label: "You", icon: "settings" },
];

function useUnreadAlerts() {
  const [unread, setUnread] = useState(0);
  const seen = useRef<number | null>(null);
  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const r = await api<{ unread: number; alerts: AlertItem[] }>("/api/alerts?limit=5");
        if (stop) return;
        setUnread(r.unread);
        const newest = r.alerts[0]?.id ?? 0;
        // Without FCM, surface new alerts as local notifications while the app is open.
        if (seen.current != null && newest > seen.current && !fcmConfigured) {
          r.alerts.filter((a) => a.id > (seen.current ?? 0) && !a.read).forEach((a) => showLocal(a.title, a.body));
        }
        seen.current = newest;
      } catch {
        /* offline */
      }
    };
    tick();
    const id = window.setInterval(tick, 120000);
    const onFocus = () => tick();
    window.addEventListener("focus", onFocus);
    window.addEventListener("vayu:alerts-changed", onFocus);
    return () => {
      stop = true;
      window.clearInterval(id);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("vayu:alerts-changed", onFocus);
    };
  }, []);
  return unread;
}

export function Shell() {
  const { user, logout } = useSession();
  const unread = useUnreadAlerts();
  const count = (to: string): ReactNode =>
    to === "/alerts" && unread > 0 ? <span className="navcount" aria-label={`${unread} unread`}>{unread}</span> : null;

  return (
    <div className="shell">
      <aside className="rail">
        <NavLink to="/" className="brand" aria-label="Vayu home">
          <BrandMark />
          <span className="brand-name">Vayu</span>
        </NavLink>
        <nav aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `navlink${isActive ? " active" : ""}`}>
              <Icon name={n.icon} />
              {n.label}
              {count(n.to)}
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          <strong>{user?.name}</strong>
          Alerts above AQI {user?.threshold}
          <br />
          <button type="button" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="main" id="main">
        <Outlet />
      </main>
      <nav className="tabbar" aria-label="Main">
        {TABS.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? "active" : "")}>
            <Icon name={n.icon} size={22} />
            {n.label}
            {count(n.to)}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
