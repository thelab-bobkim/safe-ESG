/**
 * MediSafe Clinic - 구독 관리 (F5)
 * 현재 플랜 표시, 업그레이드, 결제 이력
 */
import { useState, useEffect } from 'react'
import { CreditCard, CheckCircle, Crown, Zap, Shield, TrendingUp, RefreshCw } from 'lucide-react'
import apiClient from '../api/client'

interface SubscriptionData {
  plan: string
  plan_name: string
  plan_price: number
  plan_expires_at: string | null
  payment_method: string | null
  max_endpoints: number
  is_active: boolean
  test_mode: boolean
  billing_history: Array<{
    id: number
    plan: string
    plan_name: string
    amount: number
    status: string
    created_at: string
    paid_at: string | null
  }>
}

const PLANS = [
  {
    id: 'basic',
    name: 'Basic',
    price: 49000,
    priceLabel: '4.9만원/월',
    endpoints: '최대 3대',
    features: ['PC 보안 모니터링', '기본 컴플라이언스', '이메일 알림'],
    color: 'border-gray-200',
    headerColor: 'bg-gray-50',
    badge: null,
  },
  {
    id: 'standard',
    name: 'Standard',
    price: 149000,
    priceLabel: '14.9만원/월',
    endpoints: '최대 10대',
    features: ['PC 보안 모니터링', '전체 컴플라이언스', '주간 보안 리포트', '심평원 내보내기', 'PIA 보조'],
    color: 'border-blue-400',
    headerColor: 'bg-blue-50',
    badge: '추천',
  },
  {
    id: 'pro',
    name: 'Pro',
    price: 349000,
    priceLabel: '34.9만원/월',
    endpoints: '무제한',
    features: ['PC 보안 모니터링', '전체 컴플라이언스', '주간 보안 리포트', '심평원 내보내기', 'PIA 보조', '다중 지점 관리', '전담 지원'],
    color: 'border-purple-400',
    headerColor: 'bg-purple-50',
    badge: '최고 기능',
  },
]

const PLAN_ICONS: Record<string, JSX.Element> = {
  basic: <Shield className="w-5 h-5 text-gray-500" />,
  standard: <Crown className="w-5 h-5 text-blue-600" />,
  pro: <Zap className="w-5 h-5 text-purple-600" />,
}

export default function Billing() {
  const [subscription, setSubscription] = useState<SubscriptionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [upgrading, setUpgrading] = useState<string | null>(null)
  const [confirmModal, setConfirmModal] = useState<{ plan: string; price: number } | null>(null)

  useEffect(() => {
    loadSubscription()
  }, [])

  const loadSubscription = async () => {
    try {
      const res = await apiClient.get('/billing/subscription')
      setSubscription(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleUpgrade = async (planId: string, price: number) => {
    setConfirmModal({ plan: planId, price })
  }

  const handleConfirmPayment = async () => {
    if (!confirmModal) return
    setUpgrading(confirmModal.plan)
    setConfirmModal(null)

    try {
      // 1. 결제 세션 생성
      const checkoutRes = await apiClient.post('/billing/checkout', {
        plan: confirmModal.plan,
      })

      if (checkoutRes.data.test_mode) {
        // Mock 모드: confirm 바로 호출
        await apiClient.post('/billing/confirm', {
          payment_key: 'TEST_' + Date.now(),
          order_id: checkoutRes.data.order_id,
          amount: checkoutRes.data.amount,
        })
        alert('✅ 테스트 결제가 완료되었습니다!\n실제 운영 시 토스페이먼츠 연동이 필요합니다.')
        await loadSubscription()
      } else {
        // 실제 토스페이먼츠 결제 페이지로 이동
        window.location.href = checkoutRes.data.payment_url
      }
    } catch (err: any) {
      alert('결제 오류: ' + (err.response?.data?.detail || '알 수 없는 오류'))
    } finally {
      setUpgrading(null)
    }
  }

  const handleCancel = async () => {
    if (!confirm('구독을 취소하시겠습니까? 만료일까지 서비스가 유지됩니다.')) return
    try {
      const res = await apiClient.post('/billing/cancel', { reason: '사용자 요청' })
      alert(res.data.message)
    } catch (err: any) {
      alert('취소 오류: ' + (err.response?.data?.detail || ''))
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const currentPlan = subscription?.plan || 'standard'

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">구독 관리</h1>
          <p className="text-sm text-gray-500 mt-0.5">플랜을 업그레이드하여 더 많은 기능을 사용하세요</p>
        </div>
        <button onClick={loadSubscription} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded-lg hover:bg-gray-100">
          <RefreshCw className="w-4 h-4" />
          새로고침
        </button>
      </div>

      {/* 테스트 모드 알림 */}
      {subscription?.test_mode && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 flex items-start gap-3">
          <TrendingUp className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-yellow-800">테스트 결제 모드</p>
            <p className="text-sm text-yellow-700 mt-0.5">TOSS_SECRET_KEY가 설정되지 않아 테스트 모드로 동작합니다. 실제 결제는 이루어지지 않습니다.</p>
          </div>
        </div>
      )}

      {/* 현재 구독 상태 */}
      {subscription && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-500 uppercase mb-3">현재 구독</h2>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {PLAN_ICONS[currentPlan]}
              <div>
                <p className="font-bold text-gray-900">{subscription.plan_name}</p>
                <p className="text-sm text-gray-500">
                  최대 {subscription.max_endpoints}대 · {subscription.plan_price.toLocaleString()}원/월
                </p>
              </div>
            </div>
            <div className="text-right">
              {subscription.plan_expires_at ? (
                <div>
                  <p className="text-sm text-gray-500">만료일</p>
                  <p className="font-semibold text-gray-900">
                    {new Date(subscription.plan_expires_at).toLocaleDateString('ko-KR')}
                  </p>
                </div>
              ) : (
                <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
                  <CheckCircle className="w-3 h-3" />
                  체험 중
                </span>
              )}
            </div>
          </div>
          {subscription.plan !== 'basic' && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <button onClick={handleCancel} className="text-sm text-red-500 hover:text-red-700">
                구독 취소
              </button>
            </div>
          )}
        </div>
      )}

      {/* 플랜 선택 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {PLANS.map(plan => {
          const isCurrent = currentPlan === plan.id
          return (
            <div
              key={plan.id}
              className={`bg-white rounded-xl border-2 ${isCurrent ? 'border-blue-500 shadow-md' : plan.color} overflow-hidden`}
            >
              <div className={`${plan.headerColor} p-4`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {PLAN_ICONS[plan.id]}
                    <span className="font-bold text-gray-900">{plan.name}</span>
                  </div>
                  {plan.badge && (
                    <span className="px-2 py-0.5 bg-blue-600 text-white text-xs font-bold rounded-full">
                      {plan.badge}
                    </span>
                  )}
                  {isCurrent && (
                    <span className="px-2 py-0.5 bg-blue-600 text-white text-xs font-bold rounded-full">
                      현재 플랜
                    </span>
                  )}
                </div>
                <p className="text-2xl font-bold text-gray-900 mt-2">{plan.priceLabel}</p>
                <p className="text-sm text-gray-500">{plan.endpoints}</p>
              </div>
              <div className="p-4">
                <ul className="space-y-2 mb-4">
                  {plan.features.map(f => (
                    <li key={f} className="flex items-center gap-2 text-sm text-gray-600">
                      <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => handleUpgrade(plan.id, plan.price)}
                  disabled={isCurrent || upgrading === plan.id}
                  className={`w-full py-2 rounded-lg text-sm font-semibold transition-colors ${
                    isCurrent
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}
                >
                  {isCurrent ? '현재 플랜' : upgrading === plan.id ? '처리 중...' : '업그레이드'}
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* 결제 이력 */}
      {subscription && subscription.billing_history.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-500 uppercase mb-3">결제 이력</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 text-gray-500 font-medium">날짜</th>
                  <th className="text-left py-2 text-gray-500 font-medium">플랜</th>
                  <th className="text-right py-2 text-gray-500 font-medium">금액</th>
                  <th className="text-right py-2 text-gray-500 font-medium">상태</th>
                </tr>
              </thead>
              <tbody>
                {subscription.billing_history.map(h => (
                  <tr key={h.id} className="border-b border-gray-50">
                    <td className="py-2.5 text-gray-600">
                      {new Date(h.created_at).toLocaleDateString('ko-KR')}
                    </td>
                    <td className="py-2.5 text-gray-800 font-medium">{h.plan_name}</td>
                    <td className="py-2.5 text-right text-gray-800">
                      {h.amount.toLocaleString()}원
                    </td>
                    <td className="py-2.5 text-right">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                        h.status === 'paid' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {h.status === 'paid' ? '완료' : h.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 결제 확인 모달 */}
      {confirmModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <CreditCard className="w-6 h-6 text-blue-600" />
              <h3 className="text-lg font-bold text-gray-900">결제 확인</h3>
            </div>
            <p className="text-gray-600 mb-2">
              <span className="font-semibold">{PLANS.find(p => p.id === confirmModal.plan)?.name}</span> 플랜으로
              업그레이드합니다.
            </p>
            <p className="text-2xl font-bold text-gray-900 mb-4">
              {confirmModal.price.toLocaleString()}원<span className="text-sm text-gray-500">/월</span>
            </p>
            {subscription?.test_mode && (
              <p className="text-xs text-yellow-600 bg-yellow-50 rounded-lg p-2 mb-4">
                ⚠️ 테스트 모드: 실제 결제 없이 플랜이 변경됩니다.
              </p>
            )}
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmModal(null)}
                className="flex-1 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50"
              >
                취소
              </button>
              <button
                onClick={handleConfirmPayment}
                className="flex-1 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700"
              >
                결제하기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
