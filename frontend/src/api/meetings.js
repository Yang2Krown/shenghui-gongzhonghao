import { get, post, put } from './api'

export const listMeetings = (params = {}) => get('/meetings', params)

export const createMeeting = (data) => post('/meetings', data)

export const getMeeting = (id) => get(`/meetings/${id}`)

export const getMeetingSummary = (params = {}) => get('/meetings/summary', params)

export const extractMeeting = (id) => post(`/meetings/${id}/extract`)

export const updateMeetingSynthesis = (id, data) => put(`/meetings/${id}/synthesis`, data)

export const createMeetingExperienceDrafts = (id) => post(`/meetings/${id}/experience-drafts`)

export const updateMeetingSuggestion = (id, data) => put(`/meetings/suggestions/${id}`, data)

export const linkMeetingSuggestion = (id, creationId) => post(`/meetings/suggestions/${id}/link`, { creation_id: creationId })

export const getMeetingStats = (params = {}) => get('/meetings/stats', params)
