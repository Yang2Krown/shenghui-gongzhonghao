import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCreditBalance, getCreditAccount, getCreditPackages, purchaseCredits } from '@/api/credit'
import { ElMessage } from 'element-plus'

// 默认套餐数据
const DEFAULT_PACKAGES = [
  { name: '300 元充值', credits: 3000, base_credits: 3000, bonus_credits: 0, bonus_rate: 0, price_yuan: 300, original_price_yuan: null, description: '基础兑换，1 元 = 10 积分', badge: null },
  { name: '500 元充值', credits: 5250, base_credits: 5000, bonus_credits: 250, bonus_rate: 5, price_yuan: 500, original_price_yuan: null, description: '多充多送，额外赠送 250 积分', badge: '推荐' },
  { name: '1000 元充值', credits: 11000, base_credits: 10000, bonus_credits: 1000, bonus_rate: 10, price_yuan: 1000, original_price_yuan: null, description: '高效创作，额外赠送 1000 积分', badge: '超值' },
  { name: '2000 元充值', credits: 24000, base_credits: 20000, bonus_credits: 4000, bonus_rate: 20, price_yuan: 2000, original_price_yuan: null, description: '最高赠送，额外赠送 4000 积分', badge: '最高省 ¥400' },
]

export const useCreditStore = defineStore('credit', () => {
  const balance = ref(0)
  const packages = ref(DEFAULT_PACKAGES)
  const loading = ref(false)

  // 订阅到期信息
  const subscriptionExpiresAt = ref(null)
  const daysUntilExpire = ref(null)
  const isSubscriptionActive = ref(false)
  const subscriptionAccess = ref(null)

  const formattedBalance = computed(() => balance.value.toLocaleString())
  const balanceYuan = computed(() => (balance.value / 10).toFixed(2))

  const expireDateText = computed(() => {
    if (!subscriptionExpiresAt.value) return ''
    const d = new Date(subscriptionExpiresAt.value)
    if (Number.isNaN(d.getTime())) return ''
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    return `${d.getFullYear()}-${mm}-${dd}`
  })

  const fetchBalance = async () => {
    try {
      const res = await getCreditBalance()
      const data = res.data || res
      balance.value = data.balance || 0
    } catch (error) {
      console.error('获取积分余额失败:', error)
    }
  }

  const fetchAccount = async () => {
    try {
      const res = await getCreditAccount()
      const data = res.data || res
      balance.value = data.balance ?? balance.value
      subscriptionExpiresAt.value = data.subscription_expires_at || null
      daysUntilExpire.value = data.days_until_expire ?? null
      isSubscriptionActive.value = !!data.is_subscription_active
      subscriptionAccess.value = data.subscription_access || null
    } catch (error) {
      console.error('获取积分账户详情失败:', error)
    }
  }

  const fetchPackages = async () => {
    try {
      const res = await getCreditPackages()
      const data = res.data || res
      const list = data.packages || data
      if (Array.isArray(list) && list.length > 0) {
        packages.value = list
      }
    } catch (error) {
      console.error('获取积分套餐失败，使用默认数据:', error)
    }
    return packages.value
  }

  const purchase = async (packageName) => {
    loading.value = true
    try {
      const res = await purchaseCredits(packageName)
      const data = res.data || res
      return data
    } catch (error) {
      const detail = error?.response?.data?.detail || error?.message || '创建支付订单失败'
      ElMessage.error(detail)
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    balance,
    packages,
    loading,
    subscriptionExpiresAt,
    daysUntilExpire,
    isSubscriptionActive,
    subscriptionAccess,
    formattedBalance,
    balanceYuan,
    expireDateText,
    fetchBalance,
    fetchAccount,
    fetchPackages,
    purchase,
  }
})
