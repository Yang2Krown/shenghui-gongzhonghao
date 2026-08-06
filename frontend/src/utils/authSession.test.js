import { describe, expect, it } from 'vitest'
import { isTerminalAuthError, isTerminalAuthStatus } from './authSession'

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
})
