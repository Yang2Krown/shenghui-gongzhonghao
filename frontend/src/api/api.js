import axios from 'axios'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import router from '@/router'

// 创建axios实例
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const userStore = useUserStore()
    
    // 添加token到请求头
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && typeof body === 'object' && 'code' in body && 'data' in body) {
      response.data = body.data
    }
    return response
  },
  async (error) => {
    const originalRequest = error.config
    const userStore = useUserStore()
    
    // 如果是401错误且没有重试过
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      
      try {
        // 尝试刷新token
        const newToken = await userStore.refresh()
        
        // 更新请求头
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        
        // 重试原请求
        return api(originalRequest)
      } catch (refreshError) {
        // 刷新失败，跳转到登录页
        userStore.clearAuth()
        router.push('/login')
        ElMessage.error('登录已过期，请重新登录')
        return Promise.reject(refreshError)
      }
    }
    
    // 处理其他错误
    const message = error.response?.data?.detail || error.message || '请求失败'
    
    if (error.response?.status === 403) {
      ElMessage.error('没有权限访问')
    } else if (error.response?.status === 404) {
      ElMessage.error('请求的资源不存在')
    } else if (error.response?.status === 500) {
      ElMessage.error('服务器内部错误')
    } else {
      ElMessage.error(message)
    }
    
    return Promise.reject(error)
  }
)

// 通用API方法
// 第三个参数 config 可覆盖实例默认配置（如 timeout），用于耗时较长的接口
export const get = (url, params = {}, config = {}) => api.get(url, { params, ...config })
export const post = (url, data = {}, config = {}) => api.post(url, data, config)
export const put = (url, data = {}, config = {}) => api.put(url, data, config)
export const patch = (url, data = {}, config = {}) => api.patch(url, data, config)
export const del = (url, config = {}) => api.delete(url, config)

/**
 * 上传文件并提取文本内容
 * @param {File} file - 要上传的文件
 * @returns {Promise<{filename: string, text: string, char_count: number}>}
 */
export const uploadFile = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/creation-tools/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

/**
 * 提取链接内容（公众号/小红书/抖音等）
 * @param {string} url - 链接地址
 * @returns {Promise<{title: string, content: string, author: string, platform: string}>}
 */
export const extractLinkContent = (url) => {
  return api.post('/creation-tools/extract-link', { url }, { timeout: 30000 })
}

/**
 * 内容转写 - 将内容从一个平台转写成另一个平台的风格
 * @param {Object} params - 转写参数
 * @param {string} params.content - 原文内容
 * @param {string} params.source_platform - 源平台 (wechat/xhs/douyin/zhihu)
 * @param {string} params.target_platform - 目标平台 (wechat/xhs)
 * @param {string} [params.original_title] - 原文章标题
 * @param {string} [params.extra_requirements] - 额外要求
 * @returns {Promise<{title: string, content: string, tags: string[]}>}
 */
export const transformContent = (params) => {
  return api.post('/content-transform/transform', params, { timeout: 60000 })
}

/**
 * 内容仿写 - 学习参考内容的风格，创作原创内容
 * @param {Object} params - 仿写参数
 * @param {string} params.content - 参考内容
 * @param {string} [params.title] - 参考内容标题
 * @param {string} [params.extra_requirements] - 额外要求
 * @returns {Promise<{title: string, content: string, tags: string[]}>}
 */
export const imitateContent = (params) => {
  return api.post('/content-imitate/imitate', params, { timeout: 60000 })
}

export default api