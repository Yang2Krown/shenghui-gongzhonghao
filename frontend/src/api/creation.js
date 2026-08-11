import { get, post, put, patch, del } from './api'

// 获取创作列表
export const getCreations = (params = {}) => {
  return get('/creations', params)
}

// 获取创作详情
export const getCreationById = (id) => {
  return get(`/creations/${id}`)
}

// 获取草稿调整弹窗中的当前内容和历史生成版本
export const getCreationAdjustmentOptions = (id) => {
  return get(`/creations/${id}/adjustment-options`)
}

// 创建创作
export const createCreation = (creationData) => {
  return post('/creations', creationData)
}

// 更新创作
export const updateCreation = (id, creationData) => {
  return put(`/creations/${id}`, creationData)
}

// 公众号草稿箱上传成功后回写本地创作状态
export const markCreationPublished = (id, platform = 'wechat_draft', metadata = {}) => {
  return post(`/creations/${id}/mark-published`, { platform, ...metadata })
}

// 删除创作
export const deleteCreation = (id) => {
  return del(`/creations/${id}`)
}

// AI生成内容
export const generateContent = (params) => {
  return post('/ai/generate', params)
}

// AI优化内容
export const optimizeContent = (params) => {
  return post('/ai/optimize', params)
}

// 从选题候选创建创作
export const createCreationFromCandidate = (candidateId, clusterId) => {
  return post('/creations/from-candidate', { candidate_id: candidateId, cluster_id: clusterId })
}

// 获取创作统计
export const getCreationStats = () => {
  return get('/creations/stats')
}

// 导出创作
export const exportCreation = (id, format = 'markdown') => {
  return get(`/creations/${id}/export`, { format }, { responseType: 'blob' })
}

// ── 标题候选编辑 ──

// 保存编辑后的标题候选
export const updateTitleCandidate = (candidateId, data) => {
  return patch(`/title-generation/candidates/${candidateId}`, data)
}

// 保存编辑后的推荐标题
export const updateTitleRecommendation = (recommendationId, data) => {
  return patch(`/title-generation/recommendations/${recommendationId}`, data)
}

// 重新评估标题候选（只跑 B+C）
export const reevaluateTitleCandidate = (candidateId) => {
  return post(`/title-generation/candidates/${candidateId}/reevaluate`)
}

// ── 正文重新评估 ──

// 重新评估正文（只跑 Agent D）
export const reevaluateContent = (data) => {
  return post('/content-generation/reevaluate', data)
}
