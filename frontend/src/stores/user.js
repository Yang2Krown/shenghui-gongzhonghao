import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, refreshToken as refreshTokenApi, getCurrentUser } from '@/api/auth'
import { ElMessage } from 'element-plus'

export const useUserStore = defineStore('user', () => {
  // 状态
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  const refreshToken = ref(localStorage.getItem('refreshToken') || '')
  const loading = ref(false)

  // 计算属性
  const isAuthenticated = computed(() => !!token.value)
  const userName = computed(() => user.value?.name || user.value?.username || '未登录用户')
  const userAvatar = computed(() => user.value?.avatar || '')

  // 初始化 - 从本地存储恢复token
  const initialize = async () => {
    if (token.value) {
      try {
        await fetchUser()
      } catch (error) {
        // Token无效，清除
        clearAuth()
      }
    }
  }

  // 登录
  const login = async (credentials) => {
    loading.value = true
    try {
      const response = await loginApi(credentials)
      const { access_token, refresh_token } = response.data
      
      // 保存token
      token.value = access_token
      refreshToken.value = refresh_token
      localStorage.setItem('token', access_token)
      localStorage.setItem('refreshToken', refresh_token)
      
      // 获取用户信息
      await fetchUser()
      
      ElMessage.success('登录成功')
      return true
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '登录失败')
      throw error
    } finally {
      loading.value = false
    }
  }

  // 注册
  const register = async (userData) => {
    loading.value = true
    try {
      const response = await registerApi(userData)
      const { access_token, refresh_token } = response.data
      
      // 保存token
      token.value = access_token
      refreshToken.value = refresh_token
      localStorage.setItem('token', access_token)
      localStorage.setItem('refreshToken', refresh_token)
      
      // 获取用户信息
      await fetchUser()
      
      ElMessage.success('注册成功')
      return true
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '注册失败')
      throw error
    } finally {
      loading.value = false
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
  }

  // 清除认证信息
  const clearAuth = () => {
    user.value = null
    token.value = ''
    refreshToken.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
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
    
    // 计算属性
    isAuthenticated,
    userName,
    userAvatar,
    
    // 方法
    initialize,
    login,
    register,
    fetchUser,
    refresh,
    logout,
    clearAuth,
    updateUser
  }
})