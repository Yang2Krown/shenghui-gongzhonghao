// 这些状态码表示当前认证凭据已经不能继续使用。
// 短暂的 5xx、超时和网络错误会先由刷新流程重试；重试耗尽后的最终兜底由上层处理。
const TERMINAL_AUTH_STATUSES = new Set([400, 401, 403, 404, 422])
const TRANSIENT_AUTH_STATUSES = new Set([408, 429])
const DEFAULT_RETRY_DELAYS = [400, 1200]

export const isTerminalAuthStatus = (status) => {
  return TERMINAL_AUTH_STATUSES.has(Number(status))
}

export const isTerminalAuthError = (error) => {
  return isTerminalAuthStatus(error?.response?.status)
}

export const isTransientAuthError = (error) => {
  if (!error || error.message === 'No refresh token') return false
  if (!error.response) return true

  const status = Number(error.response.status)
  return TRANSIENT_AUTH_STATUSES.has(status) || status >= 500
}

// 刷新接口在电脑唤醒、容器重启或网络恢复的短窗口内可能暂时失败。
// 只重试可恢复错误，终态认证错误立即交给上层清理登录态。
export const retryTransientAuth = async (
  operation,
  { delays = DEFAULT_RETRY_DELAYS } = {},
) => {
  let attempt = 0

  while (true) {
    try {
      return await operation()
    } catch (error) {
      const delay = delays[attempt]
      if (!isTransientAuthError(error) || delay === undefined) throw error

      await new Promise((resolve) => setTimeout(resolve, delay))
      attempt += 1
    }
  }
}
