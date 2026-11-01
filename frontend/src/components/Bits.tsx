import { CATS, catFor } from "../lib/aqi";
import { ago } from "../lib/format";
import { useT, type Key } from "../lib/i18n";
import { useSession } from "../lib/session";

export function useCatLabel() {
  const { t } = useT();
  return (aqi: number) => t(`cat.${catFor(aqi).key}` as Key);
}

export function CatChip({ aqi }: { aqi: number }) {
  const label = useCatLabel();
  const c = catFor(aqi);
  return (
    <span className="chip">
      <i style={{ background: c.color }} />
      {label(aqi)}
    </span>
  );
}

export function Legend() {
  return (
    <div className="legend" aria-label="AQI scale">
      {CATS.map((c) => (
        <span key={c.key} style={{ background: c.color, color: c.ink }}>{c.low}-{c.high}</span>
      ))}
    </div>
  );
}

export function DataNote() {
  const { meta } = useSession();
  const { t } = useT();
  if (!meta?.latest_reading) return null;
  return (
    <p className="data-note">
      {t("data.updated", { ago: ago(meta.latest_reading, t) })}{" "}
      {meta.data_mode === "simulated" && <b>{t("data.demo")}</b>}
      {meta.data_source === "open-meteo" && (
        <a href="https://open-meteo.com/en/docs/air-quality-api" target="_blank" rel="noreferrer">{t("data.src_om")}</a>
      )}
    </p>
  );
}

export function Loading() {
  const { t } = useT();
  return <p className="muted" role="status">{t("common.loading")}</p>;
}
