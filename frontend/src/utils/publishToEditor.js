/**
 * 发布到公众号编辑器的共享工具
 * - markdown → 语义 HTML 转换
 * - LLM 智能换行 + 客户端兜底拆分
 * - sessionStorage 写入 + 路由跳转
 */
import { formatParagraphs } from '@/api/api'
import { ElLoading } from 'element-plus'

/**
 * 客户端兜底：对过长段落按句号拆分，确保手机端每段不超过 ~4 行
 * 只处理普通段落，不碰标题 / 列表 / 引用
 */
function splitLongParagraphs(text) {
  if (!text) return ''
  // 关键：LLM 智能换行往往用单换行 \n 分段，这里把任意连续换行都视为段落边界，
  // 否则单 \n 分段会在后续被压成 <br>（换行没生效）。
  return text
    .split(/\n+/)
    .map((para) => {
      const t = para.trim()
      if (!t) return ''
      // 标题行不动
      if (/^#{1,3}\s/.test(t)) return t
      // 已经够短（<=70字）不动
      if (t.length <= 70) return t
      // 按中文句号/问号/感叹号 + 英文句号 拆句
      const sentences = t.match(/[^。！？.!?]+[。！？.!?]+/g) || [t]
      const groups = []
      let buf = ''
      for (const s of sentences) {
        if (!buf) { buf = s; continue }
        // 如果当前累积 + 下一句仍然很短（<40字），合在一起
        if ((buf + s).replace(/[，,；;：:\s]/g, '').length < 40) {
          buf += s
        } else {
          groups.push(buf.trim())
          buf = s
        }
      }
      if (buf.trim()) groups.push(buf.trim())
      return groups.join('\n\n')
    })
    .join('\n\n')
}

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
  // 行内 markdown：**加粗** / *斜体* → <strong>/<em>，否则会原样漏到编辑器
  const inline = (s) => s
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*]+?)\*/g, '$1<em>$2</em>')
  // 同样把任意连续换行视为段落边界：单 \n 也是一个新段落，而不是段内软换行
  return cleaned
    .split(/\n+/)
    .map((para) => {
      const t = para.trim()
      if (!t) return ''
      if (t.startsWith('## ')) return `<h2>${inline(t.slice(3).trim())}</h2>`
      if (t.startsWith('### ')) return `<h3>${inline(t.slice(4).trim())}</h3>`
      if (t.startsWith('# ')) return `<h2>${inline(t.slice(2).trim())}</h2>`
      return `<p>${inline(t)}</p>`
    })
    .join('\n')
}

/**
 * 一键发布到公众号编辑器
 * @param {object} router - Vue Router 实例（useRouter() 的返回值）
 * @param {string} text - 正文纯文本/markdown
 * @param {string} title - 文章标题
 * @param {number|string|null} creationId - 本地创作 ID，用于发布成功后回写状态
 * @returns {Promise<void>}
 */
export async function publishToWechatEditor(router, text, title, creationId = null) {
  const loading = ElLoading.service({
    fullscreen: true,
    lock: true,
    text: '正在智能排版中…',
    background: 'rgba(255,255,255,0.85)',
  })

  try {
    console.log('[publishToWechatEditor] 开始', {
      textLength: text?.length || 0,
      title,
    })

    let finalText = text || ''

    // 调用 LLM 做智能换行（内容不变，只插入段落分隔）
    if (finalText.length >= 120) {
      try {
        const res = await formatParagraphs(finalText)
        const formatted = res.data?.content || res.data || ''
        if (formatted && formatted.length > 0) {
          finalText = formatted
          console.log('[publishToWechatEditor] LLM 换行完成', { newLength: finalText.length })
        }
      } catch (e) {
        console.warn('[publishToWechatEditor] 换行失败，使用原文:', e?.message)
      }
    }

    // 兜底：无论 LLM 是否成功，都用客户端规则拆分过长段落
    finalText = splitLongParagraphs(finalText)

    const html = textToHtml(finalText)
    sessionStorage.setItem('wechat_editor_content', html)
    sessionStorage.setItem('wechat_editor_title', title || '')
    if (creationId) sessionStorage.setItem('wechat_editor_creation_id', String(creationId))
    else sessionStorage.removeItem('wechat_editor_creation_id')
    router.push('/creation/wechat-editor')
  } finally {
    loading.close()
  }
}
