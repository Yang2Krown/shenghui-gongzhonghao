// 后台编排：从当前用户已经打开的飞书页面提取内容，再回传给网站页面。
const CHANNEL = 'gzh-feishu-brief'

const isFeishuUrl = (url = '') => /^https:\/\/([^/]+\.)?(feishu\.cn|feishu\.net|larkoffice\.com|larksuite\.com)\//i.test(url)
const SITE_HOSTS = new Set(['gzh.midonghub.com', 'localhost', '127.0.0.1', '192.168.0.246', '1.13.92.57'])
const canonicalDocumentUrl = (value = '') => {
  try {
    const parsed = new URL(String(value).trim())
    return `${parsed.origin}${parsed.pathname}`.replace(/\/+$/, '')
  } catch {
    return ''
  }
}
const isSiteUrl = (url = '') => {
  try {
    const parsed = new URL(url)
    return (parsed.protocol === 'http:' || parsed.protocol === 'https:') && SITE_HOSTS.has(parsed.hostname)
  } catch {
    return false
  }
}

async function allTabs() {
  return chrome.tabs.query({})
}

async function findFeishuTab(excludeTabId, targetUrl = '') {
  const tabs = await allTabs()
  const candidates = tabs
    .filter((tab) => tab.id !== excludeTabId && isFeishuUrl(tab.url))
  const normalizedTarget = canonicalDocumentUrl(targetUrl)
  if (normalizedTarget) {
    // 链接模式只允许读取用户刚才打开的那一份文档，不能在多标签时猜“最近访问”的页面。
    return candidates.find((tab) => canonicalDocumentUrl(tab.url) === normalizedTarget) || null
  }
  return candidates.sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0))[0] || null
}

async function findSiteTab(excludeTabId, preferredTabId = null) {
  const tabs = await allTabs()
  const candidates = tabs
    .filter((tab) => tab.id !== excludeTabId && isSiteUrl(tab.url))
  if (preferredTabId != null) {
    const preferred = candidates.find((tab) => tab.id === preferredTabId)
    if (preferred) return preferred
  }
  return candidates.sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0))[0] || null
}

let lastSiteTabId = null

async function activateSiteTab(tabId) {
  try {
    const tab = await chrome.tabs.get(tabId)
    if (tab?.windowId != null) await chrome.windows.update(tab.windowId, { focused: true })
    await chrome.tabs.update(tabId, { active: true })
  } catch {
    // 标签页可能在发送完成前被关闭，聚焦失败不影响已经发送的内容。
  }
}

// 这个函数会在飞书页面的 MAIN world 执行，因而可以访问飞书页面自己的
// window.PageMain。内容脚本运行在 isolated world，看不到这个内部对象。
// 这是 Cloud Document Converter 读取完整 block tree 的关键；DOM 只适合作为兜底。
async function extractInternalFeishuText() {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

  const readPageMain = () => {
    try {
      return globalThis.PageMain || globalThis.pageMain || null
    } catch {
      return null
    }
  }

  const readRoot = () => {
    const pageMain = readPageMain()
    try {
      return pageMain?.blockManager?.rootBlockModel
        || pageMain?.blockManager?.model?.rootBlockModel
        || null
    } catch {
      return null
    }
  }

  const childrenOf = (block) => {
    try {
      const children = block?.children
      const result = Array.isArray(children)
        ? children.slice()
        : children && typeof children[Symbol.iterator] === 'function'
          ? Array.from(children)
          : []
      // 同步引用的正文挂在独立的 innerBlockManager 中，不一定出现在 children。
      const nestedRoot = block?.innerBlockManager?.rootBlockModel
      if (nestedRoot && !result.includes(nestedRoot)) result.push(nestedRoot)
      return result
    } catch {
      // 某些版本的 Block 是 Proxy，读取 children 可能在销毁时抛错。
    }
    return []
  }

  const typeOf = (block) => {
    try {
      const snapshotType = block?.snapshot?.type
      if (typeof snapshotType === 'string' && snapshotType) return snapshotType.toLowerCase()
      const type = block?.type
      return typeof type === 'string' ? type.toLowerCase() : ''
    } catch {
      return ''
    }
  }

  const pendingStats = (root) => {
    const seen = new Set()
    const stack = root ? [root] : []
    let blocks = 0
    let pending = 0
    while (stack.length && blocks < 200000) {
      const block = stack.pop()
      if (!block || seen.has(block)) continue
      seen.add(block)
      blocks += 1
      try {
        if (String(block?.snapshot?.type || '').toLowerCase() === 'pending') pending += 1
      } catch {
        // 继续统计其余 block。
      }
      stack.push(...childrenOf(block))
    }
    return { blocks, pending }
  }

  const scrollableRoot = () => {
    const candidates = [document.scrollingElement, document.documentElement, document.body]
    try {
      document.querySelectorAll(
        '[data-testid*="editor"], [data-testid*="document"], [data-testid*="page"], [class*="editor"], [class*="docx"], [class*="document"], [class*="wiki"]'
      ).forEach((element) => candidates.push(element))
    } catch {
      // 页面结构变化时仍可以使用 document.scrollingElement。
    }
    const unique = candidates.filter((element, index, all) => element && all.indexOf(element) === index)
    const scrollDelta = (element) => Math.max(0, (element?.scrollHeight || 0) - (element?.clientHeight || 0))
    const scrollable = unique.filter((element) => {
      if (scrollDelta(element) <= 160) return false
      if (element === document.body || element === document.documentElement || element === document.scrollingElement) return true
      try {
        const style = getComputedStyle(element)
        return /(auto|scroll|overlay)/i.test(`${style.overflowY} ${style.overflow}`)
      } catch {
        return false
      }
    })
    const score = (element) => {
      const identity = `${element.id || ''} ${String(element.className || '')} ${element.getAttribute?.('data-testid') || ''}`
      const semantic = /(docx|editor|document|wiki|content)/i.test(identity) ? 1000000 : 0
      const bodyPenalty = element === document.body ? 900000 : 0
      let textLength = 0
      try {
        textLength = Math.min(String(element.innerText || '').length, 200000)
      } catch {
        // Ignore detached or protected nodes.
      }
      return semantic + textLength + scrollDelta(element) / 2 - bodyPenalty
    }
    return scrollable.sort((a, b) => score(b) - score(a))[0] || null
  }

  const setScrollTop = (element, top) => {
    const value = Math.max(0, Math.round(top))
    if (element === document.body || element === document.documentElement || element === document.scrollingElement) {
      window.scrollTo(0, value)
    }
    element.scrollTop = value
    element.dispatchEvent(new Event('scroll', { bubbles: true }))
  }

  // block tree 的某些节点在首次进入页面时仍是 pending；长文档即使没有 pending
  // 标记，也可能只把当前视口附近的 block 放进模型。参考 Cloud Document
  // Converter 的 prepare 阶段，从顶部按视口走到底部，直到高度和 block 数稳定。
  const warmupModel = async (initialRoot) => {
    if (!initialRoot) return
    const scroller = scrollableRoot()
    if (!scroller) return
    const viewport = Math.max(scroller.clientHeight || window.innerHeight || 800, 480)
    // 无法只靠 pending 判断虚拟列表是否完整，因此短文档也至少走一遍；
    // 这通常只增加一两秒，却能覆盖“初始高度看起来不长、实际正文很长”的情况。
    const originalTop = scroller.scrollTop || 0
    try {
      let stableRounds = 0
      let previousSignature = ''
      for (let round = 0; round < 6 && stableRounds < 2; round += 1) {
        const heightAtStart = scroller.scrollHeight || 0
        const step = Math.max(Math.round(viewport * 0.72), 360)
        let top = 0
        let samples = 0
        while (samples < 240) {
          setScrollTop(scroller, top)
          await sleep(300)
          samples += 1
          const maxTop = Math.max(0, (scroller.scrollHeight || 0) - (scroller.clientHeight || 0))
          if (top >= maxTop - 8) break
          const nextTop = Math.min(maxTop, top + step)
          if (nextTop <= top) break
          top = nextTop
        }

        const maxTop = Math.max(0, (scroller.scrollHeight || 0) - (scroller.clientHeight || 0))
        setScrollTop(scroller, maxTop)
        await sleep(360)
        const currentRoot = readRoot()
        const stats = pendingStats(currentRoot)
        const heightAfterRound = scroller.scrollHeight || 0
        const signature = `${heightAfterRound}:${stats.blocks}:${stats.pending}`
        if (signature === previousSignature && heightAfterRound <= heightAtStart + 8) {
          stableRounds += 1
        } else {
          stableRounds = 0
        }
        previousSignature = signature
      }
    } catch (error) {
      setScrollTop(scroller, originalTop)
      throw error
    }
    // 和 Cloud Document Converter 一样：先在已经加载到末尾的状态下读取模型，
    // 等正文提取完成后再恢复用户原来的滚动位置。
    return () => setScrollTop(scroller, originalTop)
  }

  const normalizeText = (value) => String(value || '')
    .replace(/\r\n?/g, '\n')
    .replace(/\u00a0/g, ' ')
    // 飞书的自动编号在部分渲染版本会混进可见文本，实际不是正文。
    // 统一清掉行首的 auto. / auto．，后面由 block 类型重新生成 Markdown 编号。
    .replace(/^(\s*(?:(?:[-*+]\s+|\d+[.)]\s+|>\s+))?)auto[.．]\s*/gim, '$1')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n[ \t]+/g, '\n')
    .trim()

  const inlineComponentText = (insert, attributes) => {
    const componentValue = attributes?.['inline-component'] || attributes?.inlineComponent
    if (!componentValue) return insert === '\uFFFC' ? '' : insert
    let component = componentValue
    try {
      if (typeof componentValue === 'string') component = JSON.parse(componentValue)
    } catch {
      component = null
    }
    const data = component?.data || {}
    const componentType = String(component?.type || data?.type || '').toLowerCase()
    const title = data?.title || data?.name || data?.text || data?.display_name || ''
    if (/mention_doc|doc_mention|mention_file/.test(componentType)) {
      return title ? (insert && insert !== '\uFFFC' ? `${insert}${title}` : String(title)) : ''
    }
    if (/^user$|mention_user|mention_chat/.test(componentType)) {
      return insert && insert !== '\uFFFC' ? insert : String(title || data?.id || '')
    }
    return insert === '\uFFFC' ? String(title || '') : insert
  }

  const blockText = (block) => {
    try {
      const ops = block?.zoneState?.content?.ops
      if (Array.isArray(ops) && ops.length) {
        return normalizeText(ops.map((operation) => {
          const insert = typeof operation?.insert === 'string' ? operation.insert : ''
          const attributes = operation?.attributes || {}
          // 飞书用 fixEnter 标记段落末尾的结构性换行，block 之间会重新补换行。
          if (attributes?.fixEnter || attributes?.['fix-enter']) return ''
          if (!operation?.attributes && insert === '\n') return ''
          return inlineComponentText(insert, attributes)
        }).join(''))
      }
      const allText = block?.zoneState?.allText
      if (typeof allText === 'string' && allText.trim()) return normalizeText(allText)
      const snapshotText = block?.snapshot?.text
      if (typeof snapshotText === 'string' && snapshotText.trim()) return normalizeText(snapshotText)
    } catch {
      // 继续使用 children；节点可能在飞书更新时短暂不可读。
    }
    return ''
  }

  const sequenceOf = (block) => {
    try {
      const snapshot = block?.snapshot || {}
      const value = snapshot.seq ?? snapshot.sequence ?? block?.seq
      if (typeof value === 'number' && Number.isFinite(value)) return String(value)
      if (typeof value === 'string' && value.trim()) return value.trim()
    } catch {
      // 无序列表或版本差异时不加编号。
    }
    return ''
  }

  const checkedOf = (block) => {
    try {
      const snapshot = block?.snapshot || {}
      return Boolean(snapshot.checked ?? snapshot.done ?? snapshot.is_checked ?? snapshot.isChecked ?? block?.checked)
    } catch {
      return false
    }
  }

  const extractLines = (root) => {
    const seen = new Set()
    let blockCount = 0
    const containerTypes = new Set(['page', 'document', 'root'])

    const cleanLines = (lines) => {
      const result = []
      for (const line of lines) {
        const value = String(line || '').replace(/[ \t]+/g, ' ').trim()
        if (!value) continue
        // 只去掉模型镜像造成的相邻重复，不做全局去重。
        if (result[result.length - 1] === value) continue
        result.push(value)
      }
      return result
    }

    const headingLevelOf = (type) => {
      const match = String(type || '').match(/^heading([1-9])$/)
      return match ? Number(match[1]) : 0
    }

    const listMarkerOf = (type, block) => {
      if (type === 'bullet' || type === 'bulleted' || type === 'list_item') return '- '
      if (type === 'ordered' || type === 'numbered') {
        const sequence = sequenceOf(block)
        // 飞书的 auto 不是要展示给用户的文字，而是“自动编号”标记。
        return sequence && sequence.toLowerCase() !== 'auto' ? `${sequence}. ` : '1. '
      }
      if (type === 'todo' || type === 'task') return checkedOf(block) ? '[x] ' : '[ ] '
      return ''
    }

    const stripLeadingListMarker = (line) => String(line || '')
      .replace(/^\s*(?:[-*+]\s+|\d+[.)]\s+|\[[ xX]\]\s+)/, '')

    const visit = (block) => {
      if (!block || seen.has(block) || blockCount >= 200000) {
        return { plain: [], markdown: [] }
      }
      seen.add(block)
      blockCount += 1
      const type = typeOf(block)
      const children = childrenOf(block)
      const own = blockText(block)
      const childResults = children.map(visit)
      const childPlain = childResults.flatMap((result) => result.plain)
      const childMarkdown = childResults.flatMap((result) => result.markdown)
      const ownLines = own.split('\n').map((line) => line.trim()).filter(Boolean)
      const listMarker = listMarkerOf(type, block)
      const contentLines = listMarker ? ownLines.map(stripLeadingListMarker) : ownLines
      const plainOwn = own && !(children.length && containerTypes.has(type)) ? contentLines : []
      const markdownOwn = []

      if (type === 'divider' || type === 'horizontal_rule') {
        markdownOwn.push('---')
      } else if (plainOwn.length) {
        const headingLevel = headingLevelOf(type)
        if (headingLevel) {
          markdownOwn.push(...ownLines.map((line) => `${'#'.repeat(headingLevel)} ${line}`))
        } else if (listMarker) {
          markdownOwn.push(...contentLines.map((line, index) => `${index === 0 ? listMarker : '  '}${line}`))
        } else if (type === 'quote' || type === 'quote_container') {
          markdownOwn.push(...ownLines.map((line) => `> ${line}`))
        } else if (type === 'code') {
          markdownOwn.push('```', ...ownLines, '```')
        } else {
          markdownOwn.push(...ownLines)
        }
      } else if (headingLevelOf(type) && childMarkdown.length) {
        markdownOwn.push(`${'#'.repeat(headingLevelOf(type))} ${childMarkdown.shift()}`)
      } else if (listMarkerOf(type, block) && childMarkdown.length) {
        markdownOwn.push(`${listMarkerOf(type, block)}${childMarkdown.shift()}`)
      } else if ((type === 'quote' || type === 'quote_container') && childMarkdown.length) {
        markdownOwn.push(...childMarkdown.splice(0).map((line) => `> ${line}`))
      } else if (type === 'code' && childMarkdown.length) {
        markdownOwn.push('```', ...childMarkdown.splice(0), '```')
      }

      return {
        plain: cleanLines([...plainOwn, ...childPlain]),
        markdown: cleanLines([...markdownOwn, ...childMarkdown]),
      }
    }
    const result = visit(root)
    return { plainLines: result.plain, markdownLines: result.markdown, blockCount }
  }

  const permissionError = (text) => /没有权限访问|无权访问|申请阅读权限|申请权限/.test(String(text || ''))

  return (async () => {
    const initialRoot = readRoot()
    if (!initialRoot) return { ok: false, reason: 'internal-model-unavailable' }
    let restoreScroll = null
    try {
      restoreScroll = await warmupModel(initialRoot)
      const root = readRoot()
      if (!root) return { ok: false, reason: 'internal-model-unavailable' }
      const finalStats = pendingStats(root)
      if (finalStats.pending > 0) {
        return { ok: false, reason: 'internal-model-pending', error: '飞书正文仍在加载，请稍后重试' }
      }
      const result = extractLines(root)
      const rawText = result.plainLines.join('\n').trim()
      const markdown = result.markdownLines.join('\n').trim()
      if (permissionError(rawText)) {
        return { ok: false, reason: 'permission', error: '当前账号没有该飞书文档的阅读权限，请先在飞书中申请并获得批准' }
      }
      if (!rawText) {
        return { ok: false, reason: 'internal-model-empty', error: '飞书内部文档模型暂时没有完整正文' }
      }
      return {
        ok: true,
        title: String(document.title || '').replace(/\s*[-|｜]\s*(飞书|Lark).*$/i, '').trim() || '飞书 Brief',
        sourceUrl: window.location.href,
        rawText,
        markdown: markdown || rawText,
        charCount: rawText.length,
        method: 'internal-page-model',
        blockCount: result.blockCount,
      }
    } finally {
      try {
        restoreScroll?.()
      } catch {
        // 恢复滚动失败不影响已经提取到的正文。
      }
    }
  })()
}

async function extractFromTab(tabId, fullScan = true) {
  try {
    if (chrome.scripting?.executeScript) {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        world: 'MAIN',
        func: extractInternalFeishuText,
      })
      const internalResult = results?.[0]?.result
      if (internalResult?.ok) return internalResult
    }
  } catch {
    // 页面不支持 MAIN world、扩展版本尚未重新加载，或当前 tab 不是普通网页时，走 DOM 兜底。
  }

  try {
    return await chrome.tabs.sendMessage(tabId, {
      channel: CHANNEL,
      type: 'extract-current',
      fullScan
    })
  } catch (error) {
    return {
      ok: false,
      error: '没有连接到飞书页面，请确认插件已安装并刷新该文档页面'
    }
  }
}

async function sendToSite(siteTabId, payload) {
  if (siteTabId == null) return false
  const message = {
    channel: CHANNEL,
    type: payload.ok ? 'extracted' : 'error',
    payload: payload.ok ? payload : undefined,
    error: payload.ok ? undefined : payload.error,
  }
  try {
    await chrome.tabs.sendMessage(siteTabId, message)
    return true
  } catch {
    // 网站可能在插件安装前就已经打开，content script 没有自动注入；
    // 发送失败时补注入一次，避免用户必须手动重开服务器页面。
    try {
      await chrome.scripting.executeScript({ target: { tabId: siteTabId }, files: ['site-bridge.js'] })
      await new Promise((resolve) => setTimeout(resolve, 80))
      await chrome.tabs.sendMessage(siteTabId, message)
      return true
    } catch {
      return false
    }
  }
}

async function extractForSite(siteTabId, targetUrl = '') {
  const feishuTab = await findFeishuTab(siteTabId, targetUrl)
  if (!feishuTab) {
    await sendToSite(siteTabId, {
      ok: false,
      error: targetUrl ? '没有找到刚才打开的那份飞书 Brief，请确认文档已加载并保持打开' : '没有找到已打开的飞书文档，请先在浏览器打开 Brief'
    })
    return
  }
  const result = await extractFromTab(feishuTab.id)
  const sent = await sendToSite(siteTabId, result)
  if (sent && result?.ok) await activateSiteTab(siteTabId)
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.channel !== CHANNEL) return false

  if (message.type === 'ping') {
    if (sender.tab?.id != null && isSiteUrl(sender.tab.url)) lastSiteTabId = sender.tab.id
    sendResponse({ channel: CHANNEL, type: 'ready' })
    return false
  }

  if (message.type === 'extract-current') {
    // 网站按钮触发：把结果异步推回同一个网站标签页。
    if (sender.tab?.id != null && isSiteUrl(sender.tab.url)) {
      lastSiteTabId = sender.tab.id
      extractForSite(sender.tab.id, message.payload?.targetUrl || '').catch((error) => {
        sendToSite(sender.tab.id, { ok: false, error: error?.message || '提取失败' })
      })
      sendResponse({ channel: CHANNEL, type: 'accepted' })
      return false
    }

    // 插件弹窗触发：返回给弹窗本身，便于先预览。
    const activeTabPromise = chrome.tabs.query({ active: true, lastFocusedWindow: true })
    activeTabPromise
      .then((tabs) => tabs[0])
      .then((tab) => tab?.id != null ? extractFromTab(tab.id, message.fullScan !== false) : { ok: false, error: '没有找到当前页面' })
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: error?.message || '提取失败' }))
    return true
  }

  if (message.type === 'deliver-to-site') {
    findSiteTab(sender.tab?.id, lastSiteTabId)
      .then(async (siteTab) => {
        if (!siteTab) return { sent: false, siteTab: null }
        const sent = await sendToSite(siteTab.id, message.payload || {})
        if (sent && message.payload?.ok) await activateSiteTab(siteTab.id)
        return { sent, siteTab }
      })
      .then(({ sent }) => sendResponse({ ok: sent, error: sent ? undefined : '没有找到可接收消息的公众号智能体页面，请先打开并刷新网站页面后重试' }))
      .catch((error) => sendResponse({ ok: false, error: error?.message || '发送失败' }))
    return true
  }

  return false
})
