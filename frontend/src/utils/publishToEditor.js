/**
 * 发布到公众号编辑器的共享工具
 * - markdown → 语义 HTML 转换
 * - sessionStorage 写入 + 路由跳转
 */

/**
 * 纯文本 / markdown → 语义 HTML
 * 由编辑器负责最终公众号格式（convertToWechatHtml）
 */
export function textToHtml(text) {
  if (!text) return ''
  // 已经是 HTML，原样返回
  if (/<(p|h[1-6]|section|div)[\s>]/i.test(text)) return text
  // 清理 LLM 残留
  let cleaned = text
    .replace(/金句种子[：:]\s*/g, '')
    .replace(/【金句清单[^】]*】[\s\S]*$/g, '')
    .trim()
  return cleaned
    .split(/\n\n+/)
    .map((para) => {
      const t = para.trim()
      if (!t) return ''
      if (t.startsWith('## ')) return `<h2>${t.slice(3).trim()}</h2>`
      if (t.startsWith('### ')) return `<h3>${t.slice(4).trim()}</h3>`
      if (t.startsWith('# ')) return `<h2>${t.slice(2).trim()}</h2>`
      return `<p>${t.replace(/\n/g, '<br>')}</p>`
    })
    .join('\n')
}

/**
 * 一键发布到公众号编辑器
 * @param {object} router - Vue Router 实例（useRouter() 的返回值）
 * @param {string} text - 正文纯文本/markdown
 * @param {string} title - 文章标题
 */
export function publishToWechatEditor(router, text, title) {
  const html = textToHtml(text)
  console.log('[publishToWechatEditor]', {
    textLength: text?.length || 0,
    htmlLength: html.length,
    title,
    textPreview: (text || '').slice(0, 100),
  })
  sessionStorage.setItem('wechat_editor_content', html)
  sessionStorage.setItem('wechat_editor_title', title || '')
  router.push('/creation/wechat-editor')
}
