/**
 * MediSafe Clinic - 병원 셀프 온보딩 페이지
 * 3단계 폼: 병원정보 → 담당자 → 플랜선택 → 완료
 */
import { useState } from 'react'
import { CheckCircle, Building2, User, CreditCard, ChevronRight, ChevronLeft, Download } from 'lucide-react'

interface RegisterForm {
  // 1단계: 병원정보
  hospital_name: string
  business_number: string
  phone: string
  // 2단계: 담당자
  admin_name: string
  admin_email: string
  admin_password: string
  admin_password_confirm: string
  // 3단계: 플랜
  plan: 'basic' | 'standard' | 'pro'
}

interface RegisterResult {
  tenant_id: number
  enroll_code: string
  plan: string
  max_endpoints: number
  trial_ends_at: string | null
  message: string
}

const PLANS = [
  {
    id: 'basic' as const,
    name: '베이직',
    price: '49,000원',
    unit: '/월',
    maxEndpoints: 5,
    features: ['PC 최대 5대', '기본 보안 모니터링', '컴플라이언스 체크리스트', '이메일 알림'],
    color: 'border-gray-300',
    headerColor: 'bg-gray-100 text-gray-700',
    buttonColor: 'bg-gray-600 hover:bg-gray-700',
  },
  {
    id: 'standard' as const,
    name: '스탠다드',
    price: '149,000원',
    unit: '/월',
    maxEndpoints: 20,
    features: ['PC 최대 20대', '실시간 보안 알림', 'PDF 보고서 자동화', 'EMR 프로세스 감지', 'CSV 감사 로그'],
    color: 'border-blue-500',
    headerColor: 'bg-blue-600 text-white',
    buttonColor: 'bg-blue-600 hover:bg-blue-700',
    recommended: true,
  },
  {
    id: 'pro' as const,
    name: '프로',
    price: '349,000원',
    unit: '/월',
    maxEndpoints: 100,
    features: ['PC 최대 100대', '스탠다드 모든 기능', 'USB 이벤트 WORM 저장', '전담 기술지원', '맞춤형 컴플라이언스'],
    color: 'border-purple-500',
    headerColor: 'bg-purple-700 text-white',
    buttonColor: 'bg-purple-700 hover:bg-purple-800',
  },
]

const API_BASE = '/api/v1'

export default function Register() {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState<RegisterForm>({
    hospital_name: '',
    business_number: '',
    phone: '',
    admin_name: '',
    admin_email: '',
    admin_password: '',
    admin_password_confirm: '',
    plan: 'standard',
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RegisterResult | null>(null)
  const [error, setError] = useState<string>('')

  const updateForm = (field: keyof RegisterForm, value: string) => {
    setForm(prev => ({ ...prev, [field]: value }))
    setError('')
  }

  // 단계별 유효성 검사
  const validateStep = (s: number): string => {
    if (s === 1) {
      if (!form.hospital_name.trim()) return '병원명을 입력하세요.'
      if (!form.business_number.trim()) return '사업자등록번호를 입력하세요.'
    }
    if (s === 2) {
      if (!form.admin_name.trim()) return '담당자명을 입력하세요.'
      if (!form.admin_email.trim()) return '이메일을 입력하세요.'
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.admin_email)) return '올바른 이메일 형식을 입력하세요.'
      if (form.admin_password.length < 8) return '비밀번호는 8자 이상이어야 합니다.'
      if (form.admin_password !== form.admin_password_confirm) return '비밀번호가 일치하지 않습니다.'
    }
    return ''
  }

  const handleNext = () => {
    const err = validateStep(step)
    if (err) { setError(err); return }
    setStep(prev => prev + 1)
  }

  const handleSubmit = async () => {
    const err = validateStep(2)
    if (err) { setError(err); return }

    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/auth/register-hospital`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hospital_name: form.hospital_name,
          business_number: form.business_number,
          admin_name: form.admin_name,
          admin_email: form.admin_email,
          admin_password: form.admin_password,
          phone: form.phone,
          plan: form.plan,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || '등록 중 오류가 발생했습니다.')
        return
      }
      setResult(data)
      setStep(4)
    } catch (e: any) {
      setError('서버 연결 오류: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* 로고 */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-black text-blue-800">🏥 MediSafe Clinic</h1>
          <p className="text-blue-600 mt-1">소형 병·의원 의료정보보호 SaaS</p>
        </div>

        {/* 단계 표시기 (완료 화면 제외) */}
        {step < 4 && (
          <div className="flex items-center justify-center mb-8 gap-3">
            {[
              { num: 1, label: '병원 정보', icon: <Building2 className="w-4 h-4" /> },
              { num: 2, label: '담당자', icon: <User className="w-4 h-4" /> },
              { num: 3, label: '플랜 선택', icon: <CreditCard className="w-4 h-4" /> },
            ].map(({ num, label, icon }) => (
              <div key={num} className="flex items-center gap-2">
                <div className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold transition-colors ${
                  step === num
                    ? 'bg-blue-600 text-white shadow-md'
                    : step > num
                    ? 'bg-green-500 text-white'
                    : 'bg-white text-gray-400 border border-gray-200'
                }`}>
                  {step > num ? <CheckCircle className="w-4 h-4" /> : icon}
                  {label}
                </div>
                {num < 3 && <ChevronRight className="w-4 h-4 text-gray-300" />}
              </div>
            ))}
          </div>
        )}

        {/* 카드 */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden">

          {/* 1단계: 병원 정보 */}
          {step === 1 && (
            <div className="p-8">
              <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                <Building2 className="w-5 h-5 text-blue-600" /> 병원 정보 입력
              </h2>
              <div className="space-y-4">
                <FormField
                  label="병원명 *"
                  placeholder="예: 연세가정의원"
                  value={form.hospital_name}
                  onChange={v => updateForm('hospital_name', v)}
                />
                <FormField
                  label="사업자등록번호 *"
                  placeholder="예: 123-45-67890"
                  value={form.business_number}
                  onChange={v => updateForm('business_number', v)}
                />
                <FormField
                  label="대표 전화번호"
                  placeholder="예: 02-1234-5678"
                  value={form.phone}
                  onChange={v => updateForm('phone', v)}
                />
              </div>
              {error && <ErrorBox message={error} />}
              <div className="mt-6 flex justify-end">
                <button onClick={handleNext} className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold transition-colors">
                  다음 <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* 2단계: 담당자 */}
          {step === 2 && (
            <div className="p-8">
              <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                <User className="w-5 h-5 text-blue-600" /> 관리자 계정 설정
              </h2>
              <div className="space-y-4">
                <FormField
                  label="담당자명 *"
                  placeholder="예: 김원장"
                  value={form.admin_name}
                  onChange={v => updateForm('admin_name', v)}
                />
                <FormField
                  label="이메일 주소 *"
                  type="email"
                  placeholder="예: doctor@clinic.kr"
                  value={form.admin_email}
                  onChange={v => updateForm('admin_email', v)}
                />
                <FormField
                  label="비밀번호 *"
                  type="password"
                  placeholder="8자 이상, 대소문자+숫자 조합"
                  value={form.admin_password}
                  onChange={v => updateForm('admin_password', v)}
                />
                <FormField
                  label="비밀번호 확인 *"
                  type="password"
                  placeholder="비밀번호를 다시 입력하세요"
                  value={form.admin_password_confirm}
                  onChange={v => updateForm('admin_password_confirm', v)}
                />
              </div>
              {error && <ErrorBox message={error} />}
              <div className="mt-6 flex justify-between">
                <button onClick={() => setStep(1)} className="flex items-center gap-2 px-4 py-2 text-gray-500 hover:text-gray-700 transition-colors">
                  <ChevronLeft className="w-4 h-4" /> 이전
                </button>
                <button onClick={handleNext} className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold transition-colors">
                  다음 <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* 3단계: 플랜 선택 */}
          {step === 3 && (
            <div className="p-8">
              <h2 className="text-xl font-bold text-gray-900 mb-2 flex items-center gap-2">
                <CreditCard className="w-5 h-5 text-blue-600" /> 플랜 선택
              </h2>
              <p className="text-sm text-gray-500 mb-6">30일 무료 체험 후 과금됩니다. 언제든지 변경 가능합니다.</p>

              <div className="grid grid-cols-3 gap-4">
                {PLANS.map(plan => (
                  <div
                    key={plan.id}
                    onClick={() => updateForm('plan', plan.id)}
                    className={`relative border-2 rounded-xl cursor-pointer transition-all ${
                      form.plan === plan.id
                        ? plan.color + ' shadow-lg scale-105'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    {plan.recommended && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                        <span className="bg-blue-600 text-white text-xs font-bold px-3 py-1 rounded-full">추천</span>
                      </div>
                    )}
                    <div className={`p-3 rounded-t-xl ${plan.headerColor}`}>
                      <h3 className="font-bold text-center">{plan.name}</h3>
                    </div>
                    <div className="p-4">
                      <div className="text-center mb-3">
                        <span className="text-2xl font-black text-gray-900">{plan.price}</span>
                        <span className="text-gray-500 text-sm">{plan.unit}</span>
                      </div>
                      <p className="text-center text-xs text-gray-500 mb-3">PC 최대 {plan.maxEndpoints}대</p>
                      <ul className="space-y-1.5">
                        {plan.features.map(f => (
                          <li key={f} className="text-xs text-gray-600 flex items-start gap-1.5">
                            <span className="text-green-500 font-bold mt-0.5">✓</span>
                            {f}
                          </li>
                        ))}
                      </ul>
                    </div>
                    {form.plan === plan.id && (
                      <div className="p-3 border-t border-gray-100 text-center">
                        <span className="text-xs font-bold text-blue-600">✓ 선택됨</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {error && <ErrorBox message={error} />}

              <div className="mt-6 flex justify-between">
                <button onClick={() => setStep(2)} className="flex items-center gap-2 px-4 py-2 text-gray-500 hover:text-gray-700 transition-colors">
                  <ChevronLeft className="w-4 h-4" /> 이전
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="flex items-center gap-2 px-8 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl font-semibold transition-colors"
                >
                  {loading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      등록 중...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4" /> 병원 등록 완료
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* 4단계: 완료 */}
          {step === 4 && result && (
            <div className="p-8 text-center">
              <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-10 h-10 text-green-600" />
              </div>
              <h2 className="text-2xl font-black text-gray-900 mb-2">등록 완료! 🎉</h2>
              <p className="text-gray-500 mb-8">{form.hospital_name} 병원이 성공적으로 등록되었습니다.</p>

              {/* 등록 코드 크게 표시 */}
              <div className="bg-blue-50 border-2 border-blue-300 rounded-2xl p-6 mb-6">
                <p className="text-sm text-blue-600 font-semibold mb-2">에이전트 등록 코드</p>
                <p className="text-4xl font-black tracking-widest text-blue-800 font-mono">
                  {result.enroll_code}
                </p>
                <p className="text-xs text-blue-500 mt-3">
                  PC에 MediSafe 에이전트를 설치할 때 이 코드를 입력하세요.
                </p>
              </div>

              {/* 안내 */}
              <div className="text-left bg-gray-50 rounded-xl p-5 mb-6 space-y-3">
                <h3 className="font-bold text-gray-800">시작하기 3단계</h3>
                <div className="space-y-2 text-sm text-gray-600">
                  <div className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">1</span>
                    <div>
                      <p className="font-semibold text-gray-800">로그인</p>
                      <p>아래 버튼을 클릭하여 등록한 이메일과 비밀번호로 로그인하세요.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">2</span>
                    <div>
                      <p className="font-semibold text-gray-800">에이전트 다운로드 및 설치</p>
                      <p>대시보드에서 에이전트를 다운로드하여 병원 PC에 설치하세요.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">3</span>
                    <div>
                      <p className="font-semibold text-gray-800">등록 코드 입력</p>
                      <p>에이전트 설치 시 위의 등록 코드 <strong>{result.enroll_code}</strong>를 입력하세요.</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex gap-3 justify-center">
                <a
                  href="/login"
                  className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold transition-colors"
                >
                  로그인하기 →
                </a>
                <a
                  href="/downloads/MediSafe_Agent_Setup_v1.1.exe"
                  className="flex items-center gap-2 px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl font-semibold transition-colors"
                >
                  <Download className="w-4 h-4" /> 에이전트 다운로드
                </a>
              </div>

              <p className="text-xs text-gray-400 mt-4">
                30일 무료 체험 기간 중 언제든지 플랜을 변경하실 수 있습니다.
              </p>
            </div>
          )}
        </div>

        {/* 이미 계정 있음 링크 */}
        {step < 4 && (
          <p className="text-center text-sm text-gray-500 mt-4">
            이미 계정이 있으신가요?{' '}
            <a href="/login" className="text-blue-600 hover:underline font-medium">로그인</a>
          </p>
        )}
      </div>
    </div>
  )
}

function FormField({
  label, value, onChange, placeholder, type = 'text'
}: {
  label: string; value: string; onChange: (v: string) => void
  placeholder?: string; type?: string
}) {
  return (
    <div>
      <label className="block text-sm font-semibold text-gray-700 mb-1.5">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-shadow"
      />
    </div>
  )
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600">
      ⚠️ {message}
    </div>
  )
}
