import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiFns = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}))

vi.mock('./api', () => apiFns)

import {
  createDraftDiagnosisExperience,
  createPastedDraftDiagnosis,
  createUploadedDraftDiagnosis,
  getDraftDiagnosis,
  listDraftDiagnoses,
} from './draftDiagnoses'

describe('draft diagnoses API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('调用诊断历史、详情和粘贴文字入口', () => {
    listDraftDiagnoses({ page: 2 })
    getDraftDiagnosis(7)
    createPastedDraftDiagnosis({ content: '初稿' })
    createDraftDiagnosisExperience(7, { finding_index: 0 })
    expect(apiFns.get).toHaveBeenNthCalledWith(1, '/draft-diagnoses', { page: 2 })
    expect(apiFns.get).toHaveBeenNthCalledWith(2, '/draft-diagnoses/7')
    expect(apiFns.post).toHaveBeenNthCalledWith(1, '/draft-diagnoses', { content: '初稿' }, { timeout: 120000 })
    expect(apiFns.post).toHaveBeenNthCalledWith(2, '/draft-diagnoses/7/experience-drafts', { finding_index: 0 })
  })

  it('上传初稿文件并传递商单 brief 上下文', () => {
    const file = new File(['正文'], 'draft.md', { type: 'text/markdown' })
    createUploadedDraftDiagnosis({
      file,
      title: '初稿',
      brief_context: { core_message: '先让读者看到结果' },
    })
    const [url, formData, config] = apiFns.post.mock.calls[0]
    expect(url).toBe('/draft-diagnoses/upload')
    expect(formData).toBeInstanceOf(FormData)
    expect(formData.get('file')).toBe(file)
    expect(JSON.parse(formData.get('brief_context_json'))).toEqual({ core_message: '先让读者看到结果' })
    expect(config.timeout).toBe(120000)
  })
})
