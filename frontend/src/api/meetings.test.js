import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiFns = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}))

vi.mock('./api', () => apiFns)

import {
  createMeetingExperienceDrafts,
  createMeeting,
  extractMeeting,
  getMeeting,
  getMeetingSummary,
  getMeetingStats,
  linkMeetingSuggestion,
  listMeetings,
  updateMeetingSuggestion,
  updateMeetingSynthesis,
} from './meetings'

describe('meetings API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('使用统一 API client 调用会议列表和统计接口', () => {
    listMeetings({ page: 2, status: 'ready' })
    getMeetingSummary()
    getMeetingStats()
    expect(apiFns.get).toHaveBeenNthCalledWith(1, '/meetings', { page: 2, status: 'ready' })
    expect(apiFns.get).toHaveBeenNthCalledWith(2, '/meetings/summary', {})
    expect(apiFns.get).toHaveBeenNthCalledWith(3, '/meetings/stats', {})
  })

  it('覆盖创建、提取、建议更新和文章关联动作', () => {
    createMeeting({ title: '周会' })
    getMeeting(7)
    extractMeeting(7)
    updateMeetingSynthesis(7, { summary: '方法论摘要' })
    updateMeetingSuggestion(9, { status: 'adopted' })
    linkMeetingSuggestion(9, 12)
    createMeetingExperienceDrafts(7)
    expect(apiFns.post).toHaveBeenNthCalledWith(1, '/meetings', { title: '周会' })
    expect(apiFns.get).toHaveBeenCalledWith('/meetings/7')
    expect(apiFns.post).toHaveBeenNthCalledWith(2, '/meetings/7/extract')
    expect(apiFns.put).toHaveBeenNthCalledWith(1, '/meetings/7/synthesis', { summary: '方法论摘要' })
    expect(apiFns.put).toHaveBeenCalledWith('/meetings/suggestions/9', { status: 'adopted' })
    expect(apiFns.post).toHaveBeenNthCalledWith(3, '/meetings/suggestions/9/link', { creation_id: 12 })
    expect(apiFns.post).toHaveBeenNthCalledWith(4, '/meetings/7/experience-drafts')
  })
})
