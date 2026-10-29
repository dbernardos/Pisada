{% load static %}// Service worker do Baropodometria.
// Servido pela view `service_worker` em /sw.js (na raiz, para controlar o site inteiro).
//
// Estratégia:
//  - Páginas (HTML):      sempre da rede. Offline -> página /offline/. Dados de pacientes NUNCA vão para o cache.
//  - Arquivos estáticos:  "stale-while-revalidate" (responde do cache e atualiza em segundo plano).
//  - API, PDF, admin etc.: não são interceptados.
//
// Ao mudar a lógica deste arquivo, aumente VERSION para limpar os caches antigos.
const VERSION = 'v2';
const CACHE_NAME = 'baropodometria-' + VERSION;

const OFFLINE_URL = '{% url "offline" %}';
const STATIC_PREFIX = '{% get_static_prefix %}';

// Arquivos pré-carregados na instalação. Um arquivo ausente não impede a instalação.
const PRECACHE_URLS = [
  OFFLINE_URL,
  '{% static "core/css/style.css" %}',
  '{% static "core/js/heatmap.js" %}',
  '{% static "core/images/logo.png" %}',
  '{% static "core/images/mapa_planta_pe.png" %}',
  '{% static "core/images/icon-192x192.png" %}'
];

// CDNs usados pelo base.html (ícones e fontes) também ficam em cache.
const CDN_HOSTS = ['cdn.jsdelivr.net', 'fonts.googleapis.com', 'fonts.gstatic.com'];

// 1. Instalação: pré-carrega o essencial para a tela offline.
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) =>
        Promise.allSettled(PRECACHE_URLS.map((url) => cache.add(url))).then((results) => {
          results.forEach((result, i) => {
            if (result.status === 'rejected') {
              console.warn('[SW] Não foi possível pré-carregar', PRECACHE_URLS[i]);
            }
          });
        })
      )
      .then(() => self.skipWaiting())
  );
});

// 2. Ativação: remove caches de versões antigas e assume as abas abertas.
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) =>
        Promise.all(names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name)))
      )
      .then(() => self.clients.claim())
  );
});

// 3. Requisições
self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Navegação entre páginas: rede primeiro; sem conexão, mostra a página offline.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match(OFFLINE_URL).then((cached) => cached || Response.error())
      )
    );
    return;
  }

  const sameOrigin = url.origin === self.location.origin;
  const isStatic = sameOrigin && url.pathname.startsWith(STATIC_PREFIX);
  const isCdn = CDN_HOSTS.includes(url.hostname);

  if (isStatic || isCdn) {
    event.respondWith(staleWhileRevalidate(request));
  }
  // Qualquer outra coisa (API, PDF, admin, mídia) segue direto para a rede.
});

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);

  const network = fetch(request)
    .then((response) => {
      if (response && (response.ok || response.type === 'opaque')) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => null);

  return cached || (await network) || Response.error();
}
