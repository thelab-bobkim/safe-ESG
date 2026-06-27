/**
 * MediSafe Clinic - 로그인 페이지
 */
import { useState } from 'react'
import { Shield, Lock, Mail, AlertCircle } from 'lucide-react'
import { authApi } from '../api/client'
import type { UserInfo } from '../App'

interface Props {
  onLogin: (user: UserInfo) => void
}

export default function Login({ onLogin }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const res = await authApi.login(email, password)
      const { access_token, user_id, user_name, role, tenant_id } = res.data

      localStorage.setItem('access_token', access_token)
      const userInfo: UserInfo = { id: user_id, email, name: user_name, role, tenant_id }
      localStorage.setItem('user_info', JSON.stringify(userInfo))
      onLogin(userInfo)
    } catch (err: any) {
      setError(err.response?.data?.detail || '로그인에 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* 로고 영역 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl mb-4">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">MediSafe Clinic</h1>
          <p className="text-gray-500 mt-1">의료정보보호 플랫폼</p>
        </div>

        {/* 로그인 폼 */}
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-6">로그인</h2>

          {error && (
            <div className="flex items-center gap-2 bg-red-50 text-red-700 p-3 rounded-lg mb-4 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">이메일</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="doctor@clinic.kr"
                  required
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">비밀번호</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? '로그인 중...' : '로그인'}
            </button>
          </form>

          {/* 테스트 계정 안내 */}
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <p className="text-xs font-medium text-gray-600 mb-2">🔑 베타 테스트 계정</p>
            <div className="space-y-1 text-xs text-gray-500">
              <p><span className="font-medium">원장:</span> doctor@yonsei-clinic.kr / Doctor1234!</p>
              <p><span className="font-medium">직원:</span> staff@yonsei-clinic.kr / Staff1234!</p>
              <p><span className="font-medium">치과:</span> doctor@seoul-dental.kr / Doctor5678!</p>
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-gray-400 mt-4">
          © 2024 MediSafe Clinic. 의료정보보호 전문 플랫폼
        </p>
      </div>
    </div>
  )
}
