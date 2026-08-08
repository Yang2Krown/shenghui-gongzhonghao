import { get, post, put, del } from './api'

// ── 成员 ────────────────────────────────────────────────
export const listTeamMembers = (params = {}) => {
  return get('/team/members', params)
}

export const updateTeamMember = (userId, data) => {
  return put(`/team/members/${userId}`, data)
}

// 管理员直接赋予 / 取消员工角色（无邀请码流程）
export const searchTeamCandidates = (keyword) => {
  return get('/team/users/search', { keyword })
}

export const updateMemberRole = (userId, role) => {
  return put(`/team/members/${userId}/role`, { role })
}

// ── 文章共享 ────────────────────────────────────────────
export const shareCreation = (creationId, data) => {
  return post(`/team/creations/${creationId}/share`, data)
}

export const unshareCreation = (creationId, userId) => {
  return del(`/team/creations/${creationId}/share/${userId}`)
}

export const listCreationMembers = (creationId) => {
  return get(`/team/creations/${creationId}/members`)
}
