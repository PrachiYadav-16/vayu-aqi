import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, getToken, post, setToken } from "./api";
import { useT, type Lang } from "./i18n";
import type { Meta, Profile } from "./types";

interface Position {
  lat: number;
  lon: number;
  accuracy: number;
  at: number;
}

interface SessionValue {
  user: Profile | null;
  loading: boolean;
  meta: Meta | null;
  position: Position | null;
  positionError: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; name: string; password: string; sensitivity: string[]; language: Lang }) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  setUser: (p: Profile) => void;
  locateOnce: () => void;
}

const Ctx = createContext<SessionValue | null>(null);
const PING_EVERY_MS = 10 * 60 * 1000;

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [positionError, setPositionError] = useState<string | null>(null);
  const lastPing = useRef(0);
  const { setLang, t } = useT();

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api<Profile>("/api/me");
      setUser(me);
      if (me.language) setLang(me.language);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [setLang]);

  useEffect(() => {
    refresh();
    api<Meta>("/api/air/meta").then(setMeta).catch(() => setMeta(null));
  }, [refresh]);

  const onPosition = useCallback(
    (p: GeolocationPosition) => {
      const pos = { lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy, at: Date.now() };
      setPosition(pos);
      setPositionError(null);
      if (user?.location_consent && Date.now() - lastPing.current > PING_EVERY_MS) {
        lastPing.current = Date.now();
        post("/api/me/location", { lat: pos.lat, lon: pos.lon, accuracy_m: pos.accuracy }).catch(() => undefined);
      }
    },
    [user?.location_consent]
  );

  const onPositionError = useCallback((e: GeolocationPositionError) => {
    setPositionError(
      e.code === e.PERMISSION_DENIED
        ? t("loc.blocked")
        : t("loc.unavailable")
    );
  }, [t]);

  // Watch position only after the user has said yes in Settings or onboarding.
  useEffect(() => {
    if (!user?.location_consent || !("geolocation" in navigator)) return;
    const id = navigator.geolocation.watchPosition(onPosition, onPositionError, {
      enableHighAccuracy: false,
      maximumAge: 5 * 60 * 1000,
      timeout: 20000,
    });
    return () => navigator.geolocation.clearWatch(id);
  }, [user?.location_consent, onPosition, onPositionError]);

  const locateOnce = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setPositionError(t("loc.unsupported"));
      return;
    }
    navigator.geolocation.getCurrentPosition(onPosition, onPositionError, { timeout: 15000 });
  }, [onPosition, onPositionError, t]);

  const login = async (email: string, password: string) => {
    const t = await api<{ access_token: string }>("/api/auth/token", {
      method: "POST",
      form: { username: email, password },
    });
    setToken(t.access_token);
    await refresh();
  };

  const register = async (data: { email: string; name: string; password: string; sensitivity: string[]; language: Lang }) => {
    const t = await post<{ access_token: string }>("/api/auth/register", data);
    setToken(t.access_token);
    await refresh();
  };

  const logout = () => {
    setToken(null);
    setUser(null);
  };

  return (
    <Ctx.Provider
      value={{ user, loading, meta, position, positionError, login, register, logout, refresh, setUser, locateOnce }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useSession() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession outside provider");
  return v;
}
