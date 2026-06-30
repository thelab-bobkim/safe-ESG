/**
 * MediSafe Clinic - SafeGuard 페이지
 * 규제 컴플라이언스 체크리스트 및 점검 관리
 */
import { useState, useEffect } from 'react'
import { ClipboardCheck, Play, CheckCircle, XCircle, AlertTriangle, Minus, Info, ChevronDown, ChevronUp, Monitor } from 'lucide-react'
import { complianceApi, endpointApi } from '../api/client'

interface Check {
  id: number; title: string; total_score: number; privacy_score: number
  medical_score: number; emr_score: number; pass_count: number; fail_count: number
  partial_count: number; na_count: number; checked_by_name: string | null
  checked_at: string | null; next_check_at: string | null
}

interface CheckResult {
  id: number; item_id: number; item_code: string; item_title: string
  regulation: string; is_mandatory: boolean; status: string
  evidence: string | null; note: string | null; due_date: string | null; guidance: string | null
}

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  pass: { label: '통과', color: 'text-green-600', icon: <CheckCircle className="w-4 h-4" /> },
  fail: { label: '미충족', color: 'text-red-600', icon: <XCircle className="w-4 h-4" /> },
  partial: { label: '부분충족', color: 'text-yellow-600', icon: <AlertTriangle className="w-4 h-4" /> },
  na: { label: '해당없음', color: 'text-gray-400', icon: <Minus className="w-4 h-4" /> },
  pending: { label: '미확인', color: 'text-gray-500', icon: <Info className="w-4 h-4" /> },
}

const REGULATION_LABELS: Record<string, string> = {
  privacy_act_29: '개인정보보호법 제29조',
  medical_act_23: '의료법 제23조',
  emr_cert: 'EMR 인증 기준',
  isms_p: 'ISMS-P',
}

export default function Compliance() {
  const [checks, setChecks] = useState<Check[]>([])
  const [activeCheck, setActiveCheck] = useState<Check | null>(null)
  const [results, setResults] = useState<CheckResult[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set())
  const [editingStatus, setEditingStatus] = useState<Record<number, string>>({})
  const [endpoints, setEndpoints] = useState<{id:number; hostname:string; location:string|null; status:string}[]>([])
  const [selectedEndpointId, setSelectedEndpointId] = useState<number | null>(null)

  const loadChecks = () => {
    setLoading(true)
    complianceApi.listChecks()
      .then(res => {
        setChecks(res.data)
        if (res.data.length > 0 && !activeCheck) {
          loadCheckDetail(res.data[0])
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  const loadCheckDetail = (check: Check) => {
    setActiveCheck(check)
    complianceApi.getCheckDetail(check.id)
      .then(res => {
        const data = res.data
        // 상세 API 응답의 점수로 activeCheck 업데이트 (목록 캐시 덮어쓰기)
        setActiveCheck({
          ...check,
          total_score:   data.total_score   ?? check.total_score,
          privacy_score: data.privacy_score ?? check.privacy_score,
          medical_score: data.medical_score ?? check.medical_score,
          emr_score:     data.emr_score     ?? check.emr_score,
          pass_count:    data.pass_count    ?? check.pass_count,
          fail_count:    data.fail_count    ?? check.fail_count,
          partial_count: data.partial_count ?? check.partial_count,
          na_count:      data.na_count      ?? check.na_count,
          checked_by_name: data.checked_by_name ?? check.checked_by_name,
        })
        setResults(data.results || [])
        const statusMap: Record<number, string> = {}
        data.results?.forEach((r: CheckResult) => { statusMap[r.item_id] = r.status })
        setEditingStatus(statusMap)
      })
      .catch(console.error)
  }

  useEffect(() => {
    loadChecks()
    endpointApi.list().then(res => {
      setEndpoints(res.data)
      if (res.data.length > 0) setSelectedEndpointId(res.data[0].id)
    }).catch(() => {})
  }, [])

  const handleCreateCheck = async () => {
    setCreating(true)
    try {
      const res = await complianceApi.createCheck(selectedEndpointId ?? undefined)
      await loadChecks()
      loadCheckDetail(res.data)
    } catch (err: any) {
      alert(err.response?.data?.detail || '점검 생성 실패')
    } finally {
      setCreating(false)
    }
  }

  const handleSaveResults = async () => {
    if (!activeCheck) return
    const updates = Object.entries(editingStatus).map(([item_id, status]) => ({
      item_id: parseInt(item_id), status
    }))
    try {
      await complianceApi.updateResults(activeCheck.id, updates)
      loadCheckDetail(activeCheck)
      alert('저장 완료!')
    } catch (err: any) {
      alert('저장 실패: ' + (err.response?.data?.detail || err.message))
    }
  }

  const toggleExpand = (id: number) => {
    setExpandedItems(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const groupedResults = results.reduce((acc, r) => {
    const key = r.regulation
    if (!acc[key]) acc[key] = []
    acc[key].push(r)
    return acc
  }, {} as Record<string, CheckResult[]>)

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">규제 점검 (SafeGuard)</h2>
          <p className="text-sm text-gray-500">개인정보보호법·의료법 체크리스트 | 🤖 에이전트 수집 항목은 자동 판정됩니다</p>
        </div>
        <div className="flex items-center gap-2">
          {/* PC 선택 */}
          <div className="flex flex-col">
            <label className="text-xs text-gray-500 mb-0.5 pl-1">점검 대상 PC</label>
            <select
              value={selectedEndpointId ?? ''}
              onChange={e => {
                const val = e.target.value
                setSelectedEndpointId(val ? Number(val) : null)
              }}
              className="border-2 border-blue-400 rounded-lg px-3 py-2 text-sm bg-blue-50 font-semibold min-w-48"
            >
              <option value="">전체 PC 평균</option>
              {endpoints.map(ep => (
                <option key={ep.id} value={ep.id}>
                  {ep.status === 'online' ? '🟢' : '⚫'} {ep.hostname}{ep.location ? ` (${ep.location})` : ''}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col">
            <label className="text-xs text-gray-500 mb-0.5 pl-1">&nbsp;</label>
            <button onClick={handleCreateCheck} disabled={creating} className="btn-primary flex items-center gap-2">
              <Play className="w-4 h-4" />
              {creating ? '생성 중...' : '새 점검 시작'}
            </button>
          </div>
        </div>
      </div>

      {/* 점검 이력 선택 */}
      {checks.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {checks.slice(0, 5).map(check => (
            <button
              key={check.id}
              onClick={() => loadCheckDetail(check)}
              className={`flex-shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeCheck?.id === check.id ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 border border-gray-200 hover:border-blue-300'
              }`}
            >
              <div>{new Date(check.checked_at!).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })} ({check.total_score.toFixed(0)}점)</div>
              {check.checked_by_name && (
                <div className="text-xs opacity-70 truncate max-w-32">{check.checked_by_name}</div>
              )}
            </button>
          ))}
        </div>
      )}

      {activeCheck ? (
        <>
          {/* 점수 카드 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <ScoreCard label="종합 점수" score={activeCheck.total_score} large />
            <ScoreCard label="개인정보보호법 제29조" score={activeCheck.privacy_score} />
            <ScoreCard label="의료법 제23조" score={activeCheck.medical_score} />
            <ScoreCard label="EMR 인증 기준" score={activeCheck.emr_score} />
          </div>

          {/* 결과 요약 */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-800">항목별 결과</h3>
              <div className="flex gap-4 text-sm">
                <span className="text-green-600 font-medium">✓ 통과 {activeCheck.pass_count}</span>
                <span className="text-red-600 font-medium">✗ 미충족 {activeCheck.fail_count}</span>
                <span className="text-yellow-600 font-medium">△ 부분 {activeCheck.partial_count}</span>
                <span className="text-gray-400">— 해당없음 {activeCheck.na_count}</span>
              </div>
            </div>

            {/* 규제별 그룹 */}
            <div className="space-y-4">
              {Object.entries(groupedResults).map(([reg, items]) => (
                <div key={reg}>
                  <h4 className="text-sm font-semibold text-gray-700 mb-2 px-2 py-1 bg-gray-50 rounded-lg">
                    {REGULATION_LABELS[reg] || reg}
                  </h4>
                  <div className="space-y-2">
                    {items.map(item => {
                      const currentStatus = editingStatus[item.item_id] || item.status
                      const cfg = STATUS_CONFIG[currentStatus] || STATUS_CONFIG.pending
                      const isExpanded = expandedItems.has(item.item_id)

                      return (
                        <div key={item.id} className={`border rounded-lg overflow-hidden ${
                          currentStatus === 'fail' ? 'border-red-200 bg-red-50/30' :
                          currentStatus === 'pass' ? 'border-green-200' : 'border-gray-200'
                        }`}>
                          <div
                            className="flex items-center gap-3 p-3 cursor-pointer"
                            onClick={() => toggleExpand(item.item_id)}
                          >
                            <span className={cfg.color}>{cfg.icon}</span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-mono text-gray-400">{item.item_code}</span>
                                {item.is_mandatory && (
                                  <span className="badge-fail text-xs">필수</span>
                                )}
                              </div>
                              <p className="text-sm font-medium text-gray-800 truncate">{item.item_title}</p>
                            </div>

                            {/* 상태 변경 셀렉트 */}
                            <select
                              value={currentStatus}
                              onChange={e => {
                                e.stopPropagation()
                                setEditingStatus(prev => ({...prev, [item.item_id]: e.target.value}))
                              }}
                              onClick={e => e.stopPropagation()}
                              className="text-xs border border-gray-300 rounded-lg px-2 py-1.5 bg-white"
                            >
                              {Object.entries(STATUS_CONFIG).map(([k, v]) => (
                                <option key={k} value={k}>{v.label}</option>
                              ))}
                            </select>

                            {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                          </div>

                          {isExpanded && (
                            <div className="px-4 pb-4 space-y-3 border-t border-gray-100 bg-white">
                              {/* 자동 수집 배지 */}
                              {item.evidence && (item.evidence.includes('에이전트 자동') || item.evidence.includes('MediSafe') || item.evidence.includes('SafeLog')) && (
                                <div className="flex items-start gap-2 p-2 bg-purple-50 rounded-lg text-xs text-purple-700">
                                  <span className="text-base leading-none">🤖</span>
                                  <span><span className="font-semibold">자동 판정: </span>{item.evidence}</span>
                                </div>
                              )}
                              {/* 상세 가이드 */}
                              {item.guidance && (
                                <div className="rounded-lg border border-blue-100 overflow-hidden">
                                  <div className="px-3 py-2 bg-blue-600 text-white text-xs font-semibold flex items-center gap-1">
                                    <span>📋</span>
                                    <span>
                                      {currentStatus === 'fail' ? '❌ 미충족 — 조치 방법' :
                                       currentStatus === 'partial' ? '⚠️ 부분충족 — 개선 방법' :
                                       currentStatus === 'pass' ? '✅ 통과 기준 및 증빙' :
                                       '💡 이행 가이드'}
                                    </span>
                                  </div>
                                  <div className="px-3 py-3 bg-blue-50 text-xs text-gray-700 whitespace-pre-line leading-relaxed">
                                    {item.guidance}
                                  </div>
                                </div>
                              )}
                              {/* 직접 입력 증빙 */}
                              {item.evidence && !item.evidence.includes('에이전트') && !item.evidence.includes('MediSafe') && !item.evidence.includes('SafeLog') && (
                                <div className="flex items-start gap-2 p-2 bg-green-50 rounded text-xs text-green-700">
                                  <span>📎</span>
                                  <span><span className="font-semibold">증빙: </span>{item.evidence}</span>
                                </div>
                              )}
                              {item.note && (
                                <div className="flex items-start gap-2 p-2 bg-gray-50 rounded text-xs text-gray-600">
                                  <span>📝</span>
                                  <span><span className="font-semibold">메모: </span>{item.note}</span>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-4 flex justify-end">
              <button onClick={handleSaveResults} className="btn-primary flex items-center gap-2">
                <CheckCircle className="w-4 h-4" /> 결과 저장
              </button>
            </div>
          </div>
        </>
      ) : (
        <div className="card text-center py-12">
          <ClipboardCheck className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 font-medium">아직 점검 기록이 없습니다</p>
          <p className="text-sm text-gray-400 mt-1 mb-4">새 점검을 시작하여 규제 준수 상태를 확인하세요</p>
          <button onClick={handleCreateCheck} disabled={creating} className="btn-primary inline-flex items-center gap-2">
            <Play className="w-4 h-4" />
            {creating ? '생성 중...' : '지금 점검 시작'}
          </button>
        </div>
      )}
    </div>
  )
}

function ScoreCard({ label, score, large }: { label: string; score: number; large?: boolean }) {
  const color = score >= 80 ? 'text-green-600' : score >= 60 ? 'text-yellow-600' : 'text-red-600'
  const bg = score >= 80 ? 'bg-green-50' : score >= 60 ? 'bg-yellow-50' : 'bg-red-50'
  return (
    <div className={`card text-center ${bg}`}>
      <p className={`${large ? 'text-4xl' : 'text-3xl'} font-bold ${color}`}>
        {score.toFixed(0)}
      </p>
      <p className="text-xs text-gray-600 mt-1">{label}</p>
    </div>
  )
}
