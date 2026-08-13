import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiFns = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}))

vi.mock('./api', () => apiFns)

import {
  diffContentVersions,
  getContentVersion,
  listContentVersions,
  saveContentVersion,
  summarizeContentVersions,
} from './contentVersions'
import {
  confirmExperienceCard,
  createExperienceDraft,
  getExperienceCard,
  parseExperienceUpload,
  rejectExperienceCard,
  updateExperienceCard,
} from './experience'

describe('content versions and experience API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('调用版本列表、详情、保存和文本 diff 接口', () => {
    listContentVersions(7, { version_type: 'final' })
    getContentVersion(7, 3)
    saveContentVersion(7, { version_type: 'manual' })
    diffContentVersions(7, 2, 3)
    summarizeContentVersions(7, 2, 3, true)

    expect(apiFns.get).toHaveBeenNthCalledWith(1, '/creations/7/versions', { version_type: 'final' })
    expect(apiFns.get).toHaveBeenNthCalledWith(2, '/creations/7/versions/3')
    expect(apiFns.post).toHaveBeenNthCalledWith(1, '/creations/7/versions', { version_type: 'manual' })
    expect(apiFns.get).toHaveBeenNthCalledWith(3, '/creations/7/versions/diff', { a: 2, b: 3 })
    expect(apiFns.post).toHaveBeenNthCalledWith(
      2,
      '/creations/7/versions/diff/summary',
      {},
      { params: { a: 2, b: 3, retry: true } },
    )
  })

  it('上传经验文件时使用 multipart/form-data', () => {
    const file = new File(['hello'], '经验.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    parseExperienceUpload(file)
    const [, body, config] = apiFns.post.mock.calls[0]
    expect(body).toBeInstanceOf(FormData)
    expect(config.headers['Content-Type']).toBe('multipart/form-data')
  })

  it('调用经验待确认、详情和确认接口', () => {
    createExperienceDraft({ title: '标题', content: '正文', source_type: 'uploaded' })
    getExperienceCard(8)
    updateExperienceCard(8, { content: '修订后' })
    confirmExperienceCard(8)
    rejectExperienceCard(9)

    expect(apiFns.post).toHaveBeenLastCalledWith('/experience/9/reject')
    expect(apiFns.get).toHaveBeenLastCalledWith('/experience/8')
    expect(apiFns.put).toHaveBeenCalledWith('/experience/8', { content: '修订后' })
  })
})
