import { useEffect, useId, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Place } from "../lib/types";

interface Props {
  label: string;
  value: Place | null;
  onChange: (p: Place | null) => void;
  near?: { lat: number; lon: number } | null;
  currentLocation?: Place | null;
}

export function PlaceInput({ label, value, onChange, near, currentLocation }: Props) {
  const id = useId();
  const [text, setText] = useState(value?.name ?? "");
  const [results, setResults] = useState<Place[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const timer = useRef<number>();

  useEffect(() => setText(value?.name ?? ""), [value?.name]);

  useEffect(() => {
    window.clearTimeout(timer.current);
    if (!open || text.trim().length < 2 || text === value?.name) {
      setResults([]);
      return;
    }
    timer.current = window.setTimeout(async () => {
      const q = new URLSearchParams({ q: text.trim() });
      if (near) {
        q.set("lat", String(near.lat));
        q.set("lon", String(near.lon));
      }
      try {
        setResults(await api<Place[]>(`/api/air/places?${q}`));
        setActive(0);
      } catch {
        setResults([]);
      }
    }, 300);
  }, [text, open, near, value?.name]);

  const options: Place[] = [...(currentLocation && open && !text ? [currentLocation] : []), ...results];

  const pick = (p: Place) => {
    onChange(p);
    setText(p.name);
    setOpen(false);
  };

  return (
    <label className="field place-input">
      <span>{label}</span>
      <input
        className="input"
        value={text}
        placeholder="Search a place or area"
        role="combobox"
        aria-expanded={open && options.length > 0}
        aria-controls={`${id}-list`}
        aria-autocomplete="list"
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onChange={(e) => {
          setText(e.target.value);
          if (value) onChange(null);
          setOpen(true);
        }}
        onKeyDown={(e) => {
          if (!options.length) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => Math.min(a + 1, options.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (e.key === "Enter") {
            e.preventDefault();
            pick(options[active]);
          } else if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && options.length > 0 && (
        <ul className="place-list" id={`${id}-list`} role="listbox">
          {options.map((p, i) => (
            <li key={`${p.name}-${i}`}>
              <button type="button" role="option" aria-selected={i === active} onMouseDown={(e) => e.preventDefault()} onClick={() => pick(p)}>
                {p.name.length > 90 ? `${p.name.slice(0, 90)}...` : p.name}
                {p.source === "device" && <span className="src"> (from this device)</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </label>
  );
}
