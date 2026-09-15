self.addEventListener("push", (event) => {
  const data = event.data?.json() || { title: "IIT Management", body: "You have a new update." };
  event.waitUntil(self.registration.showNotification(data.title, {
    body: data.body,
    data: { url: data.url || "/" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow(event.notification.data.url));
});
