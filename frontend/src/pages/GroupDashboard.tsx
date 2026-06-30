/**
 * MediSafe Clinic - 다중 지점 관리 (F9)
 */
import { useState, useEffect } from 'react'
import { Building2, Shield, Monitor, Plus, AlertTriangle } from 'lucide-react'
import apiClient from '../api/client'

interface TenantSummary {
  tenant_id: number
  tenant_name: string
  endpoint_count: number
  online_count: number
  avg_security_score: number
  compliance_score: number | null
  is_owner?: boolean
}

interface GroupSummary {
  group_id: number
  group_name: string
  total_tenants: number
  total_endpoints: number
  online_endpoints: number
  group_avg_score: number
  tenant_summaries: TenantSummary[]
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 90 ? 'bg-green-100 text-green-700'
    : score >= 70 ? 'bg-blue-100 text-blue-700'
    : score >= 50 ? 'bg-yellow-100 text-yellow-700'
    : 'bg-red-100 text-red-700'
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-bold ${color}`}>
      {score.toFixed(0)}점
    </span>
  )
}

export default function GroupDashboard() {
  const [groupId, setGroupId] = useState<number | null>(null)
  const [summary, setSummary] = useState<GroupSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [groupName, setGroupName] = useState('')
  const [error, setError] = useState<string | null>(null)

  // 현재 tenant의 group_id를 서버에서 가져오는 방법 없음 → create 후 받은 id 사용
  // 또는 profile API에서 추후 추가 가능. 지금은 그룹 생성 → 조회 플로우

  const handleCreateGroup = async () => {
    if (!groupName.trim()) return
    setCreating(true)
    setError(null)
    try {
      const res = await apiClient.post('/groups/', { name: groupName })
      const newGroupId = res.data.id
      setGroupId(newGroupId)
      await loadSummary(newGroupId)
    } catch (err: any) {
      setError(err.response?.data?.detail || '그룹 생성 실패')
    } finally {
      setCreating(false)
    }
  }

  const loadSummary = async (gid: number) => {
    setLoading(true)
    try {
      const res = await apiClient.get(`/groups/${gid}/summary`)
      setSummary(res.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || '조회 실패')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-xl font-bold text-gray-900">다중 지점 관리</h1>
        <p className="text-sm text-gray-500 mt-0.5">여러 지점의 보안 현황을 한 곳에서 관리하세요</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-500" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {!summary && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-4">
            <Building2 className="w-6 h-6 text-blue-600" />
            <h2 className="font-semibold text-gray-900">병원 그룹 생성</h2>
          </div>
          <p className="text-sm text-gray-600 mb-4">
            다중 지점을 관리하려면 먼저 병원 그룹을 생성하세요.
            그룹 생성 후 다른 병원 계정을 초대할 수 있습니다.
          </p>
          <div className="flex gap-3">
            <input
              type="text"
              value={groupName}
              onChange={e => setGroupName(e.target.value)}
              placeholder="그룹명 (예: 연세의료재단)"
              className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleCreateGroup}
              disabled={creating || !groupName.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 disabled:opacity-50"
            >
              <Plus className="w-4 h-4" />
              {creating ? '생성 중...' : '그룹 생성'}
            </button>
          </div>
        </div>
      )}

      {summary && (
        <>
          {/* 전체 통계 카드 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-500">소속 병원</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{summary.total_tenants}개</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-500">전체 PC</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{summary.total_endpoints}대</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-500">온라인 PC</p>
              <p className="text-2xl font-bold text-green-600 mt-1">{summary.online_endpoints}대</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-500">그룹 평균 보안점수</p>
              <p className="text-2xl font-bold text-blue-600 mt-1">{summary.group_avg_score.toFixed(0)}점</p>
            </div>
          </div>

          {/* 소속 병원 목록 */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-500 uppercase mb-3">
              {summary.group_name} — 소속 병원 목록
            </h2>
            <div className="space-y-3">
              {summary.tenant_summaries.map(t => (
                <div
                  key={t.tenant_id}
                  className="flex items-center justify-between p-3 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 bg-blue-100 rounded-xl flex items-center justify-center">
                      <Building2 className="w-4 h-4 text-blue-600" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-gray-900">{t.tenant_name}</p>
                        {t.is_owner && (
                          <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-xs font-bold rounded">대표</span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500">
                        PC {t.endpoint_count}대 · 온라인 {t.online_count}대
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-xs text-gray-500">보안점수</p>
                      <ScoreBadge score={t.avg_security_score} />
                    </div>
                    {t.compliance_score !== null && (
                      <div className="text-right">
                        <p className="text-xs text-gray-500">컴플라이언스</p>
                        <ScoreBadge score={t.compliance_score} />
                      </div>
                    )}
                    <div className="flex items-center gap-1">
                      <Monitor className="w-4 h-4 text-gray-400" />
                      <Shield className="w-4 h-4 text-gray-400" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {loading && (
        <div className="flex items-center justify-center h-32">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      )}
    </div>
  )
}
