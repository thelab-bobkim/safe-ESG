/**
 * MediSafe Clinic - 직원 전용: 내 활동 기록 전체 보기
 * 본인 이메일로 필터링된 로그만 표시합니다.
 */
import { useState, useEffect } from 'react'
import { FileText, Download, Search, Info, Lock } from 'lucide-react'
import { logApi } from '../api/client'

interface Log {
  id: number
  event_type: string
  severity: string
  resource: string | null
  action: string | null
  result: string
  description: string | null
  occurred_at: string
  ip_address: string | null
  endpoint_hostname: string | null
}

const EVENT_LABELS: Record<string, string> = {
  emr_access: 'EMR 접속', emr_query: '기록 조회', emr_modify: '기록 수정',
  emr_delete: '기록 삭제', login_success: '로그인 성공', login_fail: '로그인 실패',
  file_access: '파일 접근', admin_action: '관리 행위', system_event: '시스템 이벤트',
}

const SEV_CONFIG: Record<string, { label: string; cls: string }> = {
  info: { label: '정상', cls: 'bg-blue-50 text-blue-700' },
  warning: { label: '경고', cls: 'bg-yellow-50 text-yellow-700' },
  critical: { label: '위험', cls: 'bg-red-50 text-red-700' },
}

export default function MyActivity() {
  const [logs, setLogs] = useState<Log[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')

  const userInfo = JSON.parse(localStorage.getItem('user_info') || '{}')

  const load = (p = page, kw = keyword) => {
    setLoading(true)
    logApi.list({
      user_email: userInfo.email,  // 반드시 본인 이메일로 필터
      keyword: kw || undefined,
      page: p,
      page_size: 30,
    }).then(res => {
      setLogs(res.data.items || [])
      setTotal(res.data.total || 0)
    }).catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page])

  const handleSearch = () => { setPage(1); load(1, keyword) }

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">내 활동 기록</h2>
          <p className="text-sm text-gray-400">{userInfo.email}의 접속 및 활동 이력</p>
        </div>
        <button
          onClick={() => logApi.exportCsv()}
          className="flex items-center gap-2 px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-600"
        >
          <Download className="w-4 h-4" /> 내 기록 내보내기
        </button>
      </div>

      {/* 내 기록만 본다는 안내 */}
      <div className="flex items-start gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-sm">
        <Lock className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
        <p className="text-emerald-700">
          <strong>본인 기록만 표시됩니다.</strong> 다른 직원의 활동 기록은 원장 계정에서만 확인 가능합니다.
        </p>
      </div>

      {/* 검색 */}
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="키워드 검색 (예: 환자ID, 파일명...)"
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
        />
        <button onClick={handleSearch} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm hover:bg-emerald-700 flex items-center gap-1">
          <Search className="w-4 h-4" /> 검색
        </button>
      </div>

      {/* 로그 목록 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b text-sm text-gray-500">
          총 <span className="font-semibold text-gray-800">{total}</span>건의 내 활동 기록
        </div>
        <div className="divide-y divide-gray-50">
          {loading ? (
            <div className="text-center py-8 text-gray-400">로딩 중...</div>
          ) : logs.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">활동 기록이 없습니다</p>
            </div>
          ) : (
            logs.map(log => {
              const sev = SEV_CONFIG[log.severity] || SEV_CONFIG.info
              return (
                <div key={log.id} className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 mt-0.5 ${sev.cls}`}>
                    {sev.label}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800">
                      {EVENT_LABELS[log.event_type] || log.event_type}
                      {log.resource && (
                        <span className="text-xs text-gray-400 font-normal ml-2">({log.resource})</span>
                      )}
                    </p>
                    {log.description && <p className="text-xs text-gray-400 mt-0.5">{log.description}</p>}
                    {log.endpoint_hostname && (
                      <p className="text-xs text-gray-400">PC: {log.endpoint_hostname} · IP: {log.ip_address}</p>
                    )}
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className={`text-xs font-semibold ${log.result === 'success' ? 'text-green-600' : 'text-red-500'}`}>
                      {log.result === 'success' ? '✓ 성공' : '✗ 실패'}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {new Date(log.occurred_at).toLocaleString('ko-KR', {
                        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                      })}
                    </p>
                  </div>
                </div>
              )
            })
          )}
        </div>
        {total > 30 && (
          <div className="px-4 py-3 border-t bg-gray-50 flex items-center justify-between text-sm text-gray-500">
            <span>페이지 {page} / {Math.ceil(total / 30)}</span>
            <div className="flex gap-2">
              <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
                className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-white">이전</button>
              <button disabled={page >= Math.ceil(total / 30)} onClick={() => setPage(p => p + 1)}
                className="px-3 py-1 border rounded disabled:opacity-40 hover:bg-white">다음</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
