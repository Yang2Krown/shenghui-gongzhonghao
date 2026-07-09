import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { refreshToken as refreshTokenApi, getCurrentUser } from '@/api/auth'
import { ElMessage } from 'element-plus'
import router from '@/router'

export const useUserStore = defineStore('user', () => {
  // 状态
  const user = ref(null)
  const TOKEN_MAX_AGE = 7 * 24 * 60 * 60 * 1000 // 7天

  const isTokenExpired = () => {
    const hasToken = localStorage.getItem('token')
    if (!hasToken) return true
    const savedAt = localStorage.getItem('tokenSavedAt')
    if (!savedAt) {
      // 兼容旧登录：有 token 但没记录时间，补记当前时间
      localStorage.setItem('tokenSavedAt', String(Date.now()))
      return false
    }
    return Date.now() - Number(savedAt) > TOKEN_MAX_AGE
  }

  const token = ref(isTokenExpired() ? '' : (localStorage.getItem('token') || ''))
  const refreshToken = ref(isTokenExpired() ? '' : (localStorage.getItem('refreshToken') || ''))
  const loading = ref(false)
  const initialized = ref(false)

  // 计算属性
  const isAuthenticated = computed(() => !!token.value)
  const userName = computed(() => user.value?.full_name || user.value?.username || '未登录用户')
  const userAvatar = computed(() => user.value?.avatar_url || '')
  const adminRoles = ['admin']
  const isAdmin = computed(() => adminRoles.includes(user.value?.role) || !!user.value?.is_superuser)
  const isSuperAdmin = computed(() => !!user.value?.is_superuser)
  const productAccess = computed(() => user.value?.product_access || [])
  const isMember = computed(() => productAccess.value.length > 0 || !!user.value?.is_member)
  const hasProduct = (product) => isAdmin.value || productAccess.value.includes(product)

  // 初始化 - 从本地存储恢复token
  const initialize = async () => {
    try {
      if (isTokenExpired()) {
        clearAuth()
        return
      }
      if (token.value && !user.value) {
        try {
          await fetchUser()
        } catch (error) {
          clearAuth()
        }
      }
    } finally {
      initialized.value = true
    }
  }

  // 获取用户信息
  const fetchUser = async () => {
    try {
      const response = await getCurrentUser()
      user.value = response.data
      return response.data
    } catch (error) {
      throw error
    }
  }

  // 刷新token
  const refresh = async () => {
    if (!refreshToken.value) {
      throw new Error('No refresh token')
    }
    
    try {
      const response = await refreshTokenApi(refreshToken.value)
      const { access_token, refresh_token } = response.data
      
      token.value = access_token
      refreshToken.value = refresh_token
      localStorage.setItem('token', access_token)
      localStorage.setItem('refreshToken', refresh_token)
      localStorage.setItem('tokenSavedAt', String(Date.now()))
      
      return access_token
    } catch (error) {
      clearAuth()
      throw error
    }
  }

  // 退出登录
  const logout = () => {
    clearAuth()
    ElMessage.success('已退出登录')
    router.push('/landing')
  }

  // 清除认证信息
  const clearAuth = () => {
    user.value = null
    token.value = ''
    refreshToken.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('tokenSavedAt')
  }

  // 更新用户信息
  const updateUser = (userData) => {
    if (user.value) {
      user.value = { ...user.value, ...userData }
    }
  }

  return {
    // 状态
    user,
    token,
    refreshToken,
    loading,
    initialized,
    
    // 计算属性
    isAuthenticated,
    userName,
    userAvatar,
    isAdmin,
    isSuperAdmin,
    isMember,
    productAccess,
    hasProduct,
    
    // 方法
    initialize,
    fetchUser,
    refresh,
    logout,
    clearAuth,
    updateUser
  }
})
