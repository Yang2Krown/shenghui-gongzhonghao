import api from './api'

// ── 飞书授权（设备码） ──────────────────────────────
// 发起授权：返回 { verification_url, expires_in, status }
export const feishuAuthStart = () => api.post('/feishu/auth/start')

// 查询授权状态：{ status: none|pending|valid|expired, feishu_user_name, ... }
export const feishuAuthStatus = () => api.get('/feishu/auth/status')

// 解除绑定
export const feishuAuthLogout = () => api.delete('/feishu/auth')

// ── brief 读取 / 总结 ──────────────────────────────
// 读取原文：source_type = 'feishu_link' | 'text'
export const feishuBriefRead = (sourceType, value) =>
  api.post('/feishu/brief/read', { source_type: sourceType, value })

// 上传文件（docx/pdf/txt），返回 { title, raw_text }
export const feishuBriefUpload = (file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/feishu/brief/upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

// 结构化总结：返回 StructuredBrief
export const feishuBriefSummarize = (rawText, title = '') =>
  api.post('/feishu/brief/summarize', { raw_text: rawText, title }, { timeout: 60000 })
