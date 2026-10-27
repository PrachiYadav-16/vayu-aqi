import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BrandMark } from "../components/Icon";
import { LanguageSelect } from "../components/Shell";
import { api } from "../lib/api";
import { CATS } from "../lib/aqi";
import { useT, type Key } from "../lib/i18n";
import { useSession } from "../lib/session";

function Side() {
  const { t } = useT();
  return (
    <div className="auth-side">
      <div className="auth-top">
        <div className="brand"><BrandMark /><span className="brand-name">Vayu</span></div>
        <LanguageSelect />
      </div>
      <div style={{ position: "relative", zIndex: 1 }}>
        <h1>{t("auth.headline")}</h1>
        <p>{t("auth.lede")}</p>
      </div>
      <div className="auth-scale" aria-label="CPCB AQI">
        {CATS.map((c) => (
          <div key={c.key}>
            <i style={{ background: c.color }} />
            <span>{t("auth.scale", { label: t(`cat.${c.key}` as Key), lo: c.low, hi: c.high })}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function LoginPage() {
  const { login } = useSession();
  const { t } = useT();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      nav("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <Side />
      <div className="auth-form">
        <div className="card">
          <h2 style={{ marginBottom: 16 }}>{t("auth.signin")}</h2>
          <form onSubmit={submit}>
            <label className="field"><span>{t("auth.email")}</span>
              <input className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label className="field"><span>{t("auth.password")}</span>
              <input className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="btn" type="submit" disabled={busy}>{busy ? t("auth.signing") : t("auth.signin")}</button>
          </form>
          <p className="switch" style={{ marginTop: 16 }}>{t("auth.new")} <Link to="/register">{t("auth.create")}</Link></p>
        </div>
      </div>
    </div>
  );
}

interface Group {
  key: string;
  threshold: number;
}

export function RegisterPage() {
  const { register } = useSession();
  const { t, lang } = useT();
  const nav = useNavigate();
  const [groups, setGroups] = useState<Group[]>([]);
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [sens, setSens] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Group[]>("/api/me/sensitivity-groups").then(setGroups).catch(() => undefined);
  }, []);

  const threshold = sens.length ? Math.min(...groups.filter((g) => sens.includes(g.key)).map((g) => g.threshold)) : 200;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register({ ...form, sensitivity: sens, language: lang });
      nav("/settings");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <Side />
      <div className="auth-form">
        <div className="card">
          <h2 style={{ marginBottom: 16 }}>{t("auth.create_title")}</h2>
          <form onSubmit={submit}>
            <label className="field"><span>{t("auth.name")}</span>
              <input className="input" autoComplete="name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <label className="field"><span>{t("auth.email")}</span>
              <input className="input" type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </label>
            <label className="field"><span>{t("auth.password")}</span>
              <input className="input" type="password" autoComplete="new-password" minLength={8} required value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })} />
              <span className="help">{t("auth.pw_help")}</span>
            </label>
            <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
              <span>{t("auth.applies")}</span>
              <span className="help">{t("auth.applies_help")}</span>
              <div className="groups">
                {groups.map((g) => (
                  <label key={g.key} className="check">
                    <input type="checkbox" checked={sens.includes(g.key)}
                      onChange={(e) => setSens(e.target.checked ? [...sens, g.key] : sens.filter((s) => s !== g.key))} />
                    <span>{t(`grp.${g.key}` as Key)}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <p className="small muted">{t("auth.will_alert", { t: threshold })}</p>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="btn" type="submit" disabled={busy}>{busy ? t("auth.creating") : t("auth.create")}</button>
          </form>
          <p className="switch" style={{ marginTop: 16 }}>{t("auth.have")} <Link to="/login">{t("auth.signin")}</Link></p>
        </div>
      </div>
    </div>
  );
}
