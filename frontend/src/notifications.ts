import { api, json } from "./api";

function rememberEndpoint(endpoint: string | null): void {
  try {
    if (endpoint) localStorage.setItem("wolsar.push-endpoint", endpoint);
    else localStorage.removeItem("wolsar.push-endpoint");
  } catch {}
}
function previousEndpoint(): string | null {
  try {
    return localStorage.getItem("wolsar.push-endpoint");
  } catch {
    return null;
  }
}

export function supportsPush(): boolean {
  return (
    window.isSecureContext &&
    "Notification" in window &&
    "serviceWorker" in navigator &&
    "PushManager" in window
  );
}
export async function syncNotifications(): Promise<boolean> {
  if (!supportsPush()) return false;
  const registration = await navigator.serviceWorker.getRegistration("/");
  const subscription = await registration?.pushManager.getSubscription();
  if (!subscription) {
    const previous = previousEndpoint();
    if (previous)
      await api(
        "/portal/push/state",
        json("POST", { endpoint: previous, permission: "default" }),
      );
    return false;
  }
  if (Notification.permission === "granted") {
    await api(
      "/portal/push/subscriptions",
      json("POST", subscription.toJSON()),
    );
    rememberEndpoint(subscription.endpoint);
    return true;
  }
  await api(
    "/portal/push/state",
    json("POST", {
      endpoint: subscription.endpoint,
      permission: Notification.permission,
    }),
  );
  return false;
}
export async function enableNotifications(): Promise<void> {
  if (!supportsPush())
    throw new Error(
      "Для уведомлений нужен поддерживаемый браузер и HTTPS. На iPhone откройте сайт с домашнего экрана.",
    );
  const permission = await Notification.requestPermission();
  if (permission !== "granted")
    throw new Error(
      "Разрешите уведомления в настройках сайта в браузере, затем попробуйте снова.",
    );
  const config = await api<{ available: boolean; public_key: string }>(
    "/portal/push/config",
  );
  if (!config.available)
    throw new Error(
      "Администратору сервера нужно настроить отправку уведомлений.",
    );
  await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  const registration = await navigator.serviceWorker.ready;
  let subscription = await registration.pushManager.getSubscription();
  if (!subscription) {
    const encoded = config.public_key.replace(/-/g, "+").replace(/_/g, "/");
    const decoded = atob(encoded + "=".repeat((4 - (encoded.length % 4)) % 4));
    const key = Uint8Array.from(decoded, (char) => char.charCodeAt(0));
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: key,
    });
  }
  await api("/portal/push/subscriptions", json("POST", subscription.toJSON()));
  rememberEndpoint(subscription.endpoint);
}
export async function disableNotifications(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  const registration = await navigator.serviceWorker.getRegistration("/");
  const subscription = await registration?.pushManager.getSubscription();
  if (!subscription) return;
  try {
    await api(
      "/portal/push/subscriptions",
      json("DELETE", {
        endpoint: subscription.endpoint,
        permission: "default",
      }),
    );
  } finally {
    await subscription.unsubscribe();
    rememberEndpoint(null);
  }
}
export async function checkNotification(): Promise<void> {
  const registration = await navigator.serviceWorker.getRegistration("/");
  const subscription = await registration?.pushManager.getSubscription();
  if (!subscription) throw new Error("Сначала подключите уведомления");
  await api(
    "/portal/push/check",
    json("POST", {
      endpoint: subscription.endpoint,
      permission: Notification.permission,
    }),
  );
}
