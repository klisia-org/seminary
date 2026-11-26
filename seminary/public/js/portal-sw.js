// The site's service worker (decisions/121 §3 and its addendum). Served at /sw.js
// so its scope is every portal on the site. It only shows notifications and opens
// the right page when one is clicked: nothing is cached, so no portal ever serves
// a stale page from here.

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
	// Reuse a tab already in the same portal (/seminary, /desk...), else open one.
	const portal = (url) => new URL(url).pathname.split("/")[1];
	event.waitUntil(
		(async () => {
			const windows = await self.clients.matchAll({
				type: "window",
				includeUncontrolled: true,
			});
			const same = windows.find(
				(c) => portal(c.url) === portal(target.href) && "focus" in c
			);
			if (same) {
				await same.focus();
				if ("navigate" in same) await same.navigate(target.href);
				return;
			}
			await self.clients.openWindow(target.href);
		})()
	);
});
