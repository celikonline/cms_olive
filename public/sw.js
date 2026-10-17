/* Altın Gıda servis çalışanı: mağaza kabuğunu ve görselleri önbelleğe alır.
   /api istekleri her zaman ağdan gider; yönetici verisi ve ses kayıtları önbelleğe alınmaz. */
const CACHE = 'altin-gida-v1';
const SHELL = ['/', '/manifest.webmanifest'];
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
    event.respondWith(fetch(request)
      .then(response => { caches.open(CACHE).then(cache => cache.put('/', response.clone())).catch(() => {}); return response; })
      .catch(() => caches.match('/').then(hit => hit || caches.match(request)).then(hit => hit || new Response('Çevrimdışı', { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } }))));
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
