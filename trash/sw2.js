// core/templates/sw.js
const CACHE_NAME = 'baropodometria-v1';
const urlsToCache = [
  '/',
  '{% static "core/css/style.css" %}',
  '{% static "core/js/heatmap.js" %}',
  '{% static "core/images/mapa_planta_pe.png" %}'
];

// 1. Instalação: Cacheia os arquivos estáticos essenciais
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache);
    })
  );
});

// 2. Ativação: Limpa caches antigos se o nome da versão mudar
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache);
          }
        })
      );
    })
  );
});

// 3. Interceptação de Requisições: Estratégia "Cache First, Network Fallback"
self.addEventListener('fetch', (event) => {
  // Ignora requisições de API que precisam de dados sempre frescos, ou solicitações não-GET
  if (event.request.method !== 'GET' || event.request.url.includes('/api/')) {
    return; 
  }

  event.respondWith(
    caches.match(event.request).then((response) => {
      // Se estiver no cache, retorna. Se não, busca na rede.
      return response || fetch(event.request).catch(() => {
        // Fallback offline (opcional: crie uma página offline.html)
        if (event.request.mode === 'navigate') {
          return caches.match('/offline/'); 
        }
      });
    })
  );
});