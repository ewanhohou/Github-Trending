// 由 trending/render.py 產生。網頁用「網路優先、離線時用快取」，圖片用「快取優先」。
<<<<<<< Updated upstream
const VERSION = "b77682967fcc";
=======
const VERSION = "53a18dfa74c1";
>>>>>>> Stashed changes
const PAGES = "pages-" + VERSION;
const IMAGES = "images-v2";
const MAX_IMAGES = 80;
const PRECACHE = ["./", "style.css", "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png", "index.html", "offline.html", "daily/2026-10-29.html", "weekly/2026-W44.html", "en/index.html", "en/offline.html", "en/manifest.webmanifest", "en/daily/2026-10-29.html", "en/weekly/2026-W44.html"];
const LANGS = ["en/"];  // 非預設語言的網址前綴，例如 ["en/"]

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(PAGES).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keep = [PAGES, IMAGES];
    // 舊版本快取裡看過的報告搬到新快取，離線時仍可閱讀
    for (const key of await caches.keys()) {
      if (keep.includes(key)) continue;
      if (key.startsWith("pages-")) {
        const [from, to] = [await caches.open(key), await caches.open(PAGES)];
        for (const req of await from.keys()) {
          if (!(await to.match(req))) await to.put(req, await from.match(req));
        }
      }
      await caches.delete(key);
    }
    await self.clients.claim();
  })());
});

const timeout = (ms) => new Promise((resolve) => setTimeout(() => resolve(null), ms));

async function networkFirst(event) {
  const cache = await caches.open(PAGES);
  const network = fetch(event.request).then((res) => {
    if (res.ok) cache.put(event.request, res.clone());
    return res;
  });
  event.waitUntil(network.catch(() => {}));
  // 網路太慢（例如捷運上）先用快取，背景仍會更新
  const fast = await Promise.race([network, timeout(4000)]).catch(() => null);
  if (fast) return fast;
  const hit = await cache.match(event.request, { ignoreSearch: true });
  if (hit) return hit;
  try {
    return await network;
  } catch (e) {
    // 轉址而不是直接回傳，離線頁的相對路徑（樣式、連結）才會正確；依網址前綴選語言
    if (event.request.mode === "navigate") {
      const scope = new URL("./", self.location).pathname;
      const rest = new URL(event.request.url).pathname.slice(scope.length);
      const prefix = LANGS.find((p) => rest.startsWith(p)) || "";
      return Response.redirect(new URL(prefix + "offline.html", self.location).href, 302);
    }
    return Response.error();
  }
}

async function trimImages(cache) {
  const keys = await cache.keys();
  for (const req of keys.slice(0, Math.max(0, keys.length - MAX_IMAGES))) await cache.delete(req);
}

async function cacheFirstImage(event) {
  const cache = await caches.open(IMAGES);
  const hit = await cache.match(event.request.url);
  if (hit) return hit;
  // 用 CORS 取圖才看得到狀態碼，只快取成功的回應；不支援 CORS 的來源（例如 camo）照常載入但不快取，
  // 避免把 429 之類的錯誤回應永久存起來
  let res;
  try {
    res = await fetch(event.request.url, { mode: "cors", credentials: "omit" });
  } catch (e) {
    return fetch(event.request);
  }
  if (res.ok) event.waitUntil(cache.put(event.request.url, res.clone()).then(() => trimImages(cache)));
  return res;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin === self.location.origin) {
    event.respondWith(networkFirst(event));
  } else if (req.destination === "image") {
    event.respondWith(cacheFirstImage(event).catch(() => Response.error()));
  }
});