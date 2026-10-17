/* Storefront and admin app shells are cached; all API data remains network-only. */
const CACHE = 'hasret-zeytincilik-v2';
const SHELL = ['/', '/admin', '/manifest.webmanifest', '/admin.webmanifest'];
const MAX_ENTRIES = 160;

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL).catch(() => {})).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});

async function trim(cache) {
  const keys = await cache.keys();
  if (keys.length <= MAX_ENTRIES) return;
  await Promise.all(keys.slice(0, keys.length - MAX_ENTRIES).map(key => cache.delete(key)));
}

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;
  if (request.mode === 'navigate') {
    const cacheKey = url.pathname === '/admin' || url.pathname.startsWith('/admin/') ? '/admin' : '/';
    event.respondWith(fetch(request)
      .then(response => { caches.open(CACHE).then(cache => cache.put(cacheKey, response.clone())).catch(() => {}); return response; })
      .catch(async () => {
        const cache = await caches.open(CACHE);
        const hit = await cache.match(cacheKey) || await cache.match('/') || await cache.match(request);
        return hit || new Response('Çevrimdışı', { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
      }));
    return;
  }
  event.respondWith(caches.match(request).then(hit => hit || fetch(request).then(response => {
    if (response && response.ok && response.type === 'basic') {
      const copy = response.clone();
      caches.open(CACHE).then(cache => cache.put(request, copy).then(() => trim(cache))).catch(() => {});
    }
    return response;
  }).catch(() => hit || Response.error())));
});
