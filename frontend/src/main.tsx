import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { registerServiceWorker } from "./lib/push";
import { SessionProvider, useSession } from "./lib/session";
import { AlertsPage } from "./pages/Alerts";
import { LoginPage, RegisterPage } from "./pages/Auth";
import { ExposurePage } from "./pages/Exposure";
import { NowPage } from "./pages/Now";
import { PlanPage } from "./pages/Plan";
import { SettingsPage } from "./pages/Settings";
import { TripsPage } from "./pages/Trips";
import "./styles.css";

function RequireUser({ children }: { children: ReactNode }) {
  const { user, loading } = useSession();
  if (loading) return <p className="muted" style={{ padding: 24 }}>Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useSession();
  if (loading) return null;
  if (user) return <Navigate to="/" replace />;
  return <>{children}</>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<GuestOnly><LoginPage /></GuestOnly>} />
          <Route path="/register" element={<GuestOnly><RegisterPage /></GuestOnly>} />
          <Route element={<RequireUser><Shell /></RequireUser>}>
            <Route index element={<NowPage />} />
            <Route path="plan" element={<PlanPage />} />
            <Route path="trips" element={<TripsPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="exposure" element={<ExposurePage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  </StrictMode>
);

registerServiceWorker();
