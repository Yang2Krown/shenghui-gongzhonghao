// 桥接脚本：注入到「你的网页」上，在网页 (window.postMessage) 和插件后台
// (chrome.runtime) 之间转发消息。这样网页不用硬编码插件 ID。
//
// 网页 → 插件：window.postMessage({ __gzhXhs: true, dir: 'to-ext', type, payload }, '*')
// 插件 → 网页：window.postMessage({ __gzhXhs: true, dir: 'to-page', type, ... }, '*')

(function () {
  // 网页发来的消息 → 转给后台
  window.addEventListener('message', (event) => {
    if (event.source !== window) return;
    const msg = event.data;
    if (!msg || msg.__gzhXhs !== true || msg.dir !== 'to-ext') return;

    chrome.runtime.sendMessage(
      { type: msg.type, payload: msg.payload },
      (resp) => {
        // 同步回执（可选）
        if (chrome.runtime.lastError) {
          window.postMessage(
            { __gzhXhs: true, dir: 'to-page', type: 'error', error: chrome.runtime.lastError.message },
            '*'
          );
          return;
        }
        if (resp) {
          window.postMessage({ __gzhXhs: true, dir: 'to-page', ...resp }, '*');
        }
      }
    );
  });

  // 后台主动推来的进度/事件 → 转给网页
  chrome.runtime.onMessage.addListener((msg) => {
    if (!msg || msg.__gzhXhs !== true) return;
    window.postMessage({ ...msg, dir: 'to-page' }, '*');
  });

  // 让网页知道插件已就绪（网页可据此显示「插件已安装」）
  window.postMessage({ __gzhXhs: true, dir: 'to-page', type: 'ready' }, '*');
})();
