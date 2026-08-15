import { del, get, post, put } from './api'

export const listDraftDiagnoses = (params = {}) => get('/draft-diagnoses', params)

export const getDraftDiagnosis = (id) => get(`/draft-diagnoses/${id}`)

export const createPastedDraftDiagnosis = (data) => post('/draft-diagnoses', data, { timeout: 120000 })

export const createUploadedDraftDiagnosis = ({ file, title, goal, audience, channel, brief_context }) => {
  const formData = new FormData()
  formData.append('file', file)
  if (title?.trim()) formData.append('title', title.trim())
  if (goal?.trim()) formData.append('goal', goal.trim())
  if (audience?.trim()) formData.append('audience', audience.trim())
  if (channel?.trim()) formData.append('channel', channel.trim())
  if (brief_context && typeof brief_context === 'object') {
    formData.append('brief_context_json', JSON.stringify(brief_context))
  }
  return post('/draft-diagnoses/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

export const createDraftDiagnosisExperience = (id, data) => post(`/draft-diagnoses/${id}/experience-drafts`, data)

export const updateDraftDiagnosisTitle = (id, title) => put(`/draft-diagnoses/${id}/title`, { title })

export const deleteDraftDiagnosis = (id) => del(`/draft-diagnoses/${id}`)
