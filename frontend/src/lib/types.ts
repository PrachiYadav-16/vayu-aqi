export type CategoryKey = "good" | "satisfactory" | "moderate" | "poor" | "very_poor" | "severe";

export interface Category {
  key: CategoryKey;
  label: string;
  low: number;
  high: number;
  color: string;
  impact: string;
}

export interface Meta {
  categories: Category[];
  pollutants: Record<string, string>;
  data_mode: "live" | "simulated";
  data_source?: "openaq" | "waqi" | "open-meteo" | "simulated";
  push_enabled: boolean;
  latest_reading: string | null;
  model: {
    version: string;
    trained_at?: string;
    test_mae?: number;
    persistence_mae?: number;
    interval_coverage?: number;
  };
  cities: string[];
}

export interface HourForecast {
  ts: string;
  aqi: number;
  low: number;
  high: number;
  category: CategoryKey;
}

export interface PointForecast {
  lat: number;
  lon: number;
  issued_at: string;
  current_aqi: number;
  category: CategoryKey;
  dominant_pollutant: string | null;
  pollutants: Record<string, number>;
  sub_indices: Record<string, number>;
  hours: HourForecast[];
  nearest_station_km: number;
  coverage: "good" | "fair" | "outside";
  method: string;
  station?: { id: string; name: string; city: string };
}

export interface StationRow {
  id: string;
  name: string;
  city: string;
  lat: number;
  lon: number;
  aqi: number;
  category: CategoryKey;
  next_24h: number[];
}

export interface Profile {
  id: number;
  email: string;
  name: string;
  sensitivity: string[];
  custom_threshold: number | null;
  threshold: number;
  home_lat: number | null;
  home_lon: number | null;
  location_consent: boolean;
  notify_push: boolean;
  notify_trip_advisories: boolean;
  quiet_start_hour: number | null;
  quiet_end_hour: number | null;
  language: "en" | "hi" | "kn";
  notify_daily_brief: boolean;
  brief_hour: number;
}

export interface Budget {
  budget_ug: number;
  used_ug: number;
  projected_ug: number;
  used_pct: number;
  projected_pct: number;
  cigarettes_used: number;
  cigarettes_projected: number;
  tracked_hours: number;
  estimated: boolean;
}

export interface HomeAdvice {
  windows: { action: "open" | "brief" | "closed"; text: string; from: string; to: string; aqi: number };
  purifier: { action: "run" | "optional"; text: string; from?: string; to?: string; aqi: number };
}

export interface Explanation {
  trend: "up" | "down" | "flat";
  change: number;
  summary: string;
  factors: { factor: string; direction: "up" | "down"; effect: number; text: string }[];
}

export interface Here extends PointForecast {
  advice: {
    level: "ok" | "caution" | "avoid";
    headline: string;
    actions: string[];
    threshold: number;
    next_breach: { ts: string; aqi: number } | null;
    cleanest_hour: { ts: string; aqi: number };
  };
  budget: Budget;
  home: HomeAdvice | null;
  explain: Explanation | null;
}

export interface Place {
  name: string;
  lat: number;
  lon: number;
  source?: string;
}

export interface StripPoint {
  minute: number;
  lat: number;
  lon: number;
  aqi: number;
  category: CategoryKey;
}

export interface RouteOption {
  id: number;
  summary: string;
  provider: string;
  distance_km: number;
  duration_min: number;
  avg_aqi: number;
  peak_aqi: number;
  category: CategoryKey;
  dose_ug: number;
  cigarettes: number;
  minutes_above_threshold: number;
  is_fastest: boolean;
  is_cleanest: boolean;
  geometry: [number, number][];
  strip: StripPoint[];
  coverage: string;
}

export interface Suggestion {
  type: "route" | "departure" | "mask";
  text: string;
  route_id?: number;
  shift_min?: number;
  depart_at?: string;
  dose_reduction_pct?: number;
  extra_minutes?: number;
}

export interface Assessment {
  depart_at: string;
  mode: string;
  mode_label: string;
  threshold: number;
  verdict: "go" | "caution" | "reconsider";
  headline: string;
  actions: string[];
  routes: RouteOption[];
  recommended_route_id: number;
  departure_scan: { shift_min: number; depart_at: string; dose_ug: number; avg_aqi: number; peak_aqi: number }[];
  suggestions: Suggestion[];
  forecast_issued_at: string;
  approximate_geometry: boolean;
}

export interface Trip {
  id: number;
  label: string;
  origin_name: string;
  origin_lat: number;
  origin_lon: number;
  dest_name: string;
  dest_lat: number;
  dest_lon: number;
  depart_at: string;
  mode: string;
  repeat_weekdays: number[];
  last_assessment: Partial<Assessment> | null;
}

export interface AlertItem {
  id: number;
  kind: string;
  severity: "info" | "warning" | "critical";
  title: string;
  body: string;
  data: Record<string, unknown>;
  created_at: string;
  read: boolean;
}
