/**
 * Insilo PWA service worker — minimal app-shell + runtime cache.
 *
 * Strategy:
 *  - Static assets (Next.js _next/static/*, fonts, icons): cache-first.
 *  - HTML navigations: network-first, fall back to cached / offline shell.
 *  - API calls (/api/* + audio presigned URLs): always go to network.
 *
 * Bump CACHE_VERSION to force clients to refresh after a release.
 */

const CACHE_VERSION = "v1";
const STATIC_CACHE = `insilo-static-${CACHE_VERSION}`;
const HTML_CACHE = `insilo-html-${CACHE_VERSION}`;

const PRECACHE = ["/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(
        names
          .filter((n) => !n.endsWith(CACHE_VERSION))
          .map((n) => caches.delete(n)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Never cache API or cross-origin (signed MinIO URLs etc.)
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  // HTML navigations: network-first, fall back to cache.
  if (req.mode === "navigate") {
    event.respondWith(
      (async () => {
        try {
          const fresh = await fetch(req);
          const cache = await caches.open(HTML_CACHE);
          cache.put(req, fresh.clone());
          return fresh;
        } catch {
          const cached = await caches.match(req);
          if (cached) return cached;
          // Final fallback: the bare root, if we've ever seen it.
          const root = await caches.match("/");
          if (root) return root;
          return new Response("Sie sind offline.", {
            status: 503,
            headers: { "Content-Type": "text/plain; charset=utf-8" },
          });
        }
      })(),
    );
    return;
  }

  // Static assets: cache-first.
  if (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname.startsWith("/_next/image")
  ) {
    event.respondWith(
      (async () => {
        const cached = await caches.match(req);
        if (cached) return cached;
        try {
          const fresh = await fetch(req);
          const cache = await caches.open(STATIC_CACHE);
          cache.put(req, fresh.clone());
          return fresh;
        } catch {
          if (cached) return cached;
          throw new Error("offline + asset uncached");
        }
      })(),
    );
  }
});
