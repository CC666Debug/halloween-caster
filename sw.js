// Keeps the app's own files on the phone so it opens instantly, even with no signal.
// The page itself is fetched fresh when online (so updates show up right away, even though
// GitHub Pages tells browsers they may reuse it for 10 minutes);
// the saved copy is only used when the network fails. Streams and song info are never cached.
const CACHE = 'hc-v2';   // bump when cached files change (v2: new app icon)
const FILES = ['./', 'index.html', 'manifest.webmanifest', 'favicon.png', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;

  if (req.mode === 'navigate') {
    // Network first for the page, falling back to the saved copy.
    e.respondWith(
      fetch(req, { cache: 'no-cache' })   // always ask the server; a quick "not modified" if unchanged
        .then(res => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then(c => c.put('./', copy));
          }
          return res;
        })
        .catch(() => caches.match('./'))
    );
    return;
  }

  // Icons and the manifest: saved copy first.
  e.respondWith(caches.match(req).then(hit => hit || fetch(req)));
});
