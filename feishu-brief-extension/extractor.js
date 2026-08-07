// 页面侧提取器：只读取当前用户已经在浏览器中打开的页面内容。
// 不读取 Cookie、不调用飞书 OpenAPI，也不会主动把正文上传到第三方服务。
(function installExtractor() {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

  const isVisible = (el) => {
    if (!el || !(el instanceof Element)) return false
    const style = window.getComputedStyle(el)
    const rect = el.getBoundingClientRect()
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
  }

  const splitLines = (value) => String(value || '')
      .replace(/\u00a0/g, ' ')
      .replace(/\r/g, '')
      .split('\n')
      // 某些飞书渲染版本会把 ordered block 的内部 seq=auto 显示成文字。
      .map((line) => line.replace(/^(\s*(?:(?:[-*+]\s+|\d+[.)]\s+|>\s+))?)auto[.．]\s*/i, '$1').replace(/[ \t]+/g, ' ').trim())
      .filter(Boolean)

  const normalizeLines = (value) => {
    const lines = splitLines(value)

    const output = []
    for (const line of lines) {
      // 只折叠相邻重复行；同一句话在 Brief 中不同位置重复出现时必须保留。
      if (output[output.length - 1] === line) continue
      output.push(line)
    }
    return output.join('\n')
  }

  const textOf = (el) => normalizeLines(el?.innerText || el?.textContent || '')

  const candidateRoots = () => {
    const selectors = [
      '[role="main"]',
      'main',
      'article',
      '[data-testid*="editor"]',
      '[data-testid*="document"]',
      '[class*="editor"]',
      '[class*="doc-content"]',
      '[class*="wiki-content"]'
    ]
    const candidates = []
    for (const selector of selectors) {
      document.querySelectorAll(selector).forEach((el) => {
        if (!isVisible(el)) return
        const text = textOf(el)
        if (text.length >= 80) candidates.push({ el, text, selector })
      })
    }
    const bodyText = textOf(document.body)
    if (bodyText) candidates.push({ el: document.body, text: bodyText, selector: 'body' })
    return candidates
  }

  const findTextRoot = () => {
    const candidates = candidateRoots()
    if (!candidates.length) return document.body
    // 不再单纯按 innerText 长度选 root：body/工具栏可能因为当前位置不同而暂时更长。
    // 编辑器语义、滚动高度和 block 数一起参与排序，让不同初始滚动位置得到同一个 root。
    return candidates
      .sort((a, b) => {
        const score = (item) => {
          const el = item.el
          const identity = `${el.id || ''} ${String(el.className || '')} ${item.selector || ''}`
          const semantic = /(docx|editor|document|wiki|content)/i.test(identity) ? 120000 : 0
          const landmark = /^(body|main|article|\[role="main"\])$/i.test(item.selector || '') ? 20000 : 0
          const bodyPenalty = el === document.body ? 90000 : 0
          const blockCount = el.querySelectorAll?.(
            '[data-block-id], [data-testid*="block"], [data-node-type], [class*="block"]'
          ).length || 0
          return semantic + landmark + Math.min(item.text.length, 160000) + Math.min(blockCount, 200) * 500
            + Math.min(scrollDelta(el), 1000000) / 20 - bodyPenalty
        }
        return score(b) - score(a)
      })
      .map((item) => item.el)[0]
  }

  const scrollDelta = (el) => Math.max(0, (el?.scrollHeight || 0) - (el?.clientHeight || 0))

  const isScrollable = (el) => {
    if (!el || !(el instanceof Element)) return false
    if (scrollDelta(el) <= 160) return false
    const style = window.getComputedStyle(el)
    const overflow = `${style.overflowY} ${style.overflow}`
    return /(auto|scroll|overlay)/i.test(overflow) || el === document.body || el === document.documentElement
  }

  const findScrollRoot = (textRoot) => {
    const candidates = [textRoot, document.scrollingElement, document.documentElement, document.body]
    let current = textRoot
    while (current && current.parentElement && candidates.length < 12) {
      current = current.parentElement
      candidates.push(current)
    }

    // 飞书通常把编辑器放在 body 的后代滚动容器里，不能只检查文本根节点的祖先。
    // 只扫描有可能成为编辑器容器的节点，避免对大型页面做无意义的全 DOM 排序。
    if (textRoot?.querySelectorAll) {
      textRoot.querySelectorAll(
        '[data-testid*="editor"], [data-testid*="document"], [class*="editor"], [class*="docx"], [class*="document"], [class*="wiki"]'
      ).forEach((el) => candidates.push(el))
    }

    const unique = candidates.filter((el, index, all) => el && all.indexOf(el) === index)
    const scrollable = unique.filter(isScrollable)
    if (!scrollable.length) return null

    // 优先选择明确的 overflow 滚动容器；若页面只用 document scrolling，则回退到高度最大的容器。
    return scrollable.sort((a, b) => {
      const aStyle = window.getComputedStyle(a)
      const bStyle = window.getComputedStyle(b)
      const aOverflow = /(auto|scroll|overlay)/i.test(`${aStyle.overflowY} ${aStyle.overflow}`)
      const bOverflow = /(auto|scroll|overlay)/i.test(`${bStyle.overflowY} ${bStyle.overflow}`)
      if (aOverflow !== bOverflow) return Number(bOverflow) - Number(aOverflow)
      return scrollDelta(b) - scrollDelta(a)
    })[0] || null
  }

  const isDocumentScroller = (el) => (
    el === document.scrollingElement || el === document.documentElement || el === document.body
  )

  const setScrollTop = (scrollRoot, top) => {
    const nextTop = Math.max(0, Math.round(top))
    if (isDocumentScroller(scrollRoot)) {
      window.scrollTo(0, nextTop)
    }
    scrollRoot.scrollTop = nextTop
    scrollRoot.dispatchEvent(new Event('scroll', { bubbles: true }))
  }

  const waitForScroll = async (scrollRoot, top) => {
    const target = Math.max(0, Math.round(top))
    setScrollTop(scrollRoot, target)
    // 等待飞书虚拟列表完成 scroll 事件、布局和网络后的 DOM 更新。
    for (let i = 0; i < 8; i += 1) {
      await sleep(45)
      if (Math.abs(scrollRoot.scrollTop - target) <= 8) break
    }
    await sleep(180)
  }

  const mergeSnapshots = (snapshots) => {
    const merged = []
    for (const snapshot of snapshots) {
      const lines = splitLines(snapshot)
      if (!lines.length) continue
      if (!merged.length) {
        merged.push(...lines)
        continue
      }

      // 相邻视口有重叠时，按最长的尾部/头部重叠拼接，避免固定窗口产生重复正文。
      const maxOverlap = Math.min(80, merged.length, lines.length)
      let overlap = 0
      for (let size = maxOverlap; size >= 1; size -= 1) {
        let same = true
        for (let i = 0; i < size; i += 1) {
          if (merged[merged.length - size + i] !== lines[i]) {
            same = false
            break
          }
        }
        if (same) {
          overlap = size
          break
        }
      }

      // 某些虚拟列表会在滚动时重复渲染固定标题，补一个小范围的首行定位兜底。
      if (!overlap) {
        const first = lines[0]
        const start = Math.max(0, merged.length - 120)
        const index = merged.lastIndexOf(first)
        if (index >= start) overlap = Math.min(lines.length, merged.length - index)
      }
      merged.push(...lines.slice(overlap))
    }
    return normalizeLines(merged.join('\n'))
  }

  const pageTitle = (textRoot) => {
    const heading = textRoot?.querySelector?.('h1, [role="heading"]')
    const visibleHeading = textOf(heading)
    if (visibleHeading) return visibleHeading.split('\n')[0].slice(0, 200)
    const title = document.title.replace(/\s*[-|｜]\s*(飞书|Lark).*$/i, '').trim()
    return title || '飞书 Brief'
  }

  const permissionError = (text) => {
    const value = String(text || '')
    if (/没有权限访问|无权访问|申请阅读权限|申请权限/.test(value)) {
      return '当前账号没有该飞书文档的阅读权限，请先在飞书中申请并获得批准'
    }
    return ''
  }

  async function extract(options = {}) {
    const textRoot = findTextRoot()
    const scrollRoot = findScrollRoot(textRoot)
    const originalTop = scrollRoot ? scrollRoot.scrollTop : 0
    const samples = []
    const fullScan = options.fullScan !== false
    let sampleCount = 0

    try {
      if (scrollRoot && fullScan) {
        // 飞书文档是虚拟滚动的：滚动到底部后 scrollHeight 可能继续变大。
        // 每一轮从顶部扫到当前底部，直到高度连续稳定，最多保护性地扫 6 轮。
        let stableRounds = 0
        for (let round = 0; round < 6 && stableRounds < 2; round += 1) {
          const heightAtRoundStart = scrollRoot.scrollHeight
          const viewport = Math.max(scrollRoot.clientHeight || window.innerHeight || 800, 400)
          const step = Math.max(Math.round(viewport * 0.65), 320)
          let top = 0

          while (sampleCount < 160) {
            await waitForScroll(scrollRoot, top)
            samples.push(textOf(textRoot))
            sampleCount += 1

            const maxTop = Math.max(0, scrollRoot.scrollHeight - scrollRoot.clientHeight)
            if (top >= maxTop - 8) break
            const nextTop = Math.min(maxTop, top + step)
            if (nextTop <= top) break
            top = nextTop
          }

          // 给懒加载请求一个额外稳定窗口，再重新读取高度。
          const maxTop = Math.max(0, scrollRoot.scrollHeight - scrollRoot.clientHeight)
          await waitForScroll(scrollRoot, maxTop)
          samples.push(textOf(textRoot))
          sampleCount += 1
          await sleep(320)

          const heightAfterRound = scrollRoot.scrollHeight
          if (heightAfterRound <= heightAtRoundStart + 8) {
            stableRounds += 1
          } else {
            stableRounds = 0
          }
        }
      } else {
        samples.push(textOf(textRoot))
      }
    } finally {
      if (scrollRoot) setScrollTop(scrollRoot, originalTop)
    }

    const rawText = mergeSnapshots(samples)
    const accessError = permissionError(rawText)
    if (accessError) return { ok: false, error: accessError }
    if (rawText.length < 20) {
      return {
        ok: false,
        error: '没有提取到足够的正文。请确认页面已完全加载，并且当前账号可以阅读该文档'
      }
    }

    return {
      ok: true,
      title: pageTitle(textRoot),
      sourceUrl: window.location.href,
      rawText,
      markdown: rawText,
      charCount: rawText.length,
      method: fullScan && scrollRoot ? 'visible-page-text-full-scan' : 'visible-page-text',
      scan: scrollRoot ? {
        samples: sampleCount,
        scrollHeight: scrollRoot.scrollHeight,
      } : undefined,
    }
  }

  window.__gzhFeishuExtractor = { extract }
})()
