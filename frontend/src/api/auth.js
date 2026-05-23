import { post, get, put } from './api'

// 登录
export const login = (credentials) => {
  // 后端使用username字段，但支持邮箱登录
  const loginData = {
    username: credentials.email,
    password: credentials.password
  }
  return post('/auth/login', loginData)
}

// 注册
export const register = (userData) => {
  return post('/auth/register', userData)
}

// 刷新token
export const refreshToken = (refresh_token) => {
  return post('/auth/refresh', { refresh_token })
}

// 获取当前用户信息
export const getCurrentUser = () => {
  return get('/users/profile')
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

// 手机验证码登录
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