import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BrandMark } from "../components/Icon";
import { api } from "../lib/api";
import { CATS } from "../lib/aqi";
import { useSession } from "../lib/session";

function Side() {
  return (
    <div className="auth-side">
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <BrandMark />
        <span className="brand-name" style={{ color: "#fff" }}>Vayu</span>
      </div>
      <div>
        <h1>Know the air before you step out.</h1>
        <p>
          Hourly AQI forecasts for your area, the pollution on each route you might take, and a warning when the air
          crosses the level that is safe for you.
        </p>
      </div>
      <div className="auth-scale" aria-label="India National AQI scale">
        {CATS.map((c) => (
          <div key={c.key}>
            <i style={{ background: c.color }} />
            <span>{c.label}, {c.low} to {c.high}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function LoginPage() {
  const { login } = useSession();
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
        <h2>Sign in</h2>
        <form onSubmit={submit}>
          <label className="field"><span>Email</span>
            <input className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field"><span>Password</span>
            <input className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="btn" type="submit" disabled={busy}>{busy ? "Signing in..." : "Sign in"}</button>
        </form>
        <p className="switch">New to Vayu? <Link to="/register">Create an account</Link></p>
      </div>
    </div>
  );
}

interface Group {
  key: string;
  label: string;
  threshold: number;
}

export function RegisterPage() {
  const { register } = useSession();
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
      await register({ ...form, sensitivity: sens });
      nav("/settings?welcome=1");
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
        <h2>Create your account</h2>
        <form onSubmit={submit}>
          <label className="field"><span>Name</span>
            <input className="input" autoComplete="name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label className="field"><span>Email</span>
            <input className="input" type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </label>
          <label className="field"><span>Password</span>
            <input className="input" type="password" autoComplete="new-password" minLength={8} required value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <span className="help">At least 8 characters.</span>
          </label>
          <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
            <span>Does any of this apply to you?</span>
            <span className="help">Optional. It sets when Vayu warns you. You can change it later.</span>
            <div className="groups">
              {groups.map((g) => (
                <label key={g.key} className="check">
                  <input type="checkbox" checked={sens.includes(g.key)}
                    onChange={(e) => setSens(e.target.checked ? [...sens, g.key] : sens.filter((s) => s !== g.key))} />
                  <span>{g.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <p className="small muted">You will be alerted when AQI goes above <b>{threshold}</b>.</p>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="btn" type="submit" disabled={busy}>{busy ? "Creating account..." : "Create account"}</button>
        </form>
        <p className="switch">Already have an account? <Link to="/login">Sign in</Link></p>
      </div>
    </div>
  );
}
