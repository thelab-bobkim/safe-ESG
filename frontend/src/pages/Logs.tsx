/**
 * MediSafe Clinic - SafeLog 페이지
 * 접속 로그 조회, 필터링, CSV 내보내기
 */
import { useState, useEffect } from 'react'
import { Search, Download, Filter, RefreshCw, AlertTriangle, CheckCircle, Info } from 'lucide-react'
import { logApi } from '../api/client'

interface Log {
  id: number; event_type: string; severity: string; user_name: string | null
  user_email: string | null; ip_address: string | null; endpoint_hostname: string | null
  resource: string | null; action: string | null; result: string
  description: string | null; occurred_at: string; is_worm: boolean
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  emr_access: 'EMR 접속', emr_query: '기록 조회', emr_modify: '기록 수정', emr_delete: '기록 삭제',
  login_success: '로그인 성공', login_fail: '로그인 실패', file_access: '파일 접근',
  policy_change: '정책 변경', admin_action: '관리자 행위', system_event: '시스템 이벤트',
  security_alert: '보안 경고',
}

const SEVERITY_CONFIG: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
  info: { label: '정상', className: 'badge-info', icon: <Info className="w-3 h-3" /> },
  warning: { label: '경고', className: 'badge-warning', icon: <AlertTriangle className="w-3 h-3" /> },
  critical: { label: '위험', className: 'badge-fail', icon: <AlertTriangle className="w-3 h-3" /> },
}

export default function Logs() {
  const [logs, setLogs] = useState<Log[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState<any>(null)

  // 필터 상태
  const [filters, setFilters] = useState({
    event_type: '', severity: '', start_date: '', end_date: '', keyword: ''
  })

  const load = (p = page) => {
    setLoading(true)
    const params: any = { page: p, page_size: 20 }
    if (filters.event_type) params.event_type = filters.event_type
    if (filters.severity) params.severity = filters.severity
    if (filters.start_date) params.start_date = filters.start_date
    if (filters.end_date) params.end_date = filters.end_date
    if (filters.keyword) params.keyword = filters.keyword

    logApi.list(params)
      .then(res => {
        setLogs(res.data.items)
        setTotal(res.data.total)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    logApi.getSummary().then(res => setSummary(res.data)).catch(() => {})
  }, [])

  useEffect(() => { load() }, [page])

  const handleSearch = () => { setPage(1); load(1) }

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">접속 기록 (SafeLog)</h2>
          <p className="text-sm text-gray-500">모든 기록은 WORM 방식으로 안전하게 보존됩니다</p>
        </div>
        <button
          onClick={() => logApi.exportCsv(filters.start_date, filters.end_date)}
          className="btn-secondary flex items-center gap-2"
        >
          <Download className="w-4 h-4" /> CSV 내보내기
        </button>
      </div>

      {/* 요약 통계 */}
      {summary && (
        <div className="grid grid-cols-4 gap-3">
          <SummaryCard label="총 이벤트" value={summary.total_events} sub="최근 7일" color="blue" />
          <SummaryCard label="위험 이벤트" value={summary.critical_events} sub="즉각 확인 필요" color="red" />
          <SummaryCard label="경고 이벤트" value={summary.warning_events} sub="모니터링 필요" color="yellow" />
          <SummaryCard label="로그인 실패" value={summary.failed_attempts} sub="무단 접근 의심" color={summary.failed_attempts > 3 ? "red" : "gray"} />
        </div>
      )}

      {/* 필터 */}
      <div className="card">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <select
            value={filters.event_type}
            onChange={e => setFilters({...filters, event_type: e.target.value})}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="">전체 이벤트</option>
            {Object.entries(EVENT_TYPE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>

          <select
            value={filters.severity}
            onChange={e => setFilters({...filters, severity: e.target.value})}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="">전체 심각도</option>
            <option value="info">정상</option>
            <option value="warning">경고</option>
            <option value="critical">위험</option>
          </select>

          <input
            type="date" value={filters.start_date}
            onChange={e => setFilters({...filters, start_date: e.target.value})}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
          <input
            type="date" value={filters.end_date}
            onChange={e => setFilters({...filters, end_date: e.target.value})}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />

          <div className="flex gap-2">
            <input
              type="text" placeholder="키워드 검색" value={filters.keyword}
              onChange={e => setFilters({...filters, keyword: e.target.value})}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
            <button onClick={handleSearch} className="btn-primary px-3">
              <Search className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* 로그 테이블 */}
      <div className="card p-0 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between bg-gray-50">
          <span className="text-sm text-gray-600">총 <span className="font-semibold text-gray-900">{total.toLocaleString()}</span>건</span>
          <button onClick={() => load()} className="text-gray-400 hover:text-gray-600">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {['심각도', '이벤트', '사용자', 'IP / PC', '대상', '결과', '시각'].map(h => (
                  <th key={h} className="text-left text-xs font-medium text-gray-500 px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                <tr><td colSpan={7} className="text-center py-8 text-gray-400">로딩 중...</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-8 text-gray-400">로그가 없습니다</td></tr>
              ) : (
                logs.map(log => {
                  const sev = SEVERITY_CONFIG[log.severity] || SEVERITY_CONFIG.info
                  return (
                    <tr key={log.id} className={`hover:bg-gray-50 ${log.severity === 'critical' ? 'bg-red-50/30' : ''}`}>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${sev.className}`}>
                          {sev.icon}{sev.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-medium text-gray-800">
                          {EVENT_TYPE_LABELS[log.event_type] || log.event_type}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-gray-800">{log.user_name || '-'}</p>
                        <p className="text-xs text-gray-400">{log.user_email || ''}</p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-gray-600">{log.ip_address || '-'}</p>
                        <p className="text-xs text-gray-400">{log.endpoint_hostname || ''}</p>
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs max-w-32 truncate">
                        {log.resource || log.description || '-'}
                      </td>
                      <td className="px-4 py-3">
                        {log.result === 'success'
                          ? <span className="badge-pass">성공</span>
                          : <span className="badge-fail">실패</span>
                        }
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-400">
                        {new Date(log.occurred_at).toLocaleString('ko-KR', {
                          month: 'short', day: 'numeric',
                          hour: '2-digit', minute: '2-digit'
                        })}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* 페이지네이션 */}
        {total > 20 && (
          <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between">
            <span className="text-sm text-gray-500">페이지 {page} / {Math.ceil(total / 20)}</span>
            <div className="flex gap-2">
              <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
                className="btn-secondary text-sm py-1 px-3 disabled:opacity-40">이전</button>
              <button disabled={page >= Math.ceil(total / 20)} onClick={() => setPage(p => p + 1)}
                className="btn-secondary text-sm py-1 px-3 disabled:opacity-40">다음</button>
            </div>
          </div>
        )}
      </div>

      {/* WORM 안내 */}
      <div className="flex items-start gap-3 p-4 bg-blue-50 rounded-xl text-sm">
        <Info className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
        <div>
          <p className="font-medium text-blue-800">WORM 보존 방식 적용</p>
          <p className="text-blue-600 text-xs mt-0.5">
            모든 로그는 Write-Once-Read-Many 방식으로 보존됩니다.
            삭제 또는 수정이 불가능하여 규제 감사 시 증빙 자료로 활용 가능합니다.
          </p>
        </div>
      </div>
    </div>
  )
}

function SummaryCard({ label, value, sub, color }: { label: string; value: number; sub: string; color: string }) {
  const colors: Record<string, string> = {
    blue: 'text-blue-600 bg-blue-50', red: 'text-red-600 bg-red-50',
    yellow: 'text-yellow-600 bg-yellow-50', gray: 'text-gray-600 bg-gray-50',
  }
  return (
    <div className={`card p-4 ${colors[color]?.split(' ')[1] || 'bg-gray-50'}`}>
      <p className={`text-2xl font-bold ${colors[color]?.split(' ')[0] || 'text-gray-600'}`}>{value}</p>
      <p className="text-sm font-medium text-gray-700 mt-1">{label}</p>
      <p className="text-xs text-gray-400">{sub}</p>
    </div>
  )
}
