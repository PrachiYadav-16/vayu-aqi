import type { Lang, TFn } from "./i18n";

const IST = "Asia/Kolkata";
let lang: Lang = "en";

export function setFormatLang(l: Lang) {
  lang = l;
}

const PERIODS: Record<Exclude<Lang, "en">, [number, string][]> = {
  hi: [[5, "सुबह"], [12, "दोपहर"], [16, "शाम"], [20, "रात"]],
  kn: [[5, "ಬೆಳಿಗ್ಗೆ"], [12, "ಮಧ್ಯಾಹ್ನ"], [16, "ಸಂಜೆ"], [20, "ರಾತ್ರಿ"]],
};

function istParts(iso: string | Date) {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  const ist = new Date(d.getTime() + 5.5 * 3600 * 1000);
  return { h: ist.getUTCHours(), m: ist.getUTCMinutes() };
}

function clock(iso: string | Date, withMinutes: boolean): string {
  const { h, m } = istParts(iso);
  const h12 = h % 12 || 12;
  const c = withMinutes ? `${h12}:${String(m).padStart(2, "0")}` : `${h12}`;
  if (lang === "en") return `${c} ${h < 12 ? "am" : "pm"}`;
  let period = PERIODS[lang][3][1];
  for (const [start, name] of PERIODS[lang]) if (h >= start) period = name;
  if (h < 5) period = PERIODS[lang][3][1];
  return `${period} ${c}${lang === "hi" ? " बजे" : ""}`;
}

export const hourLabel = (iso: string) => clock(iso, false);
export const timeLabel = (iso: string) => clock(iso, true);

/** Short axis label: "2 pm" in English, "2" with the period word dropped elsewhere. */
export function axisLabel(iso: string): string {
  if (lang === "en") return clock(iso, false);
  const { h } = istParts(iso);
  return `${h % 12 || 12}`;
}

const LOCALE: Record<Lang, string> = { en: "en-IN", hi: "hi-IN", kn: "kn-IN" };

export function dayLabel(iso: string): string {
  return new Date(iso).toLocaleDateString(LOCALE[lang], {
    weekday: "short", day: "numeric", month: "short", timeZone: IST, numberingSystem: "latn",
  });
}

export function ago(iso: string, t: TFn): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return t("time.just_now");
  if (mins < 60) return t("time.min_ago", { n: mins });
  const h = Math.round(mins / 60);
  if (h < 24) return t("time.h_ago", { n: h });
  return dayLabel(iso);
}

/** Value for <input type="datetime-local"> in IST. */
export function toLocalInput(d: Date): string {
  const ist = new Date(d.getTime() + 5.5 * 3600 * 1000);
  return ist.toISOString().slice(0, 16);
}

export function fromLocalInput(v: string): string {
  // Interpret the picker value as IST regardless of the device time zone.
  return new Date(`${v}:00+05:30`).toISOString();
}

export function formatDose(ug: number): string {
  return ug >= 100 ? `${Math.round(ug)} µg` : `${ug.toFixed(1)} µg`;
}

export function formatCigs(n: number): string {
  if (n < 0.1) return n === 0 ? "0" : "<0.1";
  return n < 10 ? n.toFixed(1) : String(Math.round(n));
}
