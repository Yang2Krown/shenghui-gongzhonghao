import { get, post } from './api'

export const listContentVersions = (creationId, params = {}) => {
  return get(`/creations/${creationId}/versions`, params)
}

export const getContentVersion = (creationId, versionId) => {
  return get(`/creations/${creationId}/versions/${versionId}`)
}

export const saveContentVersion = (creationId, data) => {
  return post(`/creations/${creationId}/versions`, data)
}

export const diffContentVersions = (creationId, beforeVersionId, afterVersionId) => {
  return get(`/creations/${creationId}/versions/diff`, {
    a: beforeVersionId,
    b: afterVersionId,
  })
}

export const summarizeContentVersions = (creationId, beforeVersionId, afterVersionId, retry = false) => {
  return post(
    `/creations/${creationId}/versions/diff/summary`,
    {},
    {
      params: {
        a: beforeVersionId,
        b: afterVersionId,
        retry,
      },
    },
  )
}
