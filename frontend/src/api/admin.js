import { get, patch, post } from './api'

export const getMonitoringOverview = () => {
  return get('/admin/monitoring/overview')
}

export const getSourceHealth = () => {
  return get('/admin/monitoring/source-health')
}

export const getAiCosts = () => {
  return get('/admin/monitoring/ai-costs')
}

export const createLlmPricing = (data) => {
  return post('/admin/monitoring/ai-costs/pricing', data)
}

export const updateLlmPricing = (id, data) => {
  return patch(`/admin/monitoring/ai-costs/pricing/${id}`, data)
}

export const getApiHealth = () => {
  return get('/admin/monitoring/api-health')
}

export const getUserStats = () => {
  return get('/admin/monitoring/user-stats')
}

export const getSecurityHealth = () => {
  return get('/admin/monitoring/security-health')
}

export const getMonitoringSnapshots = (limit = 24) => {
  return get('/admin/monitoring/snapshots', { limit })
}

export const getMonitoringAlerts = (params = {}) => {
  return get('/admin/monitoring/alerts', params)
}

export const updateMonitoringAlert = (id, data) => {
  return patch(`/admin/monitoring/alerts/${id}`, data)
}

export const getAdmins = () => {
  return get('/admin/admins')
}

export const getAdminUsers = (params = {}) => {
  return get('/admin/users', params)
}

export const getFailedTasks = (limit = 30) => {
  return get('/admin/tasks/failed', { limit })
}

export const getAdminAuditLogs = (limit = 50) => {
  return get('/admin/audit-logs', { limit })
}

export const setAdminByPhone = (phone, role = 'admin') => {
  return post('/admin/admins', { phone, is_admin: role !== 'user', role })
}

export const updateAdminUserStatus = (id, data) => {
  return patch(`/admin/users/${id}/status`, data)
}

export const updateAdminUserMembership = (id, data) => {
  return patch(`/admin/users/${id}/membership`, data)
}
