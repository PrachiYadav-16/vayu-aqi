const paths: Record<string, string> = {
  now: "M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4M8 12a4 4 0 108 0 4 4 0 00-8 0",
  plan: "M6 19a2 2 0 100-4 2 2 0 000 4zM18 9a2 2 0 100-4 2 2 0 000 4zM6 15V9a3 3 0 013-3h3M18 9v6a3 3 0 01-3 3h-3",
  trips: "M4 6h16M4 12h16M4 18h10",
  alerts: "M6 16V11a6 6 0 1112 0v5l2 2H4l2-2zM10 20a2 2 0 004 0",
  history: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  settings: "M4 7h10M18 7h2M4 17h4M12 17h8M14 4v6M8 14v6",
  locate: "M12 2v3M12 19v3M2 12h3M19 12h3M12 18a6 6 0 100-12 6 6 0 000 12zM12 14a2 2 0 100-4 2 2 0 000 4z",
  swap: "M7 4v16M7 4L3 8M7 4l4 4M17 20V4M17 20l-4-4M17 20l4-4",
  close: "M6 6l12 12M18 6L6 18",
  trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
  window: "M5 3h14v18H5zM12 3v18M5 12h14",
  purifier: "M7 3h10a2 2 0 012 2v14a2 2 0 01-2 2H7a2 2 0 01-2-2V5a2 2 0 012-2zM9 7h6M9 10h6M12 18a2.5 2.5 0 100-5 2.5 2.5 0 000 5z",
  lungs: "M12 3v9M12 12c-1.5 0-2.5 1-3.5 3S7 20 5 20s-2-3-2-6 2-8 5-8c2 0 2 2 2 3M12 12c1.5 0 2.5 1 3.5 3S17 20 19 20s2-3 2-6-2-8-5-8c-2 0-2 2-2 3",
  wind: "M3 8h11a3 3 0 10-3-3M3 12h15a3 3 0 11-3 3M3 16h7",
};

export function Icon({ name, size = 20 }: { name: keyof typeof paths | string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={paths[name] ?? ""} />
    </svg>
  );
}

export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="12" fill="#0B5E6B" />
      <rect x="10" y="40" width="9" height="12" fill="#2E9E4F" />
      <rect x="21" y="34" width="9" height="18" fill="#9ACD32" />
      <rect x="32" y="26" width="9" height="26" fill="#E8C21C" />
      <rect x="43" y="16" width="9" height="36" fill="#EE8B1E" />
    </svg>
  );
}
