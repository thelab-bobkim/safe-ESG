/**
 * MediSafe Clinic - 메인 앱 컴포넌트
 * 라우팅 및 인증 상태 관리
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Login from './pages/Login'
import Layout from './pages/Layout'
import Dashboard from './pages/Dashboard'
import Endpoints from './pages/Endpoints'
import Logs from './pages/Logs'
import Compliance from './pages/Compliance'

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
    // 저장된 사용자 정보 복원
    const stored = localStorage.getItem('user_info')
    const token = localStorage.getItem('access_token')
    if (stored && token) {
      setUser(JSON.parse(stored))
    }
    setLoading(false)
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

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            user ? <Navigate to="/" replace /> : <Login onLogin={setUser} />
          }
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
          <Route index element={<Dashboard />} />
          <Route path="endpoints" element={<Endpoints />} />
          <Route path="logs" element={<Logs />} />
          <Route path="compliance" element={<Compliance />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
