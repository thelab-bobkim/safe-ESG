/**
 * MediSafe Clinic - 레이아웃 (사이드바 + 헤더)
 */
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { Shield, Monitor, FileText, ClipboardCheck, LogOut, Bell, ChevronRight } from 'lucide-react'
import type { UserInfo } from '../App'

interface Props {
  user: UserInfo
  onLogout: () => void
}

const navItems = [
  { to: '/', label: '대시보드', icon: Shield, exact: true },
  { to: '/endpoints', label: 'SafeEndpoint', icon: Monitor },
  { to: '/logs', label: 'SafeLog', icon: FileText },
  { to: '/compliance', label: 'SafeGuard', icon: ClipboardCheck },
]

export default function Layout({ user, onLogout }: Props) {
  const location = useLocation()

  const getPageTitle = () => {
    if (location.pathname === '/') return '보안 대시보드'
    if (location.pathname === '/endpoints') return 'SafeEndpoint — 엔드포인트 보안'
    if (location.pathname === '/logs') return 'SafeLog — 접속 기록 관리'
    if (location.pathname === '/compliance') return 'SafeGuard — 규제 점검'
    return 'MediSafe Clinic'
  }

  const roleLabel = user.role === 'admin' ? '원장' : user.role === 'superadmin' ? '시스템관리자' : '직원'

  return (
    <div className="flex h-screen bg-gray-50">
      {/* 사이드바 */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        {/* 로고 */}
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-bold text-gray-900 text-sm">MediSafe Clinic</p>
              <p className="text-xs text-blue-600">Beta v0.1</p>
            </div>
          </div>
        </div>

        {/* 병원명 */}
        <div className="px-4 py-3 mx-3 mt-3 bg-blue-50 rounded-lg">
          <p className="text-xs text-blue-600 font-medium">현재 병원</p>
          <p className="text-sm font-semibold text-gray-800 truncate">연세가정의원</p>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, label, icon: Icon, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* 사용자 정보 */}
        <div className="p-4 border-t border-gray-100">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-800 truncate">{user.name}</p>
              <p className="text-xs text-gray-500">{roleLabel}</p>
            </div>
            <button
              onClick={onLogout}
              title="로그아웃"
              className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* 메인 콘텐츠 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* 헤더 */}
        <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span>MediSafe</span>
            <ChevronRight className="w-3 h-3" />
            <span className="text-gray-800 font-medium">{getPageTitle()}</span>
          </div>
          <div className="flex items-center gap-3">
            <button className="relative p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
            </button>
            <div className="text-right">
              <p className="text-sm font-medium text-gray-800">{user.name}</p>
              <p className="text-xs text-gray-500">{roleLabel}</p>
            </div>
          </div>
        </header>

        {/* 페이지 콘텐츠 */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
