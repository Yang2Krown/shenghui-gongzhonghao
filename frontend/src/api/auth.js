import { post, get, put } from './api'

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
