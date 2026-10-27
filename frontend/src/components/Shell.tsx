import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api, patch } from "../lib/api";
import { LANGS, useT, type Key, type Lang } from "../lib/i18n";
import { fcmConfigured, showLocal } from "../lib/push";
import { useSession } from "../lib/session";
import type { AlertItem, Profile } from "../lib/types";
import { BrandMark, Icon } from "./Icon";

const NAV: { to: string; label: Key; tab: Key; icon: string; end?: boolean; mobile?: boolean }[] = [
  { to: "/", label: "nav.now", tab: "tab.now", icon: "now", end: true, mobile: true },
  { to: "/plan", label: "nav.plan", tab: "tab.plan", icon: "plan", mobile: true },
  { to: "/trips", label: "nav.trips", tab: "tab.trips", icon: "trips", mobile: true },
  { to: "/alerts", label: "nav.alerts", tab: "tab.alerts", icon: "alerts", mobile: true },
  { to: "/exposure", label: "nav.exposure", tab: "nav.exposure", icon: "history" },
  { to: "/settings", label: "nav.settings", tab: "tab.you", icon: "settings", mobile: true },
];

const UnreadCtx = createContext(0);

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

export function LanguageSelect() {
  const { lang, setLang, t } = useT();
  const { user, setUser } = useSession();
  const change = async (l: Lang) => {
    setLang(l);
    if (user) {
      try {
        setUser(await patch<Profile>("/api/me", { language: l }));
      } catch {
        /* keep the local choice */
      }
    }
  };
  return (
    <select className="lang-select" aria-label={t("common.language")} value={lang} onChange={(e) => change(e.target.value as Lang)}>
      {LANGS.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
    </select>
  );
}

function TopBar() {
  const { t } = useT();
  const { user } = useSession();
  const unread = useContext(UnreadCtx);
  return (
    <div className="topbar">
      <NavLink to="/" className="brand" aria-label="Vayu">
        <BrandMark />
        <span className="brand-name">Vayu</span>
      </NavLink>
      <nav className="topnav" aria-label="Main">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? "active" : "")}>
            {t(n.label)}
            {n.to === "/alerts" && unread > 0 && <span className="navcount" aria-label={t("common.unread", { n: unread })}>{unread}</span>}
          </NavLink>
        ))}
      </nav>
      <div className="top-right">
        <LanguageSelect />
        {user && (
          <NavLink to="/settings" className="user-chip" title={t("common.alerts_above", { n: user.threshold })}>
            <span className="avatar" aria-hidden="true">{user.name.trim().charAt(0).toUpperCase()}</span>
            <span>{user.name.split(" ")[0]}</span>
          </NavLink>
        )}
      </div>
    </div>
  );
}

/** Every signed-in screen: navy band with the nav and a centred serif title, then content lifted over it. */
export function Page({ title, subtitle, note, actions, children }: {
  title: string;
  subtitle?: ReactNode;
  note?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <>
      <header className="band">
        <TopBar />
        <div className="hero">
          <h1>{title}</h1>
          {subtitle && <p>{subtitle}</p>}
          {note}
          {actions && <div className="hero-actions">{actions}</div>}
        </div>
      </header>
      <main className="wrap lift" id="main">{children}</main>
    </>
  );
}

export function Shell() {
  const { t } = useT();
  const { logout } = useSession();
  const unread = useUnreadAlerts();
  return (
    <UnreadCtx.Provider value={unread}>
      <Outlet />
      <footer className="footer">
        <div className="footer-in">
          <span>Vayu. {t("footer.note")}</span>
          <button type="button" className="btn quiet small" style={{ color: "#fff" }} onClick={logout}>{t("common.sign_out")}</button>
        </div>
      </footer>
      <nav className="tabbar" aria-label="Main">
        {NAV.filter((n) => n.mobile).map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? "active" : "")}>
            <Icon name={n.icon} size={22} />
            {t(n.tab)}
            {n.to === "/alerts" && unread > 0 && <span className="navcount">{unread}</span>}
          </NavLink>
        ))}
      </nav>
    </UnreadCtx.Provider>
  );
}
