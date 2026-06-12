import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCreditBalance, getCreditPackages, purchaseCredits } from '@/api/credit'
import { ElMessage } from 'element-plus'

// 默认套餐数据
const DEFAULT_PACKAGES = [
  { name: '体验包', credits: 100, price_yuan: 9.9, original_price_yuan: null, description: '适合轻度使用', badge: null },
  { name: '标准包', credits: 500, price_yuan: 39, original_price_yuan: 49.5, description: '最受欢迎', badge: '推荐' },
  { name: '专业包', credits: 1200, price_yuan: 79, original_price_yuan: 118.8, description: '专业运营首选', badge: '超值' },
  { name: '团队包', credits: 3000, price_yuan: 169, original_price_yuan: 297, description: '团队批量采购', badge: null },
]

export const useCreditStore = defineStore('credit', () => {
  const balance = ref(0)
  const packages = ref(DEFAULT_PACKAGES)
  const loading = ref(false)

  const formattedBalance = computed(() => balance.value.toLocaleString())
  const balanceYuan = computed(() => (balance.value * 0.1).toFixed(2))

  const fetchBalance = async () => {
    try {
      const res = await getCreditBalance()
      const data = res.data || res
      balance.value = data.balance || 0
    } catch (error) {
      console.error('获取积分余额失败:', error)
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
      balance.value = data.balance || balance.value
      ElMessage.success(`购买成功，获得 ${data.credits_added} 积分`)
      return true
    } catch (error) {
      ElMessage.error('购买失败')
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    balance,
    packages,
    loading,
    formattedBalance,
    balanceYuan,
    fetchBalance,
    fetchPackages,
    purchase,
  }
})