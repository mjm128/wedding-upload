self.addEventListener('install', (event) => {
    event.waitUntil(
      caches.open('wedding-app-v1').then((cache) => {
        return cache.addAll([
          '/',
          '/static/style.css',
          '/static/manifest.json'
        ]);
      })
    );
  });

  self.addEventListener('fetch', (event) => {
    event.respondWith(
      caches.match(event.request).then((response) => {
        return response || fetch(event.request);
      })
    );
  });
