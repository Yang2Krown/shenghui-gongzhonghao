import { del, get, post, put } from './api'

export const listArticleReviews = (params = {}) => get('/reviews', params)

export const getArticleReview = (id) => get(`/reviews/${id}`)

export const getArticleReviewSummary = (id, config = {}) => get(`/reviews/${id}/summary`, {}, config)

export const getArticleReviewSemanticBlocks = (id, config = {}) => get(`/reviews/${id}/semantic-blocks`, {}, config)

export const listArticleReviewChanges = (id, params = {}, config = {}) => get(`/reviews/${id}/changes`, params, config)

export const listArticleReviewComments = (id, config = {}) => get(`/reviews/${id}/comments`, {}, config)

export const getArticleReviewSourceText = (id, config = {}) => get(`/reviews/${id}/source-text`, {}, config)

export const deleteArticleReview = (id) => del(`/reviews/${id}`)

export const getArticleReviewWorkflow = (id, params = {}) => get(`/reviews/${id}/workflow`, params)

export const createArticleReview = (beforeFile, afterFile, title = '') => {
  const formData = new FormData()
  formData.append('before_file', beforeFile)
  formData.append('after_file', afterFile)
  if (title.trim()) formData.append('title', title.trim())
  return post('/reviews', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    // 这里只负责接收文件并投递后台任务，正常应在几十秒内返回；不让前端为后台解析任务长连接。
    timeout: 300000,
  })
}

/**
 * 读取文章复盘的 SSE 进度流。
 * 原生 EventSource 无法携带 Bearer token，因此用 fetch 解析 SSE 帧。
 */
export const streamArticleReview = async (id, onProgress, { signal, lastEventId } = {}) => {
  // 延迟加载用户 store，避免仅使用普通 API 的单元测试在 Node 环境初始化浏览器路由。
  const { useUserStore } = await import('@/stores/user')
  const userStore = useUserStore()
  const headers = { Accept: 'text/event-stream' }
  if (userStore.token) headers.Authorization = `Bearer ${userStore.token}`
  if (lastEventId) headers['Last-Event-ID'] = String(lastEventId)
  const response = await fetch(`/api/v1/reviews/${id}/stream`, { headers, signal })
  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new Error(detail || `进度流连接失败（${response.status}）`)
  }
  if (!response.body) throw new Error('浏览器不支持文章复盘进度流')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let latestEventId = lastEventId || 0
  const consume = (chunk) => {
    buffer += chunk
    const frames = buffer.split('\n\n')
    buffer = frames.pop() || ''
    for (const frame of frames) {
      const idLine = frame.split('\n').find((line) => line.startsWith('id:'))
      if (idLine) latestEventId = Number(idLine.slice(3).trim()) || latestEventId
      const dataLine = frame.split('\n').find((line) => line.startsWith('data:'))
      if (!dataLine) continue
      try {
        onProgress?.(JSON.parse(dataLine.slice(5).trim()), latestEventId)
      } catch {
        // 单个异常帧不打断后续进度。
      }
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    consume(decoder.decode(value, { stream: true }))
  }
  consume(decoder.decode())
  return { lastEventId: latestEventId }
}

export const addArticleReviewComment = (id, data) => post(`/reviews/${id}/comments`, data)

export const updateArticleReviewComment = (id, commentId, data) => put(`/reviews/${id}/comments/${commentId}`, data)

export const updateArticleReviewAnalysis = (id, data) => put(`/reviews/${id}/analysis`, data)

export const analyzeArticleReview = (id) => post(`/reviews/${id}/analyze`)

export const updateArticleReviewSemanticBlocks = (id, data) => put(`/reviews/${id}/semantic-blocks`, data)

export const reviewArticleReviewChange = (id, changeId, data) => put(`/reviews/${id}/changes/${changeId}/review`, data)

export const retryArticleReviewStage = (id, stageKey) => post(`/reviews/${id}/stages/${stageKey}/retry`)

export const confirmArticleReviewMethodology = (id, candidateId, data) => post(`/reviews/${id}/methodology/${candidateId}/confirm`, data)

export const promoteArticleReview = (id, data) => post(`/reviews/${id}/promote`, data)
