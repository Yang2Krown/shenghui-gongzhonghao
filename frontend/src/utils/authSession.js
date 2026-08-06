// 这些状态码表示当前认证凭据已经不能继续使用。
// 5xx、超时和网络错误不属于凭据失效，不能因为服务暂时故障把用户强制退出。
const TERMINAL_AUTH_STATUSES = new Set([400, 401, 403, 404, 422])

export const isTerminalAuthStatus = (status) => {
  return TERMINAL_AUTH_STATUSES.has(Number(status))
}

export const isTerminalAuthError = (error) => {
  return isTerminalAuthStatus(error?.response?.status)
}
