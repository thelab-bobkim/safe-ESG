/**
 * MediSafe Clinic - 직원(Staff) 전용 대시보드
 * 본인 PC 상태, 본인 접속 기록만 표시합니다.
 * 다른 직원 정보, 전체 보안 점수, 컴플라이언스 등은 보이지 않습니다.
 */
import { useState, useEffect } from 'react'
import {
  User, Monitor, FileText, CheckCircle, XCircle,
  AlertTriangle, Clock, Shield, Info, Lock
} from 'lucide-react'
import { logApi, endpointApi } from '../api/client'

interface MyLog {
  id: number
  event_type: string
  severity: string
  resource: string | null
  action: string | null
  result: string
  description: string | null
  occurred_at: string
  ip_address: string | null
}

interface Endpoint {
  id: number
  hostname: string
  ip_address: string
  location: string | null
  status: string
  security_score: number
  disk_encrypted: boolean | null
  antivirus_installed: boolean | null
  os_patched: boolean | null
  firewall_enabled: boolean | null
  screen_lock_enabled: boolean | null
  last_seen_at: string | null
}

const EVENT_LABELS: Record<string, string> = {
  emr_access: 'EMR 접속',
  emr_query: '기록 조회',
  emr_modify: '기록 수정',
  login_success: '로그인',
  login_fail: '로그인 실패',
  file_access: '파일 접근',
  admin_action: '관리 행위',
  system_event: '시스템',
}

const SEV_CLASS: Record<string, string> = {
  info: 'bg-blue-50 text-blue-700',
  warning: 'bg-yellow-50 text-yellow-700',
  critical: 'bg-red-50 text-red-700',
}

function BoolCheck({ value, label }: { value: boolean | null; label: string }) {
  if (value === null) return (
    <div className="flex items-center gap-2 p-2.5 bg-gray-50 rounded-lg">
      <Info className="w-4 h-4 text-gray-400" />
      <span className="text-sm text-gray-500">{label}</span>
      <span className="ml-auto text-xs text-gray-400">미확인</span>
    </div>
  )
  return (
    <div className={`flex items-center gap-2 p-2.5 rounded-lg ${value ? 'bg-green-50' : 'bg-red-50'}`}>
      {value
        ? <CheckCircle className="w-4 h-4 text-green-600" />
        : <XCircle className="w-4 h-4 text-red-500" />
      }
      <span className={`text-sm font-medium ${value ? 'text-green-800' : 'text-red-700'}`}>{label}</span>
      <span className={`ml-auto text-xs font-semibold ${value ? 'text-green-600' : 'text-red-600'}`}>
        {value ? '적용됨' : '미적용'}
      </span>
    </div>
  )
}

export default function StaffDashboard() {
  const [myLogs, setMyLogs] = useState<MyLog[]>([])
  const [endpoints, setEndpoints] = useState<Endpoint[]>([])
  const [logSummary, setLogSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  // 직원 본인 정보
  const userInfo = JSON.parse(localStorage.getItem('user_info') || '{}')

  useEffect(() => {
    Promise.all([
      // 본인 이메일로 필터링된 로그만 가져오기
      logApi.list({ user_email: userInfo.email, page_size: 20 }),
      logApi.getSummary(),
      endpointApi.list(),
    ]).then(([logsRes, summaryRes, epRes]) => {
      setMyLogs(logsRes.data.items || [])
      setLogSummary(summaryRes.data)
      setEndpoints(epRes.data || [])
    }).catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const myEp = endpoints[0] // 직원은 주로 1대 사용 (실제로는 본인 PC 매핑 필요)
  const scoreColor = (s: number) => s >= 80 ? 'text-green-600' : s >= 60 ? 'text-yellow-600' : 'text-red-600'
  const scoreBg = (s: number) => s >= 80 ? 'bg-green-50' : s >= 60 ? 'bg-yellow-50' : 'bg-red-50'

  if (loading) return (
    <div className="space-y-4 animate-pulse">
      {[...Array(3)].map((_, i) => <div key={i} className="card h-32 bg-gray-100" />)}
    </div>
  )

  return (
    <div className="space-y-6 max-w-3xl">
      {/* 환영 배너 */}
      <div className="bg-gradient-to-r from-emerald-600 to-teal-500 rounded-2xl p-6 text-white">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
            <User className="w-5 h-5" />
          </div>
          <div>
            <p className="text-sm opacity-80">안녕하세요</p>
            <p className="text-xl font-bold">{userInfo.name}님 👋</p>
          </div>
        </div>
        <p className="text-sm opacity-75 mt-1">
          본인의 PC 보안 상태와 접속 기록을 확인할 수 있습니다.
          보안 이상이 발견되면 원장님께 알려주세요.
        </p>
      </div>

      {/* 권한 안내 */}
      <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm">
        <Lock className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
        <div>
          <p className="font-semibold text-amber-800">직원 계정 안내</p>
          <p className="text-amber-700 text-xs mt-0.5">
            직원 계정은 <strong>본인의 활동 기록과 담당 PC 상태</strong>만 볼 수 있습니다.
            전체 병원 보안 현황, 다른 직원 로그, 컴플라이언스 관리는 원장 계정에서 확인하세요.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 내 PC 보안 상태 */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Monitor className="w-5 h-5 text-emerald-600" />
            <h3 className="font-semibold text-gray-800">내 PC 보안 상태</h3>
          </div>

          {myEp ? (
            <>
              <div className={`flex items-center justify-between p-3 rounded-xl mb-4 ${scoreBg(myEp.security_score)}`}>
                <div>
                  <p className="text-sm text-gray-600">{myEp.hostname}</p>
                  <p className="text-xs text-gray-400">{myEp.location || myEp.ip_address}</p>
                </div>
                <div className="text-right">
                  <p className={`text-3xl font-bold ${scoreColor(myEp.security_score)}`}>
                    {myEp.security_score?.toFixed(0)}
                  </p>
                  <p className="text-xs text-gray-500">보안점수</p>
                </div>
              </div>

              <div className="space-y-2">
                <BoolCheck value={myEp.disk_encrypted} label="💾 디스크 암호화" />
                <BoolCheck value={myEp.antivirus_installed} label="🛡️ 백신 설치" />
                <BoolCheck value={myEp.os_patched} label="📦 OS 최신 패치" />
                <BoolCheck value={myEp.firewall_enabled} label="🔥 방화벽 활성화" />
                <BoolCheck value={myEp.screen_lock_enabled} label="🔒 화면 잠금 설정" />
              </div>

              {myEp.last_seen_at && (
                <p className="text-xs text-gray-400 mt-3 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  마지막 접속: {new Date(myEp.last_seen_at).toLocaleString('ko-KR')}
                </p>
              )}
            </>
          ) : (
            <div className="text-center py-6 text-gray-400">
              <Monitor className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm">등록된 PC가 없습니다</p>
              <p className="text-xs mt-1">원장님께 PC 등록을 요청하세요</p>
            </div>
          )}
        </div>

        {/* 내 활동 요약 */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-5 h-5 text-emerald-600" />
            <h3 className="font-semibold text-gray-800">내 활동 요약 (7일)</h3>
          </div>

          {logSummary ? (
            <div className="space-y-3">
              {/* 직원은 전체 통계가 아닌 본인 로그 수만 */}
              <div className="p-3 bg-blue-50 rounded-xl">
                <p className="text-2xl font-bold text-blue-700">{myLogs.length}</p>
                <p className="text-xs text-blue-600 mt-0.5">내 접속 기록 건수 (최근)</p>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="p-3 bg-green-50 rounded-xl text-center">
                  <p className="text-xl font-bold text-green-700">
                    {myLogs.filter(l => l.result === 'success').length}
                  </p>
                  <p className="text-xs text-green-600">정상 접속</p>
                </div>
                <div className="p-3 bg-red-50 rounded-xl text-center">
                  <p className="text-xl font-bold text-red-700">
                    {myLogs.filter(l => l.result === 'fail').length}
                  </p>
                  <p className="text-xs text-red-600">실패 건수</p>
                </div>
              </div>

              {myLogs.filter(l => l.event_type === 'emr_modify').length > 0 && (
                <div className="flex items-start gap-2 p-2.5 bg-yellow-50 rounded-lg">
                  <AlertTriangle className="w-4 h-4 text-yellow-600 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-yellow-700">
                    최근 기록 수정 {myLogs.filter(l => l.event_type === 'emr_modify').length}건이 있습니다
                  </p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400">로딩 중...</p>
          )}
        </div>
      </div>

      {/* 내 최근 접속 기록 */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-emerald-600" />
            <h3 className="font-semibold text-gray-800">내 최근 접속 기록</h3>
          </div>
          <a href="/my-activity" className="text-sm text-emerald-600 hover:underline">전체 보기</a>
        </div>

        {myLogs.length === 0 ? (
          <div className="text-center py-6 text-gray-400">
            <FileText className="w-8 h-8 mx-auto mb-2 opacity-40" />
            <p className="text-sm">기록된 활동이 없습니다</p>
          </div>
        ) : (
          <div className="space-y-2">
            {myLogs.slice(0, 8).map(log => (
              <div key={log.id} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${SEV_CLASS[log.severity] || SEV_CLASS.info}`}>
                  {log.severity === 'critical' ? '위험' : log.severity === 'warning' ? '경고' : '정상'}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800">
                    {EVENT_LABELS[log.event_type] || log.event_type}
                    {log.resource && <span className="text-gray-400 ml-1 text-xs">({log.resource})</span>}
                  </p>
                  {log.description && (
                    <p className="text-xs text-gray-400 truncate">{log.description}</p>
                  )}
                </div>
                <div className="text-right flex-shrink-0">
                  <p className={`text-xs font-medium ${log.result === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                    {log.result === 'success' ? '성공' : '실패'}
                  </p>
                  <p className="text-xs text-gray-400">
                    {new Date(log.occurred_at).toLocaleString('ko-KR', {
                      month: 'short', day: 'numeric',
                      hour: '2-digit', minute: '2-digit'
                    })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 보안 수칙 안내 */}
      <div className="card bg-gradient-to-br from-gray-50 to-slate-50 border-gray-200">
        <h3 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <Shield className="w-4 h-4" /> 직원 보안 수칙
        </h3>
        <ul className="space-y-2 text-sm text-gray-600">
          {[
            '자리를 비울 때는 반드시 화면 잠금을 설정하세요 (Win+L)',
            '본인 계정을 다른 사람과 공유하지 마세요',
            'USB 메모리는 원장님의 허가 없이 사용하지 마세요',
            '의심스러운 이메일 첨부파일은 열지 마세요',
            '비밀번호는 90일마다 변경하는 것을 권장합니다',
          ].map((tip, i) => (
            <li key={i} className="flex items-start gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
              {tip}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
