/**
 * MediSafe Clinic - SafeEndpoint 페이지
 * 병원 내 PC 보안 상태 관리
 */
import { useState, useEffect } from 'react'
import { Monitor, Plus, CheckCircle, XCircle, AlertTriangle, Wifi, WifiOff, RefreshCw } from 'lucide-react'
import { endpointApi } from '../api/client'

interface Endpoint {
  id: number; hostname: string; ip_address: string; os_type: string; os_version: string
  location: string; status: string; security_score: number; disk_encrypted: boolean | null
  antivirus_installed: boolean | null; antivirus_updated: boolean | null; os_patched: boolean | null
  usb_blocked: boolean | null; firewall_enabled: boolean | null; screen_lock_enabled: boolean | null
  last_seen_at: string | null; registered_at: string | null
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
  online: { label: '온라인', color: 'text-green-600', bg: 'bg-green-50', icon: <Wifi className="w-3 h-3" /> },
  offline: { label: '오프라인', color: 'text-gray-400', bg: 'bg-gray-50', icon: <WifiOff className="w-3 h-3" /> },
  warning: { label: '경고', color: 'text-yellow-600', bg: 'bg-yellow-50', icon: <AlertTriangle className="w-3 h-3" /> },
  critical: { label: '위험', color: 'text-red-600', bg: 'bg-red-50', icon: <AlertTriangle className="w-3 h-3" /> },
}

function BooleanBadge({ value, trueLabel = '완료', falseLabel = '미완료' }: {
  value: boolean | null; trueLabel?: string; falseLabel?: string
}) {
  if (value === null) return <span className="badge-info">미확인</span>
  return value
    ? <span className="badge-pass">✓ {trueLabel}</span>
    : <span className="badge-fail">✗ {falseLabel}</span>
}

export default function Endpoints() {
  const [endpoints, setEndpoints] = useState<Endpoint[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Endpoint | null>(null)
  const [showAdd, setShowAdd] = useState(false)

  const load = () => {
    setLoading(true)
    endpointApi.list()
      .then(res => setEndpoints(res.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const scoreColor = (score: number) =>
    score >= 80 ? 'text-green-600' : score >= 60 ? 'text-yellow-600' : 'text-red-600'
  const scoreBg = (score: number) =>
    score >= 80 ? 'bg-green-50' : score >= 60 ? 'bg-yellow-50' : 'bg-red-50'

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">엔드포인트 목록</h2>
          <p className="text-sm text-gray-500">병원 내 PC 보안 상태를 모니터링합니다</p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="btn-secondary flex items-center gap-2">
            <RefreshCw className="w-4 h-4" /> 새로고침
          </button>
          <button onClick={() => setShowAdd(true)} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" /> PC 등록
          </button>
        </div>
      </div>

      {/* 요약 카드 */}
      <div className="grid grid-cols-4 gap-3">
        {Object.entries(STATUS_CONFIG).map(([status, cfg]) => (
          <div key={status} className={`card flex items-center gap-3 p-4 ${cfg.bg}`}>
            <div className={cfg.color}>{cfg.icon}</div>
            <div>
              <p className={`text-2xl font-bold ${cfg.color}`}>
                {endpoints.filter(e => e.status === status).length}
              </p>
              <p className="text-xs text-gray-500">{cfg.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* 엔드포인트 테이블 */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {['PC명', '위치', 'OS', '상태', '보안점수', '디스크 암호화', '백신', '패치', '마지막 접속'].map(h => (
                <th key={h} className="text-left text-xs font-medium text-gray-500 px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr><td colSpan={9} className="text-center py-8 text-gray-400">로딩 중...</td></tr>
            ) : endpoints.length === 0 ? (
              <tr><td colSpan={9} className="text-center py-8 text-gray-400">등록된 PC가 없습니다</td></tr>
            ) : (
              endpoints.map(ep => {
                const status = STATUS_CONFIG[ep.status] || STATUS_CONFIG.offline
                return (
                  <tr
                    key={ep.id}
                    className="hover:bg-blue-50/30 cursor-pointer transition-colors"
                    onClick={() => setSelected(ep)}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Monitor className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-sm font-medium text-gray-900">{ep.hostname}</p>
                          <p className="text-xs text-gray-400">{ep.ip_address}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{ep.location || '-'}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{ep.os_version || ep.os_type}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full ${status.bg} ${status.color}`}>
                        {status.icon}{status.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg ${scoreBg(ep.security_score)}`}>
                        <span className={`text-sm font-bold ${scoreColor(ep.security_score)}`}>
                          {ep.security_score?.toFixed(0) ?? 0}점
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3"><BooleanBadge value={ep.disk_encrypted} /></td>
                    <td className="px-4 py-3"><BooleanBadge value={ep.antivirus_installed} /></td>
                    <td className="px-4 py-3"><BooleanBadge value={ep.os_patched} /></td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      {ep.last_seen_at
                        ? new Date(ep.last_seen_at).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                        : '-'
                      }
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 상세 모달 */}
      {selected && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg">
            <div className="p-6 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-gray-900">{selected.hostname}</h3>
                <p className="text-sm text-gray-500">{selected.ip_address} · {selected.location}</p>
              </div>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <div className="p-6 space-y-4">
              <div className="text-center">
                <p className={`text-4xl font-bold ${scoreColor(selected.security_score)}`}>
                  {selected.security_score?.toFixed(0) ?? 0}점
                </p>
                <p className="text-sm text-gray-500">보안 점수</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[
                  ['💾 디스크 암호화', selected.disk_encrypted],
                  ['🛡️ 백신 설치', selected.antivirus_installed],
                  ['🔄 백신 업데이트', selected.antivirus_updated],
                  ['📦 OS 패치', selected.os_patched],
                  ['🚫 USB 차단', selected.usb_blocked],
                  ['🔥 방화벽', selected.firewall_enabled],
                  ['🔒 화면 잠금', selected.screen_lock_enabled],
                ].map(([label, val]) => (
                  <div key={label as string} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                    <span className="text-sm text-gray-600">{label as string}</span>
                    <BooleanBadge value={val as boolean | null} trueLabel="적용" falseLabel="미적용" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* PC 등록 모달 */}
      {showAdd && <AddEndpointModal onClose={() => setShowAdd(false)} onSuccess={() => { setShowAdd(false); load() }} />}
    </div>
  )
}

function AddEndpointModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState({ hostname: '', ip_address: '', os_type: 'windows', os_version: '', location: '' })
  const [loading, setLoading] = useState(false)
  const [agentToken, setAgentToken] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await endpointApi.create(form)
      setAgentToken(res.data.agent_token)
    } catch (err: any) {
      alert(err.response?.data?.detail || '등록 실패')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="p-6 border-b flex justify-between">
          <h3 className="font-bold text-gray-900">PC 등록</h3>
          <button onClick={onClose} className="text-gray-400">✕</button>
        </div>
        {agentToken ? (
          <div className="p-6 text-center space-y-4">
            <CheckCircle className="w-12 h-12 text-green-500 mx-auto" />
            <p className="font-semibold text-gray-800">등록 완료!</p>
            <div className="p-3 bg-gray-100 rounded-lg">
              <p className="text-xs text-gray-500 mb-1">에이전트 토큰 (안전하게 보관하세요)</p>
              <p className="text-xs font-mono text-gray-800 break-all">{agentToken}</p>
            </div>
            <button onClick={onSuccess} className="btn-primary w-full">완료</button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-6 space-y-3">
            <Input label="PC 이름" value={form.hostname} onChange={v => setForm({...form, hostname: v})} required />
            <Input label="IP 주소 (선택)" value={form.ip_address} onChange={v => setForm({...form, ip_address: v})} />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">운영체제</label>
              <select value={form.os_type} onChange={e => setForm({...form, os_type: e.target.value})}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
                <option value="windows">Windows</option>
                <option value="macos">macOS</option>
                <option value="linux">Linux</option>
              </select>
            </div>
            <Input label="OS 버전 (선택)" value={form.os_version} onChange={v => setForm({...form, os_version: v})} placeholder="예: Windows 11 Pro" />
            <Input label="위치 (선택)" value={form.location} onChange={v => setForm({...form, location: v})} placeholder="예: 진료실 1" />
            <div className="flex gap-2 pt-2">
              <button type="button" onClick={onClose} className="btn-secondary flex-1">취소</button>
              <button type="submit" disabled={loading} className="btn-primary flex-1">
                {loading ? '등록 중...' : '등록'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

function Input({ label, value, onChange, required, placeholder }: {
  label: string; value: string; onChange: (v: string) => void
  required?: boolean; placeholder?: string
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input type="text" value={value} onChange={e => onChange(e.target.value)}
        required={required} placeholder={placeholder}
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
    </div>
  )
}
