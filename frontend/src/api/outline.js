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

  // 生成大纲（4 个 Agent 串行，耗时较长，超时设 5 分钟）
  generateOutline(data) {
    return api.post('/outlines/generate', data, { timeout: 300000 })
  },

  // 创作角度体检（三关：信息源 / 角度 / 节奏）
  inspectAngle(data) {
    return api.post('/outlines/inspect-angle', data, { timeout: 180000 })
  },

  // 保存编辑后的大纲
  updateOutline(id, data) {
    return api.patch(`/outlines/${id}`, data)
  },

  // 重新评估大纲（只跑 B→C→D）
  reevaluateOutline(id) {
    return api.post(`/outlines/${id}/reevaluate`)
  },

  // 获取大纲统计
  getStats() {
    return api.get('/outlines/stats/overview')
  }
}

export default outlineApi
