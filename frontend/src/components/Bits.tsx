import { CATS, catFor } from "../lib/aqi";
import { ago } from "../lib/format";
import { useSession } from "../lib/session";

export function AqiBlock({ aqi, label = true }: { aqi: number; label?: boolean }) {
  const c = catFor(aqi);
  return (
    <span className="aqi-block" style={{ background: c.color, color: c.ink }}>
      <span className="n">{aqi}</span>
      {label && <span className="l">{c.label}</span>}
    </span>
  );
}

export function CatChip({ aqi }: { aqi: number }) {
  const c = catFor(aqi);
  return (
    <span className="chip">
      <i style={{ background: c.color }} />
      {c.label}
    </span>
  );
}

export function Legend() {
  return (
    <div className="legend" aria-label="AQI scale">
      {CATS.map((c) => (
        <span key={c.key} style={{ background: c.color, color: c.ink }}>
          {c.low}-{c.high}
        </span>
      ))}
    </div>
  );
}

export function DataNote() {
  const { meta } = useSession();
  if (!meta?.latest_reading) return null;
  return (
    <p className="data-note">
      Readings updated {ago(meta.latest_reading)}.{" "}
      {meta.data_mode === "simulated" && <b>Demo data: no live station feed is connected.</b>}
    </p>
  );
}

export function Loading({ what }: { what: string }) {
  return <p className="muted" role="status">Loading {what}...</p>;
}
