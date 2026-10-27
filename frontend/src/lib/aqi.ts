import type { CategoryKey } from "./types";

// CPCB National AQI colours, slightly adjusted for contrast on screens.
export const CATS: { key: CategoryKey; label: string; low: number; high: number; color: string; ink: string }[] = [
  { key: "good", label: "Good", low: 0, high: 50, color: "#2E9E4F", ink: "#ffffff" },
  { key: "satisfactory", label: "Satisfactory", low: 51, high: 100, color: "#9ACD32", ink: "#15211F" },
  { key: "moderate", label: "Moderate", low: 101, high: 200, color: "#E8C21C", ink: "#15211F" },
  { key: "poor", label: "Poor", low: 201, high: 300, color: "#EE8B1E", ink: "#15211F" },
  { key: "very_poor", label: "Very poor", low: 301, high: 400, color: "#D8342B", ink: "#ffffff" },
  { key: "severe", label: "Severe", low: 401, high: 500, color: "#7E1F23", ink: "#ffffff" },
];

export function catFor(aqi: number | null | undefined) {
  if (aqi == null || Number.isNaN(aqi)) return CATS[0];
  const a = Math.max(0, Math.min(500, Math.round(aqi)));
  return CATS.find((c) => a <= c.high) ?? CATS[CATS.length - 1];
}

export function catByKey(k: CategoryKey) {
  return CATS.find((c) => c.key === k) ?? CATS[0];
}

export const POLLUTANT_NAMES: Record<string, string> = {
  pm25: "PM2.5",
  pm10: "PM10",
  no2: "NO₂",
  o3: "O₃",
  co: "CO",
  so2: "SO₂",
};

export const POLLUTANT_UNITS: Record<string, string> = {
  pm25: "µg/m³",
  pm10: "µg/m³",
  no2: "µg/m³",
  o3: "µg/m³",
  co: "mg/m³",
  so2: "µg/m³",
};
