/**
 * MediSafe Clinic - 개인정보 영향평가(PIA) 보조 (F11)
 */
import { useState, useEffect } from 'react'
import { FileSearch, Download, CheckCircle, AlertCircle, HelpCircle, ChevronDown, ChevronUp } from 'lucide-react'
import apiClient from '../api/client'

interface ChecklistItem {
  id: number
  category: string
  item: string
  weight: number
  auto_status: string | null
  guidance: string
}

interface ChecklistData {
  checklist: ChecklistItem[]
  endpoint_count: number
}

const STATUS_OPTIONS = [
  { value: 'applied', label: '적용', color: 'text-green-700 bg-green-50 border-green-200' },
  { value: 'partial', label: '부분적용', color: 'text-yellow-700 bg-yellow-50 border-yellow-200' },
  { value: 'not_applied', label: '미적용', color: 'text-red-700 bg-red-50 border-red-200' },
  { value: 'na', label: '해당없음', color: 'text-gray-500 bg-gray-50 border-gray-200' },
]

export default function PIA() {
  const [checklist, setChecklist] = useState<ChecklistData | null>(null)
  const [responses, setResponses] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  useEffect(() => {
    loadChecklist()
  }, [])

  const loadChecklist = async () => {
    try {
      const res = await apiClient.get('/compliance/pia-checklist')
      setChecklist(res.data)
      // 자동 감지된 상태 초기화
      const init: Record<number, string> = {}
      res.data.checklist.forEach((item: ChecklistItem) => {
        if (item.auto_status) {
          init[item.id] = item.auto_status.includes('N/A') || !item.auto_status ? 'not_applied' : 'applied'
        }
      })
      setResponses(init)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadReport = async () => {
    setGenerating(true)
    try {
      const res = await apiClient.post('/compliance/pia-report', { responses })
      const text = res.data.report_text
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `PIA_보고서_초안_${new Date().toISOString().slice(0, 10)}.txt`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err: any) {
      alert('보고서 생성 오류: ' + (err.response?.data?.detail || ''))
    } finally {
      setGenerating(false)
    }
  }

  const completedCount = Object.keys(responses).length
  const totalCount = checklist?.checklist.length || 0
  const progress = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  const appliedCount = Object.values(responses).filter(v => v === 'applied').length
  const partialCount = Object.values(responses).filter(v => v === 'partial').length

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">개인정보 영향평가(PIA) 보조</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            「개인정보 보호법」 제33조 기반 영향평가 체크리스트
          </p>
        </div>
        <button
          onClick={handleDownloadReport}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 disabled:opacity-50"
        >
          <Download className="w-4 h-4" />
          {generating ? '생성 중...' : '보고서 초안 다운로드'}
        </button>
      </div>

      {/* 진행 상황 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">평가 진행률</span>
          <span className="text-sm font-bold text-blue-600">{progress}%</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex gap-4 mt-3 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <CheckCircle className="w-3.5 h-3.5 text-green-500" />
            적용 {appliedCount}개
          </span>
          <span className="flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5 text-yellow-500" />
            부분적용 {partialCount}개
          </span>
          <span className="flex items-center gap-1">
            <HelpCircle className="w-3.5 h-3.5 text-gray-400" />
            미응답 {totalCount - completedCount}개
          </span>
        </div>
      </div>

      {/* 체크리스트 */}
      <div className="space-y-3">
        {checklist?.checklist.map(item => {
          const isExpanded = expandedId === item.id
          const currentStatus = responses[item.id]

          return (
            <div
              key={item.id}
              className={`bg-white rounded-xl border transition-all ${
                currentStatus === 'applied' ? 'border-green-200'
                : currentStatus === 'not_applied' ? 'border-red-200'
                : 'border-gray-200'
              }`}
            >
              {/* 항목 헤더 */}
              <div className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full font-medium">
                        {item.category}
                      </span>
                      <span className="text-xs text-gray-400">가중치 {item.weight}점</span>
                    </div>
                    <p className="text-sm font-medium text-gray-800">{item.item}</p>
                    {item.auto_status && (
                      <p className="text-xs text-blue-600 mt-1">
                        🤖 자동감지: {item.auto_status}
                      </p>
                    )}
                  </div>

                  {/* 상태 선택 */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <select
                      value={currentStatus || ''}
                      onChange={e => setResponses(prev => ({ ...prev, [item.id]: e.target.value }))}
                      className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">선택하세요</option>
                      {STATUS_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : item.id)}
                      className="p-1 text-gray-400 hover:text-gray-600"
                    >
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>

              {/* 가이던스 (확장 시) */}
              {isExpanded && (
                <div className="px-4 pb-4 border-t border-gray-100 pt-3">
                  <p className="text-xs text-gray-600 bg-blue-50 rounded-lg p-3">
                    💡 {item.guidance}
                  </p>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* 하단 버튼 */}
      <div className="flex justify-end">
        <button
          onClick={handleDownloadReport}
          disabled={generating}
          className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 disabled:opacity-50"
        >
          <FileSearch className="w-4 h-4" />
          {generating ? '보고서 생성 중...' : 'PIA 보고서 초안 다운로드'}
        </button>
      </div>
    </div>
  )
}
