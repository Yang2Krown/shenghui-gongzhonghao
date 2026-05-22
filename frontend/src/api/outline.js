import api from './api'

// 大纲API
export const outlineApi = {
  // 获取大纲列表
  getOutlines(params = {}) {
    return api.get('/outlines', { params })
  },

  // 获取大纲详情
  getOutline(id) {
    return api.get(`/outlines/${id}`)
  },

  // 生成大纲
  generateOutline(data) {
    return api.post('/outlines/generate', data)
  },

  // 获取大纲统计
  getStats() {
    return api.get('/outlines/stats/overview')
  }
}

export default outlineApi
