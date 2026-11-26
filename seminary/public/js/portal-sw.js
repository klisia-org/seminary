// The portal's service worker (decisions/121 §3). Served at /seminary/sw.js so
// its scope is the whole portal. It only shows notifications and opens the
// portal when one is clicked: nothing is cached, so the portal never serves a
// stale page from here.

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
	let data = {};
	try {
		data = event.data ? event.data.json() : {};
	} catch (e) {
		data = { title: event.data ? event.data.text() : "" };
	}
	const title = data.title || "New message";
	event.waitUntil(
		self.registration.showNotification(title, {
			body: data.body || "",
			tag: data.tag || undefined,
			icon: "/assets/seminary/images/portal-icon-192.png",
			data: { url: data.url || "/seminary/" },
		})
	);
});

self.addEventListener("notificationclick", (event) => {
	event.notification.close();
	const target = new URL(
		(event.notification.data && event.notification.data.url) || "/seminary/",
		self.location.origin
	);
	// Only ever open this site's own pages.
	if (target.origin !== self.location.origin) return;
	event.waitUntil(
		(async () => {
			const windows = await self.clients.matchAll({
				type: "window",
				includeUncontrolled: true,
			});
			for (const client of windows) {
				if (client.url.startsWith(self.registration.scope) && "focus" in client) {
					await client.focus();
					if ("navigate" in client) await client.navigate(target.href);
					return;
				}
			}
			await self.clients.openWindow(target.href);
		})()
	);
});
