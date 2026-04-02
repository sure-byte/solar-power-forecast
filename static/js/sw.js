const CACHE_NAME = 'amap-tiles-v1';
const TILE_REGEX = /https:\/\/webst[0-9].*\.autonavi\.com\/.*?tile/;

self.addEventListener('fetch', event => {
  if (TILE_REGEX.test(event.request.url)) {
    event.respondWith(
      caches.open(CACHE_NAME).then(cache =>
        cache.match(event.request).then(response =>
          response || fetch(event.request).then(networkResponse => {
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
          })
        )
      )
    );
  }
});
