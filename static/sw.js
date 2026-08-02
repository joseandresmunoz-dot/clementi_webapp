const CACHE = "microbiota-v4";
const OFFLINE_URL = "/offline/";

const PRECACHE_URLS = [
  "/",
  "/manifest.json",
  OFFLINE_URL,
  "/static/css/main.css",
  "/static/css/styles.css",
  "/static/js/script.js",
  "/static/js/pwa-install.js",
  "/static/js/push-subscribe.js",
  "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Montserrat:wght@500;600;700;800&display=swap",
  "/static/images/favicon/favicon.ico",
  "/static/images/favicon/favicon-16x16.png",
  "/static/images/favicon/favicon-32x32.png",
  "/static/images/favicon/android-chrome-192x192.png",
  "/static/images/favicon/android-chrome-512x512.png",
  "/static/images/favicon/apple-touch-icon.png",
  "/static/images/logo.png",
  "/static/images/logorcblanco.png",
  "/static/images/microbiota600x700.png",
  "/static/images/microbiota1900.png",
  "/static/images/rc_frente.png",
  "/static/images/consultas.png",
  "/static/images/programa.png",
  "/static/images/test.png",
  "/static/images/meditacion.png",
  // Especialidades
  "/static/images/alergia_migrana.svg",
  "/static/images/ansiedad.svg",
  "/static/images/candidiasis.svg",
  "/static/images/diarrea.svg",
  "/static/images/digestiones_pesadas.svg",
  "/static/images/disbiosis.svg",
  "/static/images/enfermedad_inflamatoria.svg",
  "/static/images/fatiga.svg",
  "/static/images/gastritis.svg",
  "/static/images/intestino_irritable.svg",
  "/static/images/neurodesarrollo.svg",
  "/static/images/obesidad.svg",
  "/static/images/onicomicosis.svg",
  "/static/images/parasitosis.svg",
  "/static/images/piel.svg",
  "/static/images/vaginitis.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

// Aviso de actualización para forzar skipWaiting desde la app
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  // Navegación: red primero, cache como respaldo, offline como último recurso
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() =>
          caches
            .match(request)
            .then((cached) => cached || caches.match(OFFLINE_URL))
        )
    );
    return;
  }

  // Estáticos propios + CDNs con CORS (fuentes, bootstrap): stale-while-revalidate
  const cacheable = url.origin === self.location.origin ||
    url.origin === "https://fonts.googleapis.com" ||
    url.origin === "https://fonts.gstatic.com" ||
    url.origin === "https://cdn.jsdelivr.net";

  if (cacheable) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const fetchPromise = fetch(request)
          .then((response) => {
            if (
              response &&
              (response.status === 200 || response.type === "opaque")
            ) {
              const clone = response.clone();
              caches.open(CACHE).then((cache) => cache.put(request, clone));
            }
            return response;
          })
          .catch(() => cached);
        return cached || fetchPromise;
      })
    );
  }
});

self.addEventListener("push", (event) => {
  let data = {
    title: "Microbiota y Salud",
    body: "Nueva notificación",
    icon: "/static/images/favicon/android-chrome-192x192.png",
  };
  if (event.data) {
    try {
      data = event.data.json();
    } catch {
      data.body = event.data.text();
    }
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: data.icon || "/static/images/favicon/android-chrome-192x192.png",
      badge: "/static/images/favicon/favicon-32x32.png",
      data: data.url ? { url: data.url } : {},
      requireInteraction: !!data.requireInteraction,
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/";
  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windowClients) => {
        for (const client of windowClients) {
          if (client.url === url && "focus" in client) return client.focus();
        }
        return clients.openWindow(url);
      })
  );
});
