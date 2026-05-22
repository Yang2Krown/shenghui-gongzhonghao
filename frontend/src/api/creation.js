import { get, post, put, del } from './api'

// 获取创作列表
export const getCreations = (params = {}) => {
  return get('/creations', params)
}

// 获取创作详情
export const getCreationById = (id) => {
  return get(`/creations/${id}`)
}

// 创建创作
export const createCreation = (creationData) => {
  return post('/creations', creationData)
}

// 更新创作
export const updateCreation = (id, creationData) => {
  return put(`/creations/${id}`, creationData)
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

// 获取创作统计
export const getCreationStats = () => {
  return get('/creations/stats')
}

// 导出创作
export const exportCreation = (id, format = 'markdown') => {
  return get(`/creations/${id}/export`, { format }, { responseType: 'blob' })
}