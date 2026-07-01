/**
 * MediSafe Clinic - API 클라이언트
 * JWT 토큰 자동 첨부, 인증 만료 자동 처리
 */
import axios from 'axios'

const API_BASE = '/api/v1'

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

// 요청 인터셉터: JWT 토큰 자동 첨부
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 응답 인터셉터: 401 시 자동 로그아웃
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_info')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ── 인증 API ────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  me: () => api.get('/auth/me'),
  changePassword: (current_password: string, new_password: string) =>
    api.post('/auth/change-password', { current_password, new_password }),
}

// ── 대시보드 API ─────────────────────────────────────
export const dashboardApi = {
  getSummary: () => api.get('/dashboard/summary'),
  getAlerts: () => api.get('/dashboard/alerts'),
}

// ── SafeEndpoint API ─────────────────────────────────
export const endpointApi = {
  list: () => api.get('/endpoints/'),
  get: (id: number) => api.get(`/endpoints/${id}`),
  create: (data: {
    hostname: string; ip_address?: string; os_type: string;
    os_version?: string; location?: string
  }) => api.post('/endpoints/', data),
  deactivate: (id: number) => api.delete(`/endpoints/${id}`),
}

// ── SafeLog API ──────────────────────────────────────
export const logApi = {
  list: (params: {
    event_type?: string; severity?: string; start_date?: string;
    end_date?: string; user_email?: string; keyword?: string;
    page?: number; page_size?: number;
  }) => api.get('/logs/', { params }),
  create: (data: object) => api.post('/logs/', data),
  getSummary: () => api.get('/logs/summary'),
  exportCsv: (start_date?: string, end_date?: string) => {
    const params = new URLSearchParams()
    if (start_date) params.append('start_date', start_date)
    if (end_date) params.append('end_date', end_date)
    const token = localStorage.getItem('access_token')
    window.open(`${API_BASE}/logs/export/csv?${params.toString()}&token=${token}`)
  },
}

// ── SafeGuard API ────────────────────────────────────
export const complianceApi = {
  listItems: (regulation?: string) =>
    api.get('/compliance/items', { params: regulation ? { regulation } : {} }),
  listChecks: () => api.get('/compliance/checks'),
  createCheck: (endpointId?: number) => api.post('/compliance/checks', null, {
    params: endpointId ? { endpoint_id: endpointId } : {}
  }),
  getCheckDetail: (id: number) => api.get(`/compliance/checks/${id}`),
  updateResults: (checkId: number, updates: Array<{
    item_id: number; status: string; evidence?: string; note?: string
  }>) => api.put(`/compliance/checks/${checkId}/results`, updates),
  getPendingItems: (checkId: number) => api.get(`/compliance/checks/${checkId}/pending`),
}

export default api

// Named export for convenience (F5, F9, F12 features)
export const apiClient = api

