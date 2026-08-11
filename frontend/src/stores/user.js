import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { refreshToken as refreshTokenApi, getCurrentUser } from '@/api/auth'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { isTerminalAuthError } from '@/utils/authSession'

export const useUserStore = defineStore('user', () => {
  // 状态
  const user = ref(null)
  const TOKEN_MAX_AGE = 7 * 24 * 60 * 60 * 1000 // 7天
  const ACCESS_TOKEN_REFRESH_WINDOW = 5 * 60 * 1000 // access token 到期前 5 分钟主动恢复

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

  const accessTokenNeedsRefresh = () => {
    if (!token.value) return false

    try {
      const payload = token.value.split('.')[1]
      if (!payload) return true
      const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
      const decoded = JSON.parse(atob(normalized))
      const expiresAt = Number(decoded.exp) * 1000
      return !Number.isFinite(expiresAt) || expiresAt - Date.now() <= ACCESS_TOKEN_REFRESH_WINDOW
    } catch {
      // 解析失败交给后端验证，避免把仍可用的会话误清掉。
      return false
    }
  }

  const token = ref(isTokenExpired() ? '' : (localStorage.getItem('token') || ''))
  const refreshToken = ref(isTokenExpired() ? '' : (localStorage.getItem('refreshToken') || ''))
  const loading = ref(false)
  const initialized = ref(false)
  let initializePromise = null

  // 计算属性
  const isAuthenticated = computed(() => !!token.value)
  const userName = computed(() => user.value?.full_name || user.value?.username || '未登录用户')
  const userAvatar = computed(() => user.value?.avatar_url || '')
  const adminRoles = ['admin']
  const isAdmin = computed(() => adminRoles.includes(user.value?.role) || !!user.value?.is_superuser)
  const employeeRoles = ['admin', 'employee']
  const isEmployee = computed(() => employeeRoles.includes(user.value?.role) || !!user.value?.is_superuser)
  const isSuperAdmin = computed(() => !!user.value?.is_superuser)
  const productAccess = computed(() => user.value?.product_access || [])
  const isMember = computed(() => productAccess.value.length > 0 || !!user.value?.is_member)
  const hasProduct = (product) => isEmployee.value || productAccess.value.includes(product)
  const isTeamMember = computed(() => isEmployee.value)

  // 初始化 - 从本地存储恢复token
  const initialize = async () => {
    if (initialized.value) return
    if (initializePromise) return initializePromise

    initializePromise = (async () => {
      try {
        if (isTokenExpired()) {
          clearAuth()
          return
        }
        if (token.value && !user.value) {
          try {
            await fetchUser()
          } catch (error) {
            // 只有明确的认证终态失败才清理登录态；服务端暂时异常时保留 token，
            // 避免用户被误退出并再次触发登录过期提示。
            if (isTerminalAuthError(error)) {
              clearAuth()
            }
          }
        }
      } finally {
        initialized.value = true
      }
    })()

    try {
      return await initializePromise
    } finally {
      initializePromise = null
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

  // 浏览器从休眠/后台恢复时主动确认会话，避免等到用户点击功能后才暴露旧 token。
  const recoverSession = async ({ force = true } = {}) => {
    if (!token.value) return false
    if (isTokenExpired()) {
      clearAuth()
      if (router.currentRoute.value.name !== 'Landing') {
        router.push({ name: 'Landing' })
      }
      return false
    }
    if (!force && user.value && !accessTokenNeedsRefresh()) return true

    try {
      await fetchUser()
      return true
    } catch (error) {
      if (isTerminalAuthError(error)) clearAuth()
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
      // 只有刷新令牌/用户明确失效时才清理认证态；服务端/网络故障应允许稍后重试。
      if (isTerminalAuthError(error)) {
        clearAuth()
      }
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
    isEmployee,
    isSuperAdmin,
    isMember,
    productAccess,
    hasProduct,
    isTeamMember,
    
    // 方法
    initialize,
    fetchUser,
    recoverSession,
    refresh,
    logout,
    clearAuth,
    updateUser
  }
})
