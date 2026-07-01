/**
 * MediSafe Clinic - 원장(Admin) 전용 대시보드
 * 병원 전체 보안 점수, 모든 엔드포인트, 전체 로그, 컴플라이언스 현황을 표시합니다.
 * staff 계정은 이 화면에 접근할 수 없습니다.
 */
import { useState, useEffect } from 'react'
import { Shield, Monitor, FileText, ClipboardCheck, AlertTriangle, CheckCircle, XCircle, Clock, TrendingUp, Star } from 'lucide-react'
import { dashboardApi, apiClient } from '../api/client'
import { RadialBarChart, RadialBar, ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts'

interface DashboardData {
  tenant_name: string
  plan: string
  score: {
    total: number
    grade: string
    breakdown: {
      endpoint: { score: number; count: number; online: number }
      compliance: { score: number; last_checked: string | null }
      log: { score: number; critical_events_7d: number }
    }
  }
  endpoints: {
    total: number; online: number; warning: number; critical: number; offline: number; avg_score: number
    issues: Array<{ hostname: string; issue: string; score: number }>
  }
  logs: {
    total_24h: number; critical_24h: number; warning_24h: number; failed_attempts_24h: number
    recent_events: Array<{
      id: number; event_type: string; severity: string; user_name: string
      description: string | null; result: string; occurred_at: string
    }>
  }
  compliance: {
    total_score: number; privacy_score: number; medical_score: number; emr_score: number
    fail_count: number; last_checked_at: string | null; next_check_at: string | null
  }
}

const GRADE_COLORS: Record<string, string> = {
  A: 'text-green-600', B: 'text-blue-600', C: 'text-yellow-600', D: 'text-orange-600', F: 'text-red-600'
}

const SEVERITY_BADGE: Record<string, string> = {
  info: 'badge-info', warning: 'badge-warning', critical: 'badge-fail'
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  emr_access: 'EMR 접속', emr_query: '기록 조회', emr_modify: '기록 수정',
  login_success: '로그인 성공', login_fail: '로그인 실패',
  policy_change: '정책 변경', admin_action: '관리자 행위', security_alert: '보안 경고',
}

interface SecurityGrade {
  grade: number
  grade_name: string
  grade_color: string
  total_score: number
  next_grade: number
  next_grade_threshold: number
  score_to_next: number
  actions: Array<{ priority: string; action: string; targets: string[]; score_impact: string }>
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [gradeData, setGradeData] = useState<SecurityGrade | null>(null)
  const [showGradeModal, setShowGradeModal] = useState(false)

  useEffect(() => {
    dashboardApi.getSummary()
      .then(res => setData(res.data))
      .catch(console.error)
      .finally(() => setLoading(false))
    // 보안 등급 로드 (F12)
    apiClient.get('/compliance/security-grade')
      .then(res => setGradeData(res.data))
      .catch(() => {})
  }, [])

  if (loading) return <LoadingState />
  if (!data) return <div className="text-red-500">데이터를 불러오지 못했습니다.</div>

  const { score, endpoints, logs, compliance } = data
  const scoreColor = score.total >= 80 ? '#10b981' : score.total >= 60 ? '#f59e0b' : '#ef4444'

  return (
    <div className="space-y-6">
      {/* 상단: 종합 점수 + 빠른 지표 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* 종합 보안 점수 카드 */}
        <div className="md:col-span-1 card flex flex-col items-center justify-center text-center">
          <p className="text-sm text-gray-500 mb-2 font-medium">종합 보안 점수</p>
          <div className="relative w-32 h-32">
            <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
              <circle cx="60" cy="60" r="50" fill="none" stroke="#f3f4f6" strokeWidth="12" />
              <circle
                cx="60" cy="60" r="50" fill="none"
                stroke={scoreColor} strokeWidth="12"
                strokeDasharray={`${(score.total / 100) * 314} 314`}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold text-gray-900">{score.total}</span>
              <span className={`text-lg font-bold ${GRADE_COLORS[score.grade] || 'text-gray-600'}`}>
                {score.grade}등급
              </span>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-2">{data.tenant_name}</p>
        </div>

        {/* 빠른 지표 3개 */}
        <div className="md:col-span-3 grid grid-cols-3 gap-4">
          <MetricCard
            icon={<Monitor className="w-5 h-5" />}
            label="SafeEndpoint"
            value={`${endpoints.avg_score.toFixed(0)}점`}
            sub={`${endpoints.online}/${endpoints.total}대 온라인`}
            color="blue"
            alert={endpoints.warning + endpoints.critical > 0
              ? `${endpoints.warning + endpoints.critical}대 주의`
              : undefined
            }
          />
          <MetricCard
            icon={<FileText className="w-5 h-5" />}
            label="SafeLog (24h)"
            value={`${logs.total_24h}건`}
            sub={`위험 ${logs.critical_24h}건 · 경고 ${logs.warning_24h}건`}
            color={logs.critical_24h > 0 ? "red" : "green"}
            alert={logs.failed_attempts_24h > 0
              ? `로그인 실패 ${logs.failed_attempts_24h}회`
              : undefined
            }
          />
          <MetricCard
            icon={<ClipboardCheck className="w-5 h-5" />}
            label="SafeGuard"
            value={`${compliance.total_score.toFixed(0)}점`}
            sub={`미조치 ${compliance.fail_count}건`}
            color={compliance.total_score >= 70 ? "green" : "yellow"}
            alert={compliance.fail_count > 0
              ? `${compliance.fail_count}건 조치 필요`
              : undefined
            }
          />
        </div>
      </div>

      {/* 모듈별 점수 바 */}
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">모듈별 점수 현황</h3>
        <div className="space-y-4">
          <ScoreBar label="SafeEndpoint — 엔드포인트 보안" score={score.breakdown.endpoint.score} weight="50%" />
          <ScoreBar label="SafeGuard — 컴플라이언스" score={score.breakdown.compliance.score} weight="35%" />
          <ScoreBar label="SafeLog — 로그 품질" score={score.breakdown.log.score} weight="15%" />
        </div>
      </div>

      {/* 하단: 엔드포인트 이슈 + 최근 이벤트 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 엔드포인트 이슈 */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-800">엔드포인트 현황</h3>
            <a href="/endpoints" className="text-sm text-blue-600 hover:underline">전체 보기</a>
          </div>
          <div className="grid grid-cols-4 gap-2 mb-4">
            <StatusBadge count={endpoints.online} label="온라인" color="green" />
            <StatusBadge count={endpoints.warning} label="경고" color="yellow" />
            <StatusBadge count={endpoints.critical} label="위험" color="red" />
            <StatusBadge count={endpoints.offline} label="오프라인" color="gray" />
          </div>
          {endpoints.issues.length > 0 ? (
            <div className="space-y-2">
              {endpoints.issues.map((issue, i) => (
                <div key={i} className="flex items-start gap-2 p-2 bg-yellow-50 rounded-lg">
                  <AlertTriangle className="w-4 h-4 text-yellow-500 mt-0.5 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-800">{issue.hostname}</p>
                    <p className="text-xs text-gray-500 truncate">{issue.issue}</p>
                  </div>
                  <span className="ml-auto text-xs font-bold text-red-600">{issue.score}점</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-green-600 text-sm">
              <CheckCircle className="w-4 h-4" />
              모든 엔드포인트가 정상입니다
            </div>
          )}
        </div>

        {/* 최근 보안 이벤트 */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-800">최근 보안 이벤트</h3>
            <a href="/logs" className="text-sm text-blue-600 hover:underline">전체 보기</a>
          </div>
          <div className="space-y-2">
            {logs.recent_events.slice(0, 6).map((event) => (
              <div key={event.id} className="flex items-start gap-3 py-2 border-b border-gray-50 last:border-0">
                <span className={`${SEVERITY_BADGE[event.severity] || 'badge-info'} mt-0.5 flex-shrink-0`}>
                  {event.severity === 'critical' ? '위험' : event.severity === 'warning' ? '경고' : '정상'}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-gray-800 truncate">
                    {EVENT_TYPE_LABELS[event.event_type] || event.event_type}
                    {event.user_name && event.user_name !== '알수없음' && ` — ${event.user_name}`}
                  </p>
                  {event.description && (
                    <p className="text-xs text-gray-400 truncate">{event.description}</p>
                  )}
                </div>
                <span className="text-xs text-gray-400 flex-shrink-0">
                  {new Date(event.occurred_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 컴플라이언스 점수 상세 */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-800">규제 컴플라이언스 현황</h3>
          <a href="/compliance" className="text-sm text-blue-600 hover:underline">점검 시작</a>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <ComplianceScore label="개인정보보호법 제29조" score={compliance.privacy_score} />
          <ComplianceScore label="의료법 제23조" score={compliance.medical_score} />
          <ComplianceScore label="EMR 인증 기준" score={compliance.emr_score} />
        </div>
        {compliance.last_checked_at && (
          <p className="text-xs text-gray-400 mt-3 flex items-center gap-1">
            <Clock className="w-3 h-3" />
            마지막 점검: {new Date(compliance.last_checked_at).toLocaleDateString('ko-KR')}
            {compliance.next_check_at && ` · 다음 점검: ${new Date(compliance.next_check_at).toLocaleDateString('ko-KR')}`}
          </p>
        )}
      </div>

      {/* 보안 등급 뱃지 (F12) */}
      {gradeData && (
        <div
          className="card cursor-pointer hover:shadow-md transition-shadow"
          onClick={() => setShowGradeModal(true)}
        >
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-gray-800 mb-1">의료기관 정보보호 등급</h3>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold" style={{ color: gradeData.grade_color }}>
                  {gradeData.grade_name}
                </span>
                <div className="flex gap-0.5">
                  {[1,2,3,4,5].map(i => (
                    <Star
                      key={i}
                      className="w-5 h-5"
                      fill={i <= gradeData.grade ? gradeData.grade_color : '#e5e7eb'}
                      color={i <= gradeData.grade ? gradeData.grade_color : '#e5e7eb'}
                    />
                  ))}
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                종합점수 {gradeData.total_score}점
                {gradeData.score_to_next > 0 && ` · ${gradeData.next_grade}등급까지 +${gradeData.score_to_next}점`}
              </p>
            </div>
            <div className="text-sm text-blue-600">
              등급 향상 로드맵 →
            </div>
          </div>
        </div>
      )}

      {/* 보안 등급 로드맵 모달 (F12) */}
      {showGradeModal && gradeData && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setShowGradeModal(false)}>
          <div className="bg-white rounded-2xl p-6 max-w-lg w-full shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-gray-900">등급 향상 로드맵</h3>
              <button onClick={() => setShowGradeModal(false)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <div className="flex items-center gap-3 mb-4 p-3 rounded-xl" style={{ backgroundColor: gradeData.grade_color + '15' }}>
              <div className="flex gap-0.5">
                {[1,2,3,4,5].map(i => (
                  <Star key={i} className="w-5 h-5" fill={i <= gradeData.grade ? gradeData.grade_color : '#e5e7eb'} color={i <= gradeData.grade ? gradeData.grade_color : '#e5e7eb'} />
                ))}
              </div>
              <div>
                <p className="font-bold" style={{ color: gradeData.grade_color }}>{gradeData.grade_name}</p>
                <p className="text-sm text-gray-500">종합점수 {gradeData.total_score}점</p>
              </div>
            </div>
            {gradeData.actions.length > 0 ? (
              <div className="space-y-3">
                <p className="text-sm font-semibold text-gray-700">조치 필요 항목:</p>
                {gradeData.actions.map((action, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-gray-50 rounded-xl">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-bold flex-shrink-0 ${
                      action.priority === '높음' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
                    }`}>
                      {action.priority}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800">{action.action}</p>
                      {action.targets.length > 0 && (
                        <p className="text-xs text-gray-500 mt-0.5 truncate">
                          대상: {action.targets.join(', ')}
                        </p>
                      )}
                    </div>
                    <span className="text-xs font-bold text-green-600 flex-shrink-0">{action.score_impact}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center gap-2 text-green-600">
                <CheckCircle className="w-5 h-5" />
                <p className="text-sm font-medium">모든 보안 항목이 충족되었습니다!</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── 서브 컴포넌트들 ──────────────────────────────────────

function MetricCard({ icon, label, value, sub, color, alert }: {
  icon: React.ReactNode; label: string; value: string; sub: string
  color: string; alert?: string
}) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600', green: 'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600', red: 'bg-red-50 text-red-600',
  }
  return (
    <div className="card">
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center mb-3 ${colors[color]}`}>{icon}</div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
      <p className="text-xs text-gray-400 mt-1">{sub}</p>
      {alert && (
        <div className="mt-2 flex items-center gap-1 text-xs text-orange-600">
          <AlertTriangle className="w-3 h-3" />{alert}
        </div>
      )}
    </div>
  )
}

function ScoreBar({ label, score, weight }: { label: string; score: number; weight: string }) {
  const color = score >= 80 ? 'bg-green-500' : score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-700">{label}</span>
        <span className="font-medium text-gray-900">{score.toFixed(0)}점 <span className="text-gray-400 font-normal">(가중치 {weight})</span></span>
      </div>
      <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}

function StatusBadge({ count, label, color }: { count: number; label: string; color: string }) {
  const colors: Record<string, string> = {
    green: 'bg-green-50 text-green-700', yellow: 'bg-yellow-50 text-yellow-700',
    red: 'bg-red-50 text-red-700', gray: 'bg-gray-50 text-gray-500',
  }
  return (
    <div className={`text-center p-2 rounded-lg ${colors[color]}`}>
      <p className="text-xl font-bold">{count}</p>
      <p className="text-xs mt-0.5">{label}</p>
    </div>
  )
}

function ComplianceScore({ label, score }: { label: string; score: number }) {
  const color = score >= 80 ? 'text-green-600' : score >= 60 ? 'text-yellow-600' : 'text-red-600'
  const bg = score >= 80 ? 'bg-green-50' : score >= 60 ? 'bg-yellow-50' : 'bg-red-50'
  return (
    <div className={`p-4 rounded-xl ${bg} text-center`}>
      <p className={`text-3xl font-bold ${color}`}>{score.toFixed(0)}</p>
      <p className="text-xs text-gray-600 mt-1">{label}</p>
    </div>
  )
}

function LoadingState() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="card h-40 bg-gray-100" />
        ))}
      </div>
      <div className="card h-32 bg-gray-100" />
      <div className="grid grid-cols-2 gap-4">
        <div className="card h-48 bg-gray-100" />
        <div className="card h-48 bg-gray-100" />
      </div>
    </div>
  )
}
