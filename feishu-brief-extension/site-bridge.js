// 站点桥接：让网站页面用 window.postMessage 调用扩展，不需要硬编码扩展 ID。
(function installSiteBridge() {
  const CHANNEL = 'gzh-feishu-brief'
  const allowedTypes = new Set(['ping', 'extract-current'])

  const postToPage = (message) => {
    window.postMessage({ __gzhFeishuBrief: true, dir: 'to-page', ...message }, '*')
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window) return
    const message = event.data
    if (!message || message.__gzhFeishuBrief !== true || message.dir !== 'to-ext') return
    if (!allowedTypes.has(message.type)) return

    chrome.runtime.sendMessage(
      { channel: CHANNEL, type: message.type, payload: message.payload || {} },
      (response) => {
        if (chrome.runtime.lastError) {
          postToPage({ type: 'error', error: chrome.runtime.lastError.message })
          return
        }
        if (response) postToPage(response)
      }
    )
  })

  chrome.runtime.onMessage.addListener((message) => {
    if (!message || message.channel !== CHANNEL) return
    postToPage(message)
  })

  postToPage({ type: 'ready' })
})()
