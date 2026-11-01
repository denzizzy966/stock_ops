// Service worker Stock Ops — runtime caching (SPA hash-routing di /stock_ops).
// Disajikan dari root (/stock_ops_sw.js) supaya scope "/stock_ops" (tanpa slash akhir) diizinkan.
// Tujuan: app-shell + aset ter-cache → app bisa diluncurkan offline.
// Data (api/files) TIDAK di-cache di sini; ditangani layer offline app (IndexedDB + outbox).

const CACHE = 'stockops-v4'
const APP_SHELL = '/stock_ops'

self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (e) => {
  e.waitUntil(
    (async () => {
      const keys = await caches.keys()
      await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      await self.clients.claim()
    })()
  )
})

self.addEventListener('fetch', (e) => {
  const req = e.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)

  // Navigasi membuka app → network-first, fallback ke shell yang ter-cache (offline launch)
  if (req.mode === 'navigate') {
    e.respondWith(
      (async () => {
        try {
          const fresh = await fetch(req)
          const c = await caches.open(CACHE)
          c.put(APP_SHELL, fresh.clone())
          return fresh
        } catch {
          return (await caches.match(APP_SHELL)) || Response.error()
        }
      })()
    )
    return
  }

  // Aset app (JS/CSS/img) → stale-while-revalidate
  if (url.pathname.startsWith('/assets/stock_ops/')) {
    e.respondWith(
      (async () => {
        const c = await caches.open(CACHE)
        const cached = await c.match(req)
        const network = fetch(req)
          .then((res) => {
            if (res && res.ok) c.put(req, res.clone())
            return res
          })
          .catch(() => null)
        return cached || (await network) || Response.error()
      })()
    )
  }
  // /api, /files, dll → biarkan ke jaringan (ditangani app)
})

// ===== Push notification =====
self.addEventListener('push', (e) => {
  let data = {}
  try {
    data = e.data ? e.data.json() : {}
  } catch {
    data = { body: e.data && e.data.text ? e.data.text() : '' }
  }
  const title = data.title || 'Stock Ops'
  e.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || '',
      icon: '/assets/stock_ops/stock_ops/icon-192.png',
      badge: '/assets/stock_ops/stock_ops/icon-192.png',
      data: { url: data.url || '/stock_ops' }
    })
  )
})

self.addEventListener('notificationclick', (e) => {
  e.notification.close()
  const url = (e.notification.data && e.notification.data.url) || '/stock_ops'
  e.waitUntil(
    (async () => {
      const all = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      for (const c of all) {
        if (c.url.includes('/stock_ops') && 'focus' in c) return c.focus()
      }
      if (self.clients.openWindow) return self.clients.openWindow(url)
    })()
  )
})
