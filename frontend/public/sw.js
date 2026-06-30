/**
 * MediSafe Clinic - Service Worker (F7 PWA)
 * 오프라인 캐시 및 네트워크 우선 전략
 */

const CACHE_NAME = 'medisafe-v2.0'
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
]

// 설치: 정적 자원 캐시
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS).catch(err => {
        console.warn('[SW] 캐시 추가 실패 (일부 자원):', err)
      })
    })
  )
  self.skipWaiting()
})

// 활성화: 이전 캐시 제거
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
      )
    )
  )
  self.clients.claim()
})

// Fetch: API 요청은 네트워크 우선, 나머지는 캐시 우선
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url)

  // API 요청: 항상 네트워크 (캐시 안 함)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(event.request))
    return
  }

  // 정적 자원: 캐시 우선, 없으면 네트워크
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached
      return fetch(event.request).then(response => {
        // 성공한 GET 요청만 캐시
        if (response.ok && event.request.method === 'GET') {
          const cloned = response.clone()
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, cloned))
        }
        return response
      }).catch(() => {
        // 오프라인 폴백
        return caches.match('/index.html')
      })
    })
  )
})

// 푸시 알림 (향후 확장)
self.addEventListener('push', event => {
  if (!event.data) return
  const data = event.data.json()
  self.registration.showNotification(data.title || 'MediSafe 알림', {
    body: data.body || '',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    tag: 'medisafe-notification',
  })
})
