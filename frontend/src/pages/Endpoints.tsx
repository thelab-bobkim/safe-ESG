/**
 * MediSafe Clinic - SafeEndpoint 페이지
 * 병원 내 PC 보안 상태 관리 + 항목별 조치 가이드
 */
import { useState, useEffect } from 'react'
import { Monitor, Plus, RefreshCw, Download, Info, Wifi, WifiOff, AlertTriangle, CheckCircle, X, ChevronRight } from 'lucide-react'
import { endpointApi } from '../api/client'

interface Endpoint {
  id: number; hostname: string; ip_address: string; os_type: string; os_version: string
  location: string; status: string; security_score: number; disk_encrypted: boolean | null
  antivirus_installed: boolean | null; antivirus_updated: boolean | null; os_patched: boolean | null
  usb_blocked: boolean | null; firewall_enabled: boolean | null; screen_lock_enabled: boolean | null
  emr_detected: string | null
  last_seen_at: string | null; registered_at: string | null
}

function getEmrLabel(emrDetected: string | null): { label: string; detected: boolean; names: string[] } {
  if (!emrDetected) return { label: '미감지', detected: false, names: [] }
  try {
    const parsed = JSON.parse(emrDetected)
    if (Array.isArray(parsed) && parsed.length > 0) {
      return { label: `감지됨 (${parsed.join(', ')})`, detected: true, names: parsed }
    }
  } catch {}
  if (typeof emrDetected === 'string' && emrDetected.trim() && emrDetected !== '[]') {
    return { label: emrDetected, detected: true, names: [emrDetected] }
  }
  return { label: '미감지', detected: false, names: [] }
}

// ── 보안 항목별 가이드 정의 ─────────────────────────────────────────────
interface SecurityItem {
  key: keyof Endpoint
  label: string
  icon: string
  passGuide: string
  failGuide: string
  unknownGuide: string
  regulation: string
}

const SECURITY_ITEMS: SecurityItem[] = [
  {
    key: 'disk_encrypted',
    label: '디스크 암호화',
    icon: '💾',
    regulation: '개인정보보호법 제29조 제4호',
    passGuide: `✅ BitLocker가 활성화되어 있습니다.

• PC 분실/도난 시에도 환자 개인정보가 보호됩니다.
• 복구 키를 USB나 인쇄물로 별도 보관하고 있는지 확인하세요.`,
    failGuide: `❌ BitLocker(디스크 암호화)가 꺼져 있습니다.

[즉시 조치 방법]
1. Windows 검색창에 "BitLocker" 입력
2. "BitLocker 드라이브 암호화" 클릭
3. C: 드라이브 → "BitLocker 켜기" 클릭
4. 복구 키 저장 방법 선택 → "파일에 저장" 권장
5. 암호화 시작 (수 시간 소요, PC 정상 사용 가능)

⚠️ 주의: 복구 키를 잃어버리면 데이터 접근 불가 → 반드시 별도 보관`,
    unknownGuide: `⚠️ 에이전트가 아직 데이터를 전송하지 않았습니다.

[확인 방법]
1. 이 PC에 MediSafe 에이전트가 설치되어 있는지 확인
2. 에이전트 설치 후 5분 내에 자동으로 상태가 업데이트됩니다
3. Windows 검색 → "BitLocker" → 현재 활성화 여부 직접 확인 가능`,
  },
  {
    key: 'antivirus_installed',
    label: '백신(바이러스 방지)',
    icon: '🛡️',
    regulation: '개인정보보호법 제29조 제5호',
    passGuide: `✅ Windows Defender(백신)가 활성화되어 있습니다.

• 실시간 보호가 켜져 있어 랜섬웨어·악성코드로부터 보호됩니다.
• 바이러스 정의 파일이 최신 상태인지 주기적으로 확인하세요.`,
    failGuide: `❌ 백신(실시간 보호)이 꺼져 있습니다.

[즉시 조치 방법]
1. 작업 표시줄 방패 아이콘 클릭 또는
   Windows 설정 → 개인 정보 및 보안 → Windows 보안
2. "바이러스 및 위협 방지" 클릭
3. "실시간 보호" 토글 → 켜기

[타사 백신이 있는 경우]
• V3, 알약, 카스퍼스키 등이 설치된 경우: 해당 백신 정상 작동 확인
• Windows Defender는 타사 백신 설치 시 자동으로 꺼지는 것이 정상

⚠️ 백신 없는 PC: 랜섬웨어 감염 시 환자 기록 전체 손실 위험`,
    unknownGuide: `⚠️ 에이전트 미설치 또는 데이터 수신 전입니다.

[확인 방법]
• Windows 보안 → 바이러스 및 위협 방지 → 실시간 보호 상태 직접 확인
• 에이전트 설치 후 자동으로 탐지됩니다`,
  },
  {
    key: 'antivirus_updated',
    label: '백신 업데이트',
    icon: '🔄',
    regulation: '개인정보보호법 제29조 제5호',
    passGuide: `✅ 백신 바이러스 정의 파일이 최신 상태입니다.`,
    failGuide: `❌ 백신 업데이트가 필요합니다.

[조치 방법]
1. Windows 보안 → 바이러스 및 위협 방지
2. "보호 업데이트" → "업데이트 확인" 클릭
3. 자동 업데이트 설정 확인: Windows Update → 고급 옵션 → 자동 다운로드 켜기

• Windows Defender는 인터넷 연결 시 자동 업데이트됩니다
• 수동으로 업데이트하려면 위 방법으로 즉시 최신화 가능`,
    unknownGuide: `⚠️ 에이전트 미설치 또는 데이터 수신 전입니다.

• 에이전트 설치 후 자동으로 탐지됩니다
• 직접 확인: Windows 보안 → 바이러스 및 위협 방지 → 보호 업데이트`,
  },
  {
    key: 'os_patched',
    label: 'OS 최신 패치',
    icon: '📦',
    regulation: '개인정보보호법 제29조',
    passGuide: `✅ 운영체제 보안 패치가 최신 상태입니다.

• 알려진 취약점이 모두 패치되어 해킹 위험이 낮습니다.
• Windows Update 자동 설치를 유지하세요.`,
    failGuide: `❌ OS 보안 업데이트가 필요합니다.

[즉시 조치 방법]
1. Windows 설정 → Windows Update → "지금 업데이트 확인"
2. 모든 보안 업데이트 설치 후 재시작
3. 자동 업데이트 켜기: Windows Update → 고급 옵션 → 자동으로 다운로드 및 설치

⚠️ 업데이트 중 재시작 필요 → 진료 종료 후 업데이트 권장`,
    unknownGuide: `⚠️ 에이전트 미설치 또는 데이터 수신 전입니다.

• 직접 확인: Windows 설정 → Windows Update
• 에이전트 설치 후 자동으로 탐지됩니다`,
  },
  {
    key: 'firewall_enabled',
    label: '방화벽',
    icon: '🔥',
    regulation: '개인정보보호법 제29조 제2호',
    passGuide: `✅ Windows 방화벽이 활성화되어 있습니다.

• 외부로부터의 무단 네트워크 접근이 차단됩니다.
• 도메인/개인/공용 프로필 모두 켜져 있는지 확인하세요.`,
    failGuide: `❌ 방화벽이 꺼져 있습니다.

[즉시 조치 방법]
1. Windows 검색 → "방화벽" → "Windows Defender 방화벽" 클릭
2. 왼쪽 "Windows Defender 방화벽 켜기/끄기"
3. 도메인 네트워크 / 개인 네트워크 / 공용 네트워크 모두 → "켜기" 선택

⚠️ 방화벽이 꺼진 PC는 동일 네트워크 내 악성 트래픽에 무방비 상태`,
    unknownGuide: `⚠️ 에이전트 미설치 또는 데이터 수신 전입니다.

• 직접 확인: 제어판 → Windows Defender 방화벽 → 상태 확인
• 에이전트 설치 후 자동으로 탐지됩니다`,
  },
  {
    key: 'screen_lock_enabled',
    label: '화면 잠금',
    icon: '🔒',
    regulation: '개인정보보호법 제29조 제6호',
    passGuide: `✅ 화면 잠금(화면 보호기)이 설정되어 있습니다.

• 자리를 비울 때 환자 화면이 자동으로 잠깁니다.
• 빠른 잠금: Windows + L 단축키를 습관화하세요.`,
    failGuide: `❌ 화면 잠금이 설정되지 않았습니다.

[즉시 조치 방법]
1. 바탕화면 우클릭 → 개인 설정 → 잠금 화면
2. 화면 보호기 설정 → 대기 시간 5분 → "다시 시작할 때 로그온 화면 표시" 체크
   또는
3. Windows 설정 → 계정 → 로그인 옵션 → "자동으로 잠금"

⚠️ 진료 중 자리를 비울 때 항상 Windows + L 로 즉시 잠금`,
    unknownGuide: `⚠️ 에이전트 미설치 또는 데이터 수신 전입니다.

• 직접 확인: Windows 설정 → 개인 설정 → 잠금 화면
• 에이전트 설치 후 자동으로 탐지됩니다`,
  },
  {
    key: 'usb_blocked',
    label: 'USB 모니터링',
    icon: '🚫',
    regulation: '개인정보보호법 제29조 제6호',
    passGuide: `✅ USB 이벤트 모니터링이 활성화되어 있습니다.

• USB 장치 연결/해제가 SafeLog에 자동 기록됩니다.
• 비정상 USB 사용 시 즉시 경보가 발생합니다.`,
    failGuide: `❌ USB 모니터링이 비활성 상태입니다.

[조치 방법]
• MediSafe 에이전트 v0.2 이상에서 USB 모니터링이 지원됩니다
• 에이전트를 최신 버전으로 업데이트하세요
• 운영 정책: USB 반출 대장을 별도로 운영하는 것을 권장합니다`,
    unknownGuide: `⚠️ 에이전트 미설치 또는 데이터 수신 전입니다.

• MediSafe 에이전트 설치 시 USB 연결/해제 이벤트가 자동으로 기록됩니다
• SafeLog에서 USB 이벤트를 확인할 수 있습니다`,
  },
]

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
  online:   { label: '온라인',   color: 'text-green-600',  bg: 'bg-green-50',  icon: <Wifi className="w-3 h-3" /> },
  offline:  { label: '오프라인', color: 'text-gray-400',   bg: 'bg-gray-50',   icon: <WifiOff className="w-3 h-3" /> },
  warning:  { label: '경고',     color: 'text-yellow-600', bg: 'bg-yellow-50', icon: <AlertTriangle className="w-3 h-3" /> },
  critical: { label: '위험',     color: 'text-red-600',    bg: 'bg-red-50',    icon: <AlertTriangle className="w-3 h-3" /> },
}

function getItemStatus(val: boolean | null): 'pass' | 'fail' | 'unknown' {
  if (val === null) return 'unknown'
  return val ? 'pass' : 'fail'
}

function StatusBadge({ value }: { value: boolean | null }) {
  if (value === null) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 inline-block" />미확인
    </span>
  )
  return value
    ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">✓ 완료</span>
    : <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-600">✗ 미완료</span>
}

export default function Endpoints() {
  const [endpoints, setEndpoints] = useState<Endpoint[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Endpoint | null>(null)
  const [activeGuide, setActiveGuide] = useState<SecurityItem | null>(null)
  const [showAdd, setShowAdd] = useState(false)

  const load = () => {
    setLoading(true)
    endpointApi.list()
      .then(res => setEndpoints(res.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const scoreColor = (s: number) => s >= 80 ? 'text-green-600' : s >= 60 ? 'text-yellow-600' : 'text-red-600'
  const scoreBg    = (s: number) => s >= 80 ? 'bg-green-50'  : s >= 60 ? 'bg-yellow-50'  : 'bg-red-50'
  const scoreGrade = (s: number) => s >= 80 ? 'A' : s >= 60 ? 'B' : s >= 40 ? 'C' : 'F'

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

      {/* 테이블 */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              {['PC명','위치','OS','상태','보안점수','디스크 암호화','백신','패치','EMR 감지','마지막 접속'].map(h => (
                <th key={h} className="text-left text-xs font-medium text-gray-500 px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr><td colSpan={9} className="text-center py-8 text-gray-400">로딩 중...</td></tr>
            ) : endpoints.length === 0 ? (
              <tr><td colSpan={9} className="text-center py-8 text-gray-400">등록된 PC가 없습니다</td></tr>
            ) : endpoints.map(ep => {
              const statusCfg = STATUS_CONFIG[ep.status] || STATUS_CONFIG.offline
              const emrInfo = getEmrLabel(ep.emr_detected)
              return (
                <tr key={ep.id} className="hover:bg-blue-50/30 cursor-pointer transition-colors"
                    onClick={() => { setSelected(ep); setActiveGuide(null) }}>
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
                    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full ${statusCfg.bg} ${statusCfg.color}`}>
                      {statusCfg.icon}{statusCfg.label}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg ${scoreBg(ep.security_score)}`}>
                      <span className={`text-sm font-bold ${scoreColor(ep.security_score)}`}>
                        {ep.security_score?.toFixed(0) ?? 0}점
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3"><StatusBadge value={ep.disk_encrypted} /></td>
                  <td className="px-4 py-3"><StatusBadge value={ep.antivirus_installed} /></td>
                  <td className="px-4 py-3"><StatusBadge value={ep.os_patched} /></td>
                  <td className="px-4 py-3">
                    {emrInfo.detected ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                        🏥 감지됨
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
                        미감지
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {ep.last_seen_at
                      ? new Date(ep.last_seen_at).toLocaleString('ko-KR',
                          { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' })
                      : '-'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* PC 상세 + 조치 가이드 모달 */}
      {selected && (
        <div className="fixed inset-0 bg-black/40 flex items-start justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl my-8">
            {/* 모달 헤더 */}
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Monitor className="w-5 h-5 text-blue-600" />
                <div>
                  <h3 className="font-bold text-gray-900">{selected.hostname}</h3>
                  <p className="text-xs text-gray-500">{selected.ip_address} · {selected.location || '위치 미설정'}</p>
                </div>
              </div>
              <button onClick={() => { setSelected(null); setActiveGuide(null) }}
                      className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* 점수 */}
            <div className={`px-6 py-4 flex items-center gap-6 ${scoreBg(selected.security_score)}`}>
              <div className="text-center">
                <p className={`text-5xl font-black ${scoreColor(selected.security_score)}`}>
                  {selected.security_score?.toFixed(0) ?? 0}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">보안 점수</p>
              </div>
              {/* 조치 스크립트 다운로드 버튼 (F8) */}
              {selected.security_score < 100 && (
                <a
                  href={`/api/v1/endpoints/${selected.id}/remediation-script`}
                  download
                  onClick={e => {
                    const token = localStorage.getItem('access_token')
                    if (!token) { e.preventDefault(); return }
                    // fetch로 다운로드 (인증 헤더 필요)
                    e.preventDefault()
                    fetch(`/api/v1/endpoints/${selected.id}/remediation-script`, {
                      headers: { Authorization: `Bearer ${token}` }
                    }).then(res => res.blob()).then(blob => {
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = `MediSafe_Remediation_${selected.hostname}.ps1`
                      a.click()
                      URL.revokeObjectURL(url)
                    })
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-orange-600 text-white rounded-lg text-xs font-semibold hover:bg-orange-700 transition-colors flex-shrink-0"
                >
                  📥 조치 스크립트 다운로드
                </a>
              )}
              <div className={`text-4xl font-black ${scoreColor(selected.security_score)}`}>
                {scoreGrade(selected.security_score)}등급
              </div>
              <div className="flex-1 text-sm text-gray-600 space-y-1">
                <div>
                  {selected.security_score >= 80
                    ? '✅ 보안 상태가 양호합니다.'
                    : selected.security_score >= 60
                    ? '⚠️ 일부 항목의 조치가 필요합니다. 아래 항목을 클릭하여 가이드를 확인하세요.'
                    : '❌ 즉각적인 보안 조치가 필요합니다. 아래 빨간 항목을 먼저 처리하세요.'}
                </div>
                {/* EMR 감지 배지 */}
                {(() => {
                  const emr = getEmrLabel(selected.emr_detected)
                  return emr.detected ? (
                    <div className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-purple-100 text-purple-700 text-xs font-medium">
                      🏥 EMR 감지됨: {emr.names.join(', ')}
                    </div>
                  ) : (
                    <div className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-gray-100 text-gray-500 text-xs">
                      EMR: 미감지
                    </div>
                  )
                })()}
              </div>
            </div>

            <div className="flex">
              {/* 항목 목록 */}
              <div className="w-64 border-r border-gray-100 p-3 space-y-1">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide px-2 mb-2">보안 항목 — 클릭하여 가이드 확인</p>
                {SECURITY_ITEMS.map(item => {
                  const val = selected[item.key] as boolean | null
                  const st = getItemStatus(val)
                  const isActive = activeGuide?.key === item.key
                  return (
                    <button
                      key={item.key}
                      onClick={() => setActiveGuide(isActive ? null : item)}
                      className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition-all
                        ${isActive ? 'bg-blue-600 text-white shadow-md' : 'hover:bg-gray-50 text-gray-700'}
                      `}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-base">{item.icon}</span>
                        <span className="text-sm font-medium">{item.label}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        {st === 'pass' && <span className={`text-xs ${isActive ? 'text-green-200' : 'text-green-600'}`}>✓</span>}
                        {st === 'fail' && <span className={`text-xs ${isActive ? 'text-red-200' : 'text-red-500'}`}>✗</span>}
                        {st === 'unknown' && <span className={`text-xs ${isActive ? 'text-gray-300' : 'text-gray-400'}`}>?</span>}
                        <ChevronRight className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-gray-300'}`} />
                      </div>
                    </button>
                  )
                })}
              </div>

              {/* 가이드 패널 */}
              <div className="flex-1 p-5">
                {!activeGuide ? (
                  <div className="h-full flex flex-col items-center justify-center text-center text-gray-400 space-y-2 py-10">
                    <Info className="w-10 h-10 text-gray-200" />
                    <p className="font-medium text-gray-500">항목을 클릭하면</p>
                    <p className="text-sm">상태별 조치 가이드가 표시됩니다</p>
                    <div className="mt-4 text-xs space-y-1">
                      <p><span className="text-green-600 font-bold">✓ 완료</span> — 통과 기준 및 유지 방법</p>
                      <p><span className="text-red-500 font-bold">✗ 미완료</span> — 즉시 조치 단계별 가이드</p>
                      <p><span className="text-gray-400 font-bold">? 미확인</span> — 직접 확인 방법 안내</p>
                    </div>
                  </div>
                ) : (() => {
                  const val = selected[activeGuide.key] as boolean | null
                  const st = getItemStatus(val)
                  const guide = st === 'pass' ? activeGuide.passGuide
                              : st === 'fail' ? activeGuide.failGuide
                              : activeGuide.unknownGuide
                  const headerColor = st === 'pass' ? 'bg-green-600' : st === 'fail' ? 'bg-red-600' : 'bg-gray-500'
                  const headerLabel = st === 'pass' ? '✅ 통과 — 현재 상태 양호'
                                    : st === 'fail' ? '❌ 미완료 — 즉시 조치 필요'
                                    : '⚠️ 미확인 — 직접 확인 필요'
                  return (
                    <div className="space-y-3">
                      <div className={`rounded-xl overflow-hidden`}>
                        <div className={`px-4 py-2.5 ${headerColor} text-white text-sm font-semibold flex items-center justify-between`}>
                          <span>{activeGuide.icon} {activeGuide.label}</span>
                          <span className="text-xs font-normal opacity-80">{headerLabel}</span>
                        </div>
                        <div className="px-4 py-4 bg-gray-50 text-sm text-gray-700 whitespace-pre-line leading-relaxed">
                          {guide}
                        </div>
                      </div>
                      <div className="px-3 py-2 bg-blue-50 rounded-lg text-xs text-blue-600">
                        📋 관련 규정: <span className="font-semibold">{activeGuide.regulation}</span>
                      </div>
                    </div>
                  )
                })()}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 에이전트 안내 배너 */}
      {endpoints.length > 0 && endpoints.every(e => e.status === 'offline') && (
        <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl">
          <Info className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <p className="font-semibold text-blue-800 text-sm">사내 PC에 에이전트를 설치하세요</p>
            <p className="text-xs text-blue-600 mt-1">
              PC에 에이전트를 설치하면 보안 상태가 자동으로 수집됩니다.
            </p>
          </div>
          <a href="/api/v1/agent/download"
             className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 flex-shrink-0">
            <Download className="w-3.5 h-3.5" /> 에이전트 다운로드
          </a>
        </div>
      )}

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
