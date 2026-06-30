/**
 * MediSafe Clinic - 메인 앱 컴포넌트
 * 역할별 라우팅: admin → 전체 관리 / staff → 본인 현황만
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Login from './pages/Login'
import Register from './pages/Register'
import Layout from './pages/Layout'
import AdminDashboard from './pages/AdminDashboard'
import StaffDashboard from './pages/StaffDashboard'
import Endpoints from './pages/Endpoints'
import Logs from './pages/Logs'
import Compliance from './pages/Compliance'
import MyActivity from './pages/MyActivity'
import Billing from './pages/Billing'
import GroupDashboard from './pages/GroupDashboard'
import PIA from './pages/PIA'
import { authApi } from './api/client'

export interface UserInfo {
  id: number
  email: string
  name: string
  role: string
  tenant_id: number | null
}

function App() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setLoading(false)
      return
    }
    // 항상 서버 /me로 role 재검증 (localStorage 캐시 무시)
    authApi.me()
      .then(res => {
        const { id, email, name, role, tenant_id } = res.data
        const userInfo: UserInfo = { id, email, name, role, tenant_id }
        localStorage.setItem('user_info', JSON.stringify(userInfo))
        setUser(userInfo)
      })
      .catch(() => {
        // 토큰 만료 or 오류 → 로그아웃
        localStorage.removeItem('access_token')
        localStorage.removeItem('user_info')
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500">MediSafe Clinic 로딩 중...</p>
        </div>
      </div>
    )
  }

  const isAdmin = user?.role === 'admin' || user?.role === 'superadmin'

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={user ? <Navigate to="/" replace /> : <Login onLogin={setUser} />}
        />
        <Route
          path="/register"
          element={user ? <Navigate to="/" replace /> : <Register />}
        />
        <Route
          path="/"
          element={
            user ? (
              <Layout user={user} onLogout={() => {
                localStorage.removeItem('access_token')
                localStorage.removeItem('user_info')
                setUser(null)
              }} />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        >
          {/* 역할별 대시보드 분기 */}
          <Route index element={isAdmin ? <AdminDashboard /> : <StaffDashboard />} />

          {/* 원장(admin)만 접근 가능 */}
          <Route
            path="endpoints"
            element={isAdmin ? <Endpoints /> : <Navigate to="/" replace />}
          />
          <Route
            path="logs"
            element={isAdmin ? <Logs /> : <Navigate to="/" replace />}
          />
          <Route
            path="compliance"
            element={isAdmin ? <Compliance /> : <Navigate to="/" replace />}
          />

          {/* 직원(staff)용 본인 활동 내역 */}
          <Route path="my-activity" element={<MyActivity />} />

          {/* Phase 2 & 3 기능 */}
          <Route
            path="billing"
            element={isAdmin ? <Billing /> : <Navigate to="/" replace />}
          />
          <Route
            path="groups"
            element={isAdmin ? <GroupDashboard /> : <Navigate to="/" replace />}
          />
          <Route
            path="pia"
            element={isAdmin ? <PIA /> : <Navigate to="/" replace />}
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
