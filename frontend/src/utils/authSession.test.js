import { describe, expect, it } from 'vitest'
import {
  isTerminalAuthError,
  isTerminalAuthStatus,
  isTransientAuthError,
  retryTransientAuth,
} from './authSession'

describe('authSession', () => {
  it('将 refresh token 不可用的 4xx 视为终态认证失败', () => {
    for (const status of [400, 401, 403, 404, 422]) {
      expect(isTerminalAuthStatus(status)).toBe(true)
      expect(isTerminalAuthError({ response: { status } })).toBe(true)
    }
  })

  it('保留服务暂时不可用和网络错误的登录态', () => {
    for (const status of [408, 429, 500, 502, 503]) {
      expect(isTerminalAuthStatus(status)).toBe(false)
    }
    expect(isTerminalAuthError(new Error('Network Error'))).toBe(false)
  })

  it('将短暂服务故障识别为可重试错误', () => {
    for (const status of [408, 429, 500, 502, 503]) {
      expect(isTransientAuthError({ response: { status } })).toBe(true)
    }
    expect(isTransientAuthError(new Error('Network Error'))).toBe(true)
    expect(isTransientAuthError(new Error('No refresh token'))).toBe(false)
  })

  it('只对短暂故障重试刷新操作', async () => {
    let attempts = 0
    const result = await retryTransientAuth(
      async () => {
        attempts += 1
        if (attempts < 3) throw { response: { status: 503 } }
        return 'recovered'
      },
      { delays: [0, 0] },
    )

    expect(result).toBe('recovered')
    expect(attempts).toBe(3)
  })

  it('短暂故障重试耗尽后交给上层做登录态兜底', async () => {
    let attempts = 0
    await expect(
      retryTransientAuth(
        async () => {
          attempts += 1
          throw { response: { status: 503 } }
        },
        { delays: [0] },
      ),
    ).rejects.toMatchObject({ response: { status: 503 } })

    expect(attempts).toBe(2)
  })
})
