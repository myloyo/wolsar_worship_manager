self.addEventListener("push", event => {
  let message = {};
  try { message = event.data ? event.data.json() : {}; } catch { message = {}; }
  event.waitUntil(self.registration.showNotification(message.title || "Wolsar Worship", {
    body: message.body || "Изменения в вашем расписании", tag: message.tag || "worship",
    data: {url: "/schedule"},
  }));
});
self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil(clients.matchAll({type:"window", includeUncontrolled:true}).then(async windows => {
    const url = new URL("/schedule", self.location.origin).href;
    const existing = windows.find(client => client.url.startsWith(self.location.origin + "/"));
    if (existing) { await existing.navigate(url); return existing.focus(); }
    return clients.openWindow(url);
  }));
});
