import axios from 'axios'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { isTerminalAuthError } from '@/utils/authSession'

// 创建axios实例
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 所有并发请求共用同一次刷新，避免登录过期时每个请求都单独刷新并重复弹窗。
let refreshPromise = null
let authExpiryNotified = false

const isRefreshRequest = (config) => {
  if (!config) return false
  // skipAuthRefresh 是显式标记；url 判断用于保护遗漏标记的刷新请求。
  return config.skipAuthRefresh === true || String(config.url || '').includes('/auth/refresh')
}

const notifyAuthExpired = (userStore) => {
  if (authExpiryNotified) return
  authExpiryNotified = true

  userStore.clearAuth()
  if (router.currentRoute.value.name !== 'Landing') {
    router.push({ name: 'Landing' })
  }
  ElMessage.error('登录已过期，请重新登录')
}

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
    // 用户重新登录后允许下一次真正的认证过期再次提示。
    if (String(response.config?.url || '').includes('/auth/login')) {
      authExpiryNotified = false
    }
    const body = response.data
    if (body && typeof body === 'object' && 'code' in body && 'data' in body) {
      response.data = body.data
    }
    return response
  },
  async (error) => {
    const originalRequest = error.config
    const userStore = useUserStore()
    const skipErrorToast = originalRequest?.skipErrorToast === true
    const refreshRequest = isRefreshRequest(originalRequest)

    // 主动取消的请求（AbortController / 页面切换时打断重复请求）不是错误，
    // 静默放行，避免弹出 axios 默认的 "canceled" 提示。
    if (error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError') {
      return Promise.reject(error)
    }

    // 刷新接口本身失败时不能再次进入刷新流程，否则会递归请求并产生第二个错误提示。
    if (refreshRequest) {
      return Promise.reject(error)
    }

    // 如果是401错误且没有重试过
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true
      
      try {
        // 尝试刷新 token。并发请求只发起一个刷新请求，其余请求等待同一个结果。
        if (!refreshPromise) {
          refreshPromise = userStore.refresh().finally(() => {
            refreshPromise = null
          })
        }
        const newToken = await refreshPromise
        authExpiryNotified = false
        
        // 更新请求头
        originalRequest.headers = originalRequest.headers || {}
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        
        // 重试原请求
        return api(originalRequest)
      } catch (refreshError) {
        // 刷新 token 或关联用户返回终态 4xx 才判定为登录过期；Redis/网络等
        // 服务端故障不清空登录态，也不再让刷新请求额外弹出“服务器内部错误”。
        const missingRefreshToken = refreshError.message === 'No refresh token'
        if (isTerminalAuthError(refreshError) || missingRefreshToken) {
          notifyAuthExpired(userStore)
        } else if (refreshError.response?.status >= 500) {
          ElMessage.error('登录状态暂时无法验证，请稍后重试')
        }
        return Promise.reject(refreshError)
      }
    }
    
    // 后台轮询等场景由调用方自行处理错误，避免每次短暂网络抖动都弹 toast。
    if (skipErrorToast) {
      return Promise.reject(error)
    }

    // 处理其他错误
    const status = error.response?.status
    const detail = error.response?.data?.detail
    const message = (typeof detail === 'string' ? detail : detail?.message) || error.message || '请求失败'

    if (status === 413) {
      ElMessage.error('文件太大，请压缩后重试（建议不超过 2MB）')
    } else if (status === 402) {
      // 积分不足 - 触发全局事件显示充值弹窗
      const creditInfo = typeof detail === 'object' ? detail : {}
      window.dispatchEvent(new CustomEvent('insufficient-credits', {
        detail: {
          balance: creditInfo.balance || 0,
          required: creditInfo.required || 0,
          operation: creditInfo.operation || '',
          operationDesc: creditInfo.operation_desc || '',
        }
      }))
    } else if (status === 403) {
      const reason = error.response?.data?.data?.reason
      if (reason === 'membership_required' || reason === 'product_required') {
        const product = error.response?.data?.data?.product
        ElMessage.warning(error.response?.data?.message || '请先开通对应产品后再使用系统')
        router.push({ name: 'Landing', query: { show: 'membership', product } })
      } else {
        ElMessage.error('没有权限访问')
      }
    } else if (status === 404) {
      ElMessage.error('请求的资源不存在')
    } else if (status === 500 || status === 502 || status === 503) {
      // 页面调用方通常会根据业务场景给出具体文案。5xx 只透传，避免全局提示
      // 与页面 catch 中的提示叠加成两条消息。
      return Promise.reject(error)
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
  // 60s:对齐后端小红书排队+慢抓取、抖音串行策略的最坏耗时,避免慢链接被误判"提取失败"
  return api.post('/creation-tools/extract-link', { url }, { timeout: 60000 })
}

/**
 * 提取公众号文章图文预览（包括图片）
 * @param {string} url - 公众号文章链接
 * @returns {Promise<{title: string, author: string, blocks: Array, tags: string[], image_count: number, text_content: string}>}
 */
export const extractLinkPreview = (url) => {
  return api.post('/wechat-to-xhs/extract-link-preview', { url }, { timeout: 60000 })
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

// ==================== 微信公众号草稿箱 API ====================

/**
 * 上传图片到 OSS
 * @param {File} file - 图片文件
 * @returns {Promise<{url: string, filename: string, size: number}>}
 */
export const uploadImage = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/images/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

/**
 * 发布文章到微信公众号草稿箱
 * @param {Object} params - 发布参数
 * @param {string} params.title - 文章标题
 * @param {string} params.content - 文章正文 HTML
 * @param {string} [params.author] - 作者
 * @param {string} [params.digest] - 摘要
 * @param {string} params.appid - 公众号 AppID
 * @param {string} params.app_secret - 公众号 AppSecret
 * @param {string} [params.cover_image_url] - 封面图 URL
 * @param {string} [params.cover_image_base64] - 封面图 Base64
 * @returns {Promise<{success: boolean, media_id: string, message: string}>}
 */
export const createWechatDraft = (params) => {
  return api.post('/wechat-draft/create-draft', params, { timeout: 60000 })
}

/**
 * 测试公众号连接
 * @param {string} appid - 公众号 AppID
 * @param {string} appSecret - 公众号 AppSecret
 * @returns {Promise<{success: boolean, message: string}>}
 */
export const testWechatConnection = (appid, appSecret) => {
  return api.post('/wechat-draft/test-connection', null, { params: { appid, app_secret: appSecret }, timeout: 15000 })
}

/**
 * AI 生成封面图
 * @param {string} title - 文章标题
 * @param {string} [style] - 风格描述
 * @returns {Promise<{url: string}>}
 */
export const generateWechatCover = (title, content, style) => {
  return api.post('/wechat-draft/generate-cover', { title, content, style }, { timeout: 120000 })
}

/**
 * 获取 Bing 每日一图列表（最近 n 张，横屏）
 * @param {number} [n=15] - 数量，最多 15
 * @returns {Promise<{images: Array<{url: string, title: string, date: string}>}>}
 */
export const getBingImages = (n = 15) => {
  return api.get('/wechat-draft/bing-images', { params: { n }, timeout: 20000 })
}

// ==================== 小红书发布相关 API ====================

/**
 * 检查小红书登录状态
 * @returns {Promise<{logged_in: boolean}>}
 */
export const checkXhsLogin = () => {
  return api.post('/xhs-publish/check-login', {}, { timeout: 30000 })
}

/**
 * 打开小红书登录页面
 * @param {string} [account] - 账号名称
 * @returns {Promise<{status: string}>}
 */
export const openXhsLoginPage = (account) => {
  return api.get('/xhs-publish/login', { params: { account } }, { timeout: 30000 })
}

/**
 * 启动小红书长文发布流程
 * @param {Object} params - 发布参数
 * @param {string} params.title - 文章标题
 * @param {string} params.content - 文章正文
 * @param {string} [params.account] - 账号名称
 * @returns {Promise<{status: string, templates: Array}>}
 */
export const startXhsLongArticle = (params) => {
  return api.post('/xhs-publish/start-long-article', params, { timeout: 60000 })
}

/**
 * 选择小红书排版模板
 * @param {string} name - 模板名称
 * @returns {Promise<{status: string, name: string}>}
 */
export const selectXhsTemplate = (name) => {
  return api.post('/xhs-publish/select-template', { name }, { timeout: 30000 })
}

/**
 * 点击下一步并填写发布页描述
 * @param {string} content - 发布页正文描述
 * @returns {Promise<{status: string}>}
 */
export const clickXhsNextStep = (content) => {
  return api.post('/xhs-publish/click-next-step', { content }, { timeout: 30000 })
}

/**
 * 点击发布按钮
 * @returns {Promise<{status: string}>}
 */
export const clickXhsPublish = () => {
  return api.post('/xhs-publish/click-publish', {}, { timeout: 30000 })
}

/**
 * 智能换行：LLM 对正文做段落拆分，保证内容不变
 * @param {string} content - 纯文本/markdown 正文
 * @returns {Promise<{content: string}>}
 */
export const formatParagraphs = (content) => {
  return api.post('/creation-tools/format-paragraphs', { content }, { timeout: 120000 })
}

export default api
