import { post, get, put } from './api'

// 刷新token
export const refreshToken = (refresh_token) => {
  // 刷新失败由 api.js 的统一认证流程处理，不能再次触发自身的 401 刷新和通用 toast。
  return post('/auth/refresh', { refresh_token }, {
    skipAuthRefresh: true,
    skipErrorToast: true,
  })
}

// 获取当前用户信息
export const getCurrentUser = () => {
  // 初始化阶段由 user store 负责清理认证态和跳转，避免与全局拦截器重复提示。
  return get('/users/profile', {}, { skipErrorToast: true })
}

// 更新用户信息
export const updateProfile = (userData) => {
  return put('/users/profile', userData)
}

// 修改密码
export const changePassword = (passwordData) => {
  return post('/users/change-password', passwordData)
}

// 发送短信验证码
export const sendSmsCode = (phone) => {
  return post('/auth/send-sms-code', { phone })
}

// 手机验证码登录；手机号不存在时后端会自动注册
export const loginByPhone = (phone, code) => {
  return post('/auth/login-by-phone', { phone, code })
}

// 上传头像
export const uploadAvatar = (formData) => {
  return post('/users/upload-avatar', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}
