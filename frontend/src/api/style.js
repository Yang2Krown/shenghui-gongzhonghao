import { get, post, put, del } from './api'

// 获取风格列表
export const getStyles = (params = {}) => {
  return get('/styles', params)
}

// 获取风格详情
export const getStyleById = (id) => {
  return get(`/styles/${id}`)
}

// 创建风格
export const createStyle = (styleData) => {
  return post('/styles', styleData)
}

// 更新风格
export const updateStyle = (id, styleData) => {
  return put(`/styles/${id}`, styleData)
}

// 删除风格
export const deleteStyle = (id) => {
  return del(`/styles/${id}`)
}

// 分析文章风格
export const analyzeArticleStyle = (articleData) => {
  return post('/styles/analyze', articleData)
}

// 获取风格建议
export const getStyleSuggestions = (params = {}) => {
  return get('/styles/suggestions', params)
}

// 应用风格到内容
export const applyStyleToContent = (params) => {
  return post('/styles/apply', params)
}