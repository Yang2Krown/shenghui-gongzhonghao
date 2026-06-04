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

  /**
   * 创建生成记录
   * @param {Object} data - 记录数据
   * @param {string} data.type - 记录类型
   * @param {Object} data.input_snapshot - 输入快照
   * @param {string} [data.display_title] - 显示标题
   * @param {Object} [data.output_snapshot] - 输出快照
   * @param {Object} [data.resume_context] - 恢复上下文
   */
  create(data) {
    return api.post('/generation-records', data)
  },
}

export default generationRecordApi
