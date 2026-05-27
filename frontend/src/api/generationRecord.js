import api from './api'

export const generationRecordApi = {
  list(params = {}) {
    return api.get('/generation-records', { params })
  },

  get(id) {
    return api.get(`/generation-records/${id}`)
  },
}

export default generationRecordApi
