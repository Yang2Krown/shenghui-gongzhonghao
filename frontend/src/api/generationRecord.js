import api from './api'

export const generationRecordApi = {
  list(params = {}) {
    return api.get('/generation-records', { params })
  },

  get(id) {
    return api.get(`/generation-records/${id}`)
  },

  /**
   * 获取某个选题下所有已完成的生成记录（每种 type 最新一条）
   * 用于从历史记录恢复创作状态
   */
  byCandidate(candidateId) {
    return api.get(`/generation-records/by-candidate/${candidateId}`)
  },
}

export default generationRecordApi
