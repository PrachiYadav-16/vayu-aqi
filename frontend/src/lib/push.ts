import { post } from "./api";

const cfg = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY as string | undefined,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN as string | undefined,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID as string | undefined,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID as string | undefined,
  appId: import.meta.env.VITE_FIREBASE_APP_ID as string | undefined,
};
const vapidKey = import.meta.env.VITE_FIREBASE_VAPID_KEY as string | undefined;

export const fcmConfigured = Boolean(cfg.apiKey && cfg.projectId && cfg.messagingSenderId && cfg.appId && vapidKey);

export function notificationsSupported() {
  return "Notification" in window && "serviceWorker" in navigator;
}

export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator) || import.meta.env.DEV) return null;
  try {
    return await navigator.serviceWorker.register("/sw.js");
  } catch {
    return null;
  }
}

/**
 * Ask for notification permission and, when Firebase is configured, register
 * this device's FCM token with the backend. Returns a short status string.
 */
export async function enablePush(): Promise<"enabled" | "local-only" | "denied" | "unsupported"> {
  if (!notificationsSupported()) return "unsupported";
  const perm = await Notification.requestPermission();
  if (perm !== "granted") return "denied";
  if (!fcmConfigured) return "local-only";
  const reg = (await navigator.serviceWorker.getRegistration()) ?? (await registerServiceWorker());
  if (!reg) return "local-only";
  const { initializeApp } = await import("firebase/app");
  const { getMessaging, getToken } = await import("firebase/messaging");
  const app = initializeApp(cfg as Record<string, string>);
  const token = await getToken(getMessaging(app), { vapidKey, serviceWorkerRegistration: reg });
  await post("/api/me/devices", { token, platform: "web" });
  return "enabled";
}

/** Fallback when FCM is not configured: show new alerts while the app is open. */
export async function showLocal(title: string, body: string) {
  if (!notificationsSupported() || Notification.permission !== "granted") return;
  const reg = await navigator.serviceWorker.getRegistration();
  if (reg) reg.showNotification(title, { body, icon: "/icons/icon-192.png", tag: title });
  else new Notification(title, { body });
}
