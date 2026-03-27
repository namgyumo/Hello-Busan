/**
 * sw.js — Service Worker for Hello, Busan! PWA
 * Cache strategies:
 *   - Cache First: static assets (HTML, CSS, JS, fonts, icons, locale JSON)
 *   - Network First: API responses (/api/v1/*)
 *   - Stale While Revalidate: tourist spot images
 */

const CACHE_VERSION = 'hello-busan-v1';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;
const IMAGE_CACHE = `${CACHE_VERSION}-images`;

const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/map.html',
    '/detail.html',
    '/favorites.html',
    '/offline.html',
    '/css/style.css',
    '/js/i18n.js',
    '/js/theme.js',
    '/js/home.js',
    '/js/app.js',
    '/js/map.js',
    '/js/category.js',
    '/js/recommend.js',
    '/js/sse.js',
    '/js/detail.js',
    '/js/favorites.js',
    '/js/favorites-page.js',
    '/js/offline-store.js',
    '/js/pwa.js',
    '/js/analytics.js',
    '/js/share.js',
    '/js/search.js',
    '/js/course.js',
    '/locales/ko.json',
    '/locales/en.json',
    '/locales/ja.json',
    '/locales/zh.json',
    '/locales/ru.json',
];

// Install: pre-cache static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        }).then(() => {
            return self.skipWaiting();
        })
    );
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
    const currentCaches = [STATIC_CACHE, API_CACHE, IMAGE_CACHE];
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) => !currentCaches.includes(name))
                    .map((name) => caches.delete(name))
            );
        }).then(() => {
            return self.clients.claim();
        })
    );
});

// Fetch: route requests to appropriate strategy
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') return;

    // Skip SSE connections
    if (request.headers.get('Accept') === 'text/event-stream') return;

    // API requests: Network First
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(networkFirst(request, API_CACHE));
        return;
    }

    // External image URLs or common image extensions: Stale While Revalidate
    if (isImageRequest(request, url)) {
        event.respondWith(staleWhileRevalidate(request, IMAGE_CACHE));
        return;
    }

    // Static assets: Cache First
    event.respondWith(cacheFirst(request, STATIC_CACHE));
});

/**
 * Cache First strategy
 * Try cache, fall back to network, store in cache.
 * If both fail and it's a navigation request, serve offline.html.
 */
async function cacheFirst(request, cacheName) {
    const cached = await caches.match(request);
    if (cached) return cached;

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch (err) {
        if (request.mode === 'navigate') {
            const offlinePage = await caches.match('/offline.html');
            if (offlinePage) return offlinePage;
        }
        return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
    }
}

/**
 * Network First strategy
 * Try network, cache the response. Fall back to cache on failure.
 */
async function networkFirst(request, cacheName) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch (err) {
        const cached = await caches.match(request);
        if (cached) return cached;
        return new Response(
            JSON.stringify({ success: false, error: 'offline' }),
            { status: 503, headers: { 'Content-Type': 'application/json' } }
        );
    }
}

/**
 * Stale While Revalidate strategy
 * Return cached version immediately, fetch update in background.
 */
async function staleWhileRevalidate(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);

    const fetchPromise = fetch(request).then((response) => {
        if (response.ok) {
            cache.put(request, response.clone());
        }
        return response;
    }).catch(() => null);

    return cached || (await fetchPromise) || new Response('', { status: 503 });
}

/**
 * Check if a request is for an image
 */
function isImageRequest(request, url) {
    const accept = request.headers.get('Accept') || '';
    if (accept.includes('image/')) return true;

    const imageExtensions = /\.(jpg|jpeg|png|gif|webp|svg|ico|avif)(\?.*)?$/i;
    if (imageExtensions.test(url.pathname)) return true;

    // External image hosts
    if (url.origin !== self.location.origin && accept.includes('image/')) return true;

    return false;
}

// Listen for skip waiting message from client
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});
