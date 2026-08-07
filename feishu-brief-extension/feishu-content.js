// 注入飞书 / Lark 页面：接收后台提取命令并返回当前用户可见的正文。
(function installFeishuContentBridge() {
  const extractor = () => window.__gzhFeishuExtractor

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || message.channel !== 'gzh-feishu-brief') return false

    if (message.type === 'ping') {
      sendResponse({ ok: true, type: 'ready' })
      return false
    }

    if (message.type !== 'extract-current') return false
    const instance = extractor()
    if (!instance?.extract) {
      sendResponse({ ok: false, error: '提取器尚未加载，请刷新飞书页面后重试' })
      return false
    }

    instance.extract({ fullScan: message.fullScan !== false })
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: error?.message || '提取失败' }))
    return true
  })
})()
