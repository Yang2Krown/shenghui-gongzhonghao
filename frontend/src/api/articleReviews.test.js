import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const apiFns = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}))

vi.mock('./api', () => apiFns)
vi.mock('@/stores/user', () => ({
  useUserStore: () => ({ token: 'test-token' }),
}))

import {
  addArticleReviewComment,
  analyzeArticleReview,
  createArticleReview,
  getArticleReview,
  listArticleReviews,
  promoteArticleReview,
  streamArticleReview,
  updateArticleReviewAnalysis,
} from './articleReviews'

describe('article reviews API', () => {
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => vi.unstubAllGlobals())

  it('调用文章复盘列表、详情和任务接口', () => {
    listArticleReviews({ page: 2, status: 'reviewing' })
    getArticleReview(7)
    analyzeArticleReview(7)
    addArticleReviewComment(7, { change_group_id: 'change-001', body: '保留这个改法' })
    updateArticleReviewAnalysis(7, { summary: '人工确认' })
    promoteArticleReview(7, { change_group_ids: ['change-001'] })
    expect(apiFns.get).toHaveBeenNthCalledWith(1, '/reviews', { page: 2, status: 'reviewing' })
    expect(apiFns.get).toHaveBeenNthCalledWith(2, '/reviews/7')
    expect(apiFns.post).toHaveBeenNthCalledWith(1, '/reviews/7/analyze')
    expect(apiFns.post).toHaveBeenNthCalledWith(2, '/reviews/7/comments', { change_group_id: 'change-001', body: '保留这个改法' })
    expect(apiFns.put).toHaveBeenCalledWith('/reviews/7/analysis', { summary: '人工确认' })
    expect(apiFns.post).toHaveBeenNthCalledWith(3, '/reviews/7/promote', { change_group_ids: ['change-001'] })
  })

  it('上传改前稿和改后稿，并带上标题', () => {
    const before = new File(['旧稿'], 'before.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
    const after = new File(['新稿'], 'after.pdf', { type: 'application/pdf' })
    createArticleReview(before, after, '一篇复盘')
    const [url, formData, config] = apiFns.post.mock.calls[0]
    expect(url).toBe('/reviews')
    expect(formData).toBeInstanceOf(FormData)
    expect(formData.get('before_file')).toBe(before)
    expect(formData.get('after_file')).toBe(after)
    expect(formData.get('title')).toBe('一篇复盘')
    expect(config.timeout).toBe(30000)
  })

  it('解析 SSE 进度帧并携带 Bearer token', async () => {
    const frames = [
      'event: progress\ndata: {"progress":{"current_step":1,"action":"正在解析改前稿…"}}\n\n',
      'event: progress\ndata: {"progress":{"done":true,"result":{"status":"reviewing"}}}\n\n',
    ].map((item) => new TextEncoder().encode(item))
    let index = 0
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn(async () => (index < frames.length
            ? { done: false, value: frames[index++] }
            : { done: true, value: undefined })),
        }),
      },
    }))
    const progress = []
    await streamArticleReview(7, (payload) => progress.push(payload))
    expect(fetch).toHaveBeenCalledWith('/api/v1/reviews/7/stream', {
      headers: { Accept: 'text/event-stream', Authorization: 'Bearer test-token' },
      signal: undefined,
    })
    expect(progress).toHaveLength(2)
    expect(progress[0].progress.current_step).toBe(1)
    expect(progress[1].progress.done).toBe(true)
  })
})
