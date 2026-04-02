/**
 * 言忆 Service Worker
 * 实现离线缓存，支持 PWA 安装
 */

const CACHE_NAME = "yiyi-v1";

// 需要预缓存的静态资源
const PRECACHE_URLS = [
  "/",
  "/static/manifest.json",
];

// ── Install ────────────────────────────────────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS).catch((err) => {
        console.warn("[SW] 预缓存失败:", err);
      });
    })
  );
  self.skipWaiting();
});

// ── Activate ───────────────────────────────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch ──────────────────────────────────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // API 请求及 SSE 流 - 始终走网络，不缓存
  if (
    url.pathname.startsWith("/chat") ||
    url.pathname.startsWith("/api") ||
    url.pathname.startsWith("/history") ||
    url.pathname.startsWith("/memory") ||
    url.pathname.startsWith("/style") ||
    url.pathname.startsWith("/topic") ||
    url.pathname.startsWith("/daily") ||
    url.pathname.startsWith("/anniversaries") ||
    url.pathname.startsWith("/emotion") ||
    url.pathname.startsWith("/import") ||
    url.pathname.startsWith("/export") ||
    url.pathname.startsWith("/admin") ||
    url.pathname.startsWith("/characters") ||
    event.request.method !== "GET"
  ) {
    return; // Let the browser handle it normally
  }

  // 静态资源：Cache-First（优先缓存）
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (!response || response.status !== 200 || response.type === "opaque") {
          return response;
        }
        const cloned = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned));
        return response;
      });
    })
  );
});
