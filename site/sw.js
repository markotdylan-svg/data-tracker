/* Service worker: makes the site installable and usable offline.
   - The pages, styles, scripts and icons are cached when the worker installs.
   - Every request goes to the network first; a successful reply is stored in the
     cache. When the network fails (offline), the cached copy is returned, so the
     site opens and shows the last data it loaded. */
const CACHE = "crypto-tracker-v1";
const SHELL = [
  "./", "index.html", "browse.html", "trends.html",
  "style.css", "common.js", "analysis.js", "manifest.webmanifest",
  "icons/icon-192.png", "icons/icon-512.png", "icons/maskable-512.png",
  "data/history.csv", "data/status.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  const key = new URL(req.url);
  key.search = "";  // one cache entry per file
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(key.href, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(key.href).then((hit) => hit || (req.mode === "navigate" ? caches.match("index.html") : undefined))
          .then((hit) => hit || new Response("Offline and not cached yet", { status: 503, statusText: "Offline" }))
      )
  );
});
