import { get, post, put } from './api'

export const listExperienceCards = (params = {}) => get('/experience', params)

export const createExperienceCard = (data) => post('/experience', data)

export const createExperienceDraft = (data) => post('/experience/drafts', data)

export const getExperienceCard = (id) => get(`/experience/${id}`)

export const updateExperienceCard = (id, data) => put(`/experience/${id}`, data)

export const confirmExperienceCard = (id) => post(`/experience/${id}/confirm`)

export const rejectExperienceCard = (id) => post(`/experience/${id}/reject`)

export const parseExperienceUpload = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return post('/experience/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

export const scanExperienceOverlaps = () => post('/experience/overlaps', {}, { timeout: 120000 })

export const getSimilarExperiences = (id) => get(`/experience/${id}/similar`)

export const previewExperienceMerge = (sourceIds) =>
  post('/experience/merge/preview', { source_ids: sourceIds }, { timeout: 120000 })

export const confirmExperienceMerge = (data) =>
  post('/experience/merge', data, { timeout: 120000 })
