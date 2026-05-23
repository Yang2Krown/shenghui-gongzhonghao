import { get, post, put, del } from './api'

// 获取风格档案（含素材列表）
export const getStyleProfile = () => {
  return get('/styles/profile')
}

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

// 添加训练素材（文字/链接）
export const addStyleSource = (payload) => {
  return post('/styles/sources', payload, {
    timeout: 60000,  // 链接提取可能需要较长时间
  })
}

// 上传文件素材
export const uploadStyleSourceFile = (file, title = '') => {
  const formData = new FormData()
  formData.append('file', file)
  if (title) formData.append('title', title)
  return post('/styles/sources/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

// 删除训练素材
export const deleteStyleSource = (id) => {
  return del(`/styles/sources/${id}`)
}

// 训练风格
export const trainStyle = (model = 'deepseek') => {
  return post('/styles/train', { model })
}

// 风格预览
export const previewStyle = (topic, model = 'deepseek') => {
  return post('/styles/preview', { topic, model })
}

// 分析文章风格
export const analyzeArticleStyle = (articleData) => {
  return post('/styles/analyze', articleData)
}

// 上传文件/文本分析个人风格
export const analyzeUploadedStyle = ({ files = [], text = '', title = '' } = {}) => {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f))
  if (text) formData.append('text', text)
  if (title) formData.append('title', title)
  return post('/styles/analyze-upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

// 获取风格建议
export const getStyleSuggestions = (params = {}) => {
  return get('/styles/suggestions', params)
}

// 应用风格到内容
export const applyStyleToContent = (params) => {
  return post('/styles/apply', params)
}
