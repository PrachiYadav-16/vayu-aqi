const IST = "Asia/Kolkata";

export function hourLabel(iso: string): string {
  return new Date(iso)
    .toLocaleTimeString("en-IN", { hour: "numeric", hour12: true, timeZone: IST })
    .replace(" ", " ")
    .toLowerCase();
}

export function timeLabel(iso: string): string {
  return new Date(iso)
    .toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", hour12: true, timeZone: IST })
    .toLowerCase();
}

export function dayLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", timeZone: IST });
}

export function ago(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  if (h < 24) return `${h} h ago`;
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

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function formatDose(ug: number): string {
  return ug >= 100 ? `${Math.round(ug)} µg` : `${ug.toFixed(1)} µg`;
}
