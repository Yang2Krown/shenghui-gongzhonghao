import { get, post } from './api'

export const listExperienceCards = (params = {}) => get('/experience', params)

export const createExperienceCard = (data) => post('/experience', data)

export const parseExperienceUpload = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return post('/experience/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}
