/**
 * MediSafe Clinic - 레이아웃
 * 역할(admin/staff)에 따라 사이드바 메뉴가 다르게 표시됩니다.
 */
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  Shield, Monitor, FileText, ClipboardCheck,
  LogOut, Bell, ChevronRight, User, Activity,
  Crown, Users
} from 'lucide-react'
import type { UserInfo } from '../App'

interface Props {
  user: UserInfo
  onLogout: () => void
}

// 원장(admin) 메뉴
const adminNavItems = [
  { to: '/', label: '보안 대시보드', icon: Shield, exact: true, badge: null },
  { to: '/endpoints', label: 'SafeEndpoint', icon: Monitor, exact: false, badge: null },
  { to: '/logs', label: 'SafeLog', icon: FileText, exact: false, badge: null },
  { to: '/compliance', label: 'SafeGuard', icon: ClipboardCheck, exact: false, badge: null },
]

// 직원(staff) 메뉴
const staffNavItems = [
  { to: '/', label: '내 보안 현황', icon: Shield, exact: true, badge: null },
  { to: '/my-activity', label: '내 활동 기록', icon: Activity, exact: false, badge: null },
]

export default function Layout({ user, onLogout }: Props) {
  const location = useLocation()
  const isAdmin = user.role === 'admin' || user.role === 'superadmin'
  const navItems = isAdmin ? adminNavItems : staffNavItems

  const getPageTitle = () => {
    const titles: Record<string, string> = {
      '/': isAdmin ? '보안 대시보드' : '내 보안 현황',
      '/endpoints': 'SafeEndpoint — 엔드포인트 보안',
      '/logs': 'SafeLog — 접속 기록',
      '/compliance': 'SafeGuard — 규제 점검',
      '/my-activity': '내 활동 기록',
    }
    return titles[location.pathname] || 'MediSafe Clinic'
  }

  const roleLabel = {
    admin: '원장',
    superadmin: '시스템관리자',
    staff: '직원',
  }[user.role] || '사용자'

  const roleColor = isAdmin ? 'bg-blue-600' : 'bg-emerald-600'
  const roleBadgeColor = isAdmin
    ? 'bg-blue-50 text-blue-700 border border-blue-100'
    : 'bg-emerald-50 text-emerald-700 border border-emerald-100'

  return (
    <div className="flex h-screen bg-gray-50">
      {/* 사이드바 */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        {/* 로고 */}
        <div className="p-5 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 ${roleColor} rounded-xl flex items-center justify-center`}>
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-bold text-gray-900 text-sm">MediSafe Clinic</p>
              <p className="text-xs text-gray-400">Beta v0.1</p>
            </div>
          </div>
        </div>

        {/* 사용자 역할 배지 */}
        <div className="px-4 pt-4 pb-2">
          <div className={`flex items-center gap-2 px-3 py-2 rounded-xl ${roleBadgeColor}`}>
            {isAdmin
              ? <Crown className="w-4 h-4 flex-shrink-0" />
              : <User className="w-4 h-4 flex-shrink-0" />
            }
            <div className="min-w-0">
              <p className="text-xs font-bold truncate">{user.name} {roleLabel}</p>
              <p className="text-xs opacity-70 truncate">{user.email}</p>
            </div>
          </div>
        </div>

        {/* 역할 설명 */}
        <div className="px-4 pb-3">
          <p className="text-xs text-gray-400">
            {isAdmin
              ? '병원 전체 보안 현황을 관리합니다'
              : '본인의 보안 상태와 활동만 볼 수 있습니다'}
          </p>
        </div>

        {/* 구분선 */}
        <div className="mx-4 border-t border-gray-100 mb-3" />

        {/* 네비게이션 */}
        <nav className="flex-1 px-3 space-y-1">
          {navItems.map(({ to, label, icon: Icon, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? `${isAdmin ? 'bg-blue-50 text-blue-700' : 'bg-emerald-50 text-emerald-700'} shadow-sm`
                    : 'text-gray-500 hover:bg-gray-50 hover:text-gray-800'
                }`
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* 하단: 플랜 정보 (admin만) */}
        {isAdmin && (
          <div className="mx-3 mb-3 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-100">
            <p className="text-xs font-semibold text-blue-700">Clinic Standard</p>
            <p className="text-xs text-blue-500 mt-0.5">14.9만원/월 · 최대 10대</p>
          </div>
        )}

        {/* 로그아웃 */}
        <div className="p-4 border-t border-gray-100">
          <button
            onClick={onLogout}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-xl transition-colors"
          >
            <LogOut className="w-4 h-4" />
            로그아웃
          </button>
        </div>
      </aside>

      {/* 메인 콘텐츠 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* 헤더 */}
        <header className="bg-white border-b border-gray-200 px-6 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Shield className="w-3.5 h-3.5" />
            <span>MediSafe</span>
            <ChevronRight className="w-3 h-3" />
            <span className="text-gray-700 font-semibold">{getPageTitle()}</span>
          </div>
          <div className="flex items-center gap-3">
            <button className="relative p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-xl transition-colors">
              <Bell className="w-4 h-4" />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-red-500 rounded-full" />
            </button>
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium ${roleBadgeColor}`}>
              {isAdmin ? <Crown className="w-3 h-3" /> : <User className="w-3 h-3" />}
              {user.name} ({roleLabel})
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
