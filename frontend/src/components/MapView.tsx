import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import { api } from "../lib/api";
import { catFor } from "../lib/aqi";
import { useT, type Key } from "../lib/i18n";
import type { RouteOption, StationRow } from "../lib/types";

interface Grid {
  south: number;
  west: number;
  north: number;
  east: number;
  rows: number;
  cols: number;
  values: (number | null)[][];
}

interface Props {
  center: [number, number];
  zoom?: number;
  stations?: StationRow[];
  you?: [number, number] | null;
  surfaceHour?: number | null; // null hides the surface
  routes?: RouteOption[];
  selectedRoute?: number | null;
  onPick?: (lat: number, lon: number) => void;
  onStation?: (s: StationRow) => void;
  fitTo?: [number, number][] | null;
}

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function gridImage(g: Grid): string {
  const c = document.createElement("canvas");
  c.width = g.cols;
  c.height = g.rows;
  const ctx = c.getContext("2d")!;
  const img = ctx.createImageData(g.cols, g.rows);
  for (let r = 0; r < g.rows; r++) {
    for (let col = 0; col < g.cols; col++) {
      const v = g.values[g.rows - 1 - r][col]; // row 0 is south; canvas row 0 is north
      const i = (r * g.cols + col) * 4;
      if (v == null) {
        img.data[i + 3] = 0;
        continue;
      }
      const [R, G, B] = hexToRgb(catFor(v).color);
      img.data.set([R, G, B, 115], i);
    }
  }
  ctx.putImageData(img, 0, 0);
  return c.toDataURL();
}

export function MapView({ center, zoom = 12, stations, you, surfaceHour, routes, selectedRoute, onPick, onStation, fitTo }: Props) {
  const { t } = useT();
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layers = useRef<{ stations?: L.LayerGroup; you?: L.Marker; surface?: L.ImageOverlay; routes?: L.LayerGroup }>({});
  const pickRef = useRef(onPick);
  pickRef.current = onPick;

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { zoomControl: true, attributionControl: true }).setView(center, zoom);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => pickRef.current?.(e.latlng.lat, e.latlng.lng));
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    map.current?.setView(center, map.current.getZoom() < 9 ? zoom : map.current.getZoom());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center[0], center[1]]);

  // Station markers: small squares with the number printed on them.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    layers.current.stations?.remove();
    if (!stations?.length) return;
    const g = L.layerGroup();
    for (const s of stations) {
      const cat = catFor(s.aqi);
      const icon = L.divIcon({
        className: "",
        html: `<div class="station-marker" style="background:${cat.color};color:${cat.ink}">${s.aqi}</div>`,
        iconSize: [34, 24],
        iconAnchor: [17, 12],
      });
      const mk = L.marker([s.lat, s.lon], { icon, title: `${s.name}: AQI ${s.aqi}`, keyboard: true });
      mk.bindPopup(`<b>${s.name}</b><br>${t("map.station_popup", { city: s.city })}<br>AQI ${s.aqi}, ${t(`cat.${cat.key}` as Key)}`);
      if (onStation) mk.on("click", () => onStation(s));
      g.addLayer(mk);
    }
    g.addTo(m);
    layers.current.stations = g;
  }, [stations, onStation, t]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    layers.current.you?.remove();
    if (!you) return;
    const icon = L.divIcon({ className: "", html: '<div class="you-marker"></div>', iconSize: [18, 18], iconAnchor: [9, 9] });
    layers.current.you = L.marker(you, { icon, title: "You", zIndexOffset: 1000 }).addTo(m);
  }, [you]);

  // Interpolated surface, refetched when the view or hour changes.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    let cancelled = false;
    const load = async () => {
      layers.current.surface?.remove();
      layers.current.surface = undefined;
      if (surfaceHour == null || m.getZoom() < 9) return;
      const b = m.getBounds();
      try {
        const g = await api<Grid>(
          `/api/air/grid?south=${b.getSouth()}&west=${b.getWest()}&north=${b.getNorth()}&east=${b.getEast()}&hour=${surfaceHour}&cells=32`
        );
        if (cancelled) return;
        (layers.current.surface as L.ImageOverlay | undefined)?.remove();
        layers.current.surface = L.imageOverlay(gridImage(g), [[g.south, g.west], [g.north, g.east]], {
          opacity: 1,
          className: "aqi-surface",
          interactive: false,
        }).addTo(m);
        layers.current.surface.bringToBack();
      } catch {
        /* zoomed out too far or no data: just show stations */
      }
    };
    load();
    m.on("moveend", load);
    return () => {
      cancelled = true;
      m.off("moveend", load);
    };
  }, [surfaceHour]);

  // Routes: each segment coloured by forecast AQI at the minute you pass it.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    layers.current.routes?.remove();
    if (!routes?.length) return;
    const g = L.layerGroup();
    const ordered = [...routes].sort((a, b) => (a.id === selectedRoute ? 1 : 0) - (b.id === selectedRoute ? 1 : 0));
    for (const r of ordered) {
      const selected = r.id === selectedRoute;
      if (!selected) {
        g.addLayer(L.polyline(r.geometry, { color: "#7b858e", weight: 5, opacity: 0.55 }));
        continue;
      }
      g.addLayer(L.polyline(r.geometry, { color: "#1f262d", weight: 10, opacity: 0.9 }));
      for (let i = 0; i < r.strip.length - 1; i++) {
        const a = r.strip[i];
        const b = r.strip[i + 1];
        g.addLayer(L.polyline([[a.lat, a.lon], [b.lat, b.lon]], { color: catFor(a.aqi).color, weight: 6, opacity: 1 }));
      }
    }
    g.addTo(m);
    layers.current.routes = g;
  }, [routes, selectedRoute]);

  useEffect(() => {
    if (map.current && fitTo && fitTo.length > 1) {
      map.current.fitBounds(L.latLngBounds(fitTo), { padding: [36, 36] });
    }
  }, [fitTo]);

  return <div ref={el} className="map" aria-label="Map" />;
}
