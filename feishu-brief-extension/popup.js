let latest = null

const $ = (id) => document.getElementById(id)
const status = (text, error = false, busy = false) => {
  $('status').textContent = text
  $('status').style.color = error ? '#a23f36' : ''
  $('status').classList.toggle('busy', busy)
}

const escapeHtml = (value) => String(value || '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}[character]))

const inlineMarkdown = (value) => {
  let html = escapeHtml(value)
  const links = []
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_match, label, url) => {
    const token = `\u0000LINK${links.length}\u0000`
    links.push(`<a href="${url}" target="_blank" rel="noreferrer">${label}</a>`)
    return token
  })
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*|__([^_]+)__/g, (_match, strong, strongAlt) => `<strong>${strong || strongAlt}</strong>`)
  html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  html = html.replace(/(^|[\s(])(https?:\/\/[^\s<]+)/g, (_match, prefix, rawUrl) => {
    const trailing = rawUrl.match(/[),.;!?，。；：】）]+$/)?.[0] || ''
    const url = trailing ? rawUrl.slice(0, -trailing.length) : rawUrl
    return `${prefix}<a href="${url}" target="_blank" rel="noreferrer">${url}</a>${trailing}`
  })
  return html.replace(/\u0000LINK(\d+)\u0000/g, (_match, index) => links[Number(index)] || '')
}

const renderMarkdown = (source) => {
  const lines = String(source || '').replace(/\r\n?/g, '\n').split('\n')
  const html = []
  let paragraph = []
  let listType = ''
  let listItems = []
  let inCode = false
  let codeLanguage = ''
  let codeLines = []

  const flushParagraph = () => {
    if (!paragraph.length) return
    html.push(`<p>${paragraph.map(inlineMarkdown).join('<br>')}</p>`)
    paragraph = []
  }

  const flushList = () => {
    if (!listType) return
    html.push(`<${listType}>${listItems.map((item) => `<li>${inlineMarkdown(item)}</li>`).join('')}</${listType}>`)
    listType = ''
    listItems = []
  }

  const flushText = () => {
    flushParagraph()
    flushList()
  }

  for (const line of lines) {
    const fence = line.match(/^\s*```\s*([\w-]*)\s*$/)
    if (fence) {
      if (inCode) {
        html.push(`<pre><code class="language-${escapeHtml(codeLanguage)}">${escapeHtml(codeLines.join('\n'))}</code></pre>`)
        inCode = false
        codeLanguage = ''
        codeLines = []
      } else {
        flushText()
        inCode = true
        codeLanguage = fence[1] || ''
      }
      continue
    }
    if (inCode) {
      codeLines.push(line)
      continue
    }

    if (!line.trim()) {
      flushText()
      continue
    }

    const heading = line.match(/^\s*(#{1,6})\s+(.+?)\s*#*\s*$/)
    if (heading) {
      flushText()
      const level = heading[1].length
      html.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`)
      continue
    }

    if (/^\s*(?:---+|\*\s*\*\s*\*)\s*$/.test(line)) {
      flushText()
      html.push('<hr>')
      continue
    }

    const quote = line.match(/^\s*>\s?(.*)$/)
    if (quote) {
      flushText()
      html.push(`<blockquote><p>${inlineMarkdown(quote[1])}</p></blockquote>`)
      continue
    }

    const task = line.match(/^\s*[-*+]\s+\[([ xX])\]\s+(.*)$/)
    const unordered = line.match(/^\s*[-*+]\s+(.*)$/)
    const ordered = line.match(/^\s*\d+[.)]\s+(.*)$/)
    if (task || unordered || ordered) {
      const nextType = ordered ? 'ol' : 'ul'
      if (listType !== nextType) {
        flushParagraph()
        flushList()
        listType = nextType
      }
      const item = task ? `${task[1].toLowerCase() === 'x' ? '✓' : '○'} ${task[2]}` : (ordered ? ordered[1] : unordered[1])
      listItems.push(item)
      continue
    }

    // 连续的普通行作为一个 Markdown 段落，保留原文换行。
    if (listType) flushList()
    paragraph.push(line)
  }

  if (inCode) html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
  flushText()
  return html.join('') || '<p>没有可预览的文字内容。</p>'
}

$('extract').addEventListener('click', () => {
  $('extract').disabled = true
  $('send').disabled = true
  $('result').hidden = true
  status('⚠️ 提取中请勿离开、点击或刷新。正在加载完整文字内容，长文档可能需要几秒…', false, true)

  chrome.runtime.sendMessage(
    { channel: 'gzh-feishu-brief', type: 'extract-current', fullScan: true },
    (response) => {
      $('extract').disabled = false
      if (chrome.runtime.lastError) {
        status(chrome.runtime.lastError.message, true)
        return
      }
      if (!response?.ok) {
        status(response?.error || '提取失败', true)
        return
      }
      latest = response
      $('title').textContent = response.title || '飞书 Brief'
      const scanMeta = response.scan?.samples ? ` · 扫描 ${response.scan.samples} 个视口` : ''
      const blockMeta = response.blockCount ? ` · ${response.blockCount} 个文档块` : ''
      $('meta').textContent = `${response.charCount || response.rawText.length} 字 · ${response.method || '页面提取'}${blockMeta}${scanMeta}`
      $('preview').innerHTML = renderMarkdown(response.markdown || response.rawText)
      $('result').hidden = false
      $('send').disabled = false
      status('提取成功。确认内容无误后，可发送到网站。')
    }
  )
})

$('send').addEventListener('click', () => {
  if (!latest) return
  $('send').disabled = true
  status('正在发送到网站…')
  chrome.runtime.sendMessage(
    { channel: 'gzh-feishu-brief', type: 'deliver-to-site', payload: latest },
    (response) => {
      if (chrome.runtime.lastError || !response?.ok) {
        $('send').disabled = false
        status(response?.error || chrome.runtime.lastError?.message || '发送失败', true)
        return
      }
      status('已发送到网站，正在自动返回实操创作页并开始解析。')
    }
  )
})
