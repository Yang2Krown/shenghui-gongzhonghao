// 后台 service worker：编排整个发布流程。
// 1) 收网页指令  2) 打开/复用小红书标签页  3) 后台 fetch 图片(绕过 CORS)
// 4) 在小红书页 MAIN world 逐步执行(注入 publish-main.js)  5) 把进度推回网页。

const XHS_ARTICLE_URL =
  'https://creator.xiaohongshu.com/publish/publish?from=tab_switch&target=article';

// 记录发起请求的网页标签页，用于回推进度；以及待选模板阶段的上下文
let state = { webTabId: null, xhsTabId: null, description: '' };

function toPage(msg) {
  if (state.webTabId != null) {
    chrome.tabs.sendMessage(state.webTabId, { __gzhXhs: true, ...msg }).catch(() => {});
  }
}
function progress(step, detail) {
  toPage({ type: 'progress', step, detail: detail || '' });
}

function waitTabComplete(tabId, timeoutMs = 20000) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => { if (!done) { done = true; chrome.tabs.onUpdated.removeListener(listener); resolve(); } };
    function listener(id, info) { if (id === tabId && info.status === 'complete') finish(); }
    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.get(tabId, (t) => { if (t && t.status === 'complete') setTimeout(finish, 800); });
    setTimeout(finish, timeoutMs);
  });
}

async function openXhsTab() {
  const tabs = await chrome.tabs.query({ url: 'https://creator.xiaohongshu.com/*' });
  let tab;
  if (tabs.length) {
    tab = tabs[0];
    await chrome.tabs.update(tab.id, { active: true, url: XHS_ARTICLE_URL });
  } else {
    tab = await chrome.tabs.create({ url: XHS_ARTICLE_URL, active: true });
  }
  await waitTabComplete(tab.id);
  await new Promise((r) => setTimeout(r, 1500));
  return tab.id;
}

// 在小红书标签页 MAIN world 调用 window.__gzhXhs[fn](arg)
async function callMain(tabId, fn, arg) {
  const res = await chrome.scripting.executeScript({
    target: { tabId },
    world: 'MAIN',
    func: (fnName, a) => window.__gzhXhs[fnName](a),
    args: [fn, arg === undefined ? null : arg],
  });
  return res && res[0] ? res[0].result : null;
}

async function fetchAsBase64(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error('fetch ' + resp.status);
  const buf = await resp.arrayBuffer();
  const mime = resp.headers.get('content-type') || 'image/jpeg';
  const bytes = new Uint8Array(buf);
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return { base64: btoa(binary), mime };
}

function parseBlocks(blocks) {
  const paragraphs = [];
  const images = [];
  let paraBefore = 0;
  for (const b of blocks || []) {
    if (b.type === 'text' && (b.content || '').trim()) {
      const lines = b.content.split('\n').filter((l) => l.trim());
      lines.forEach((l) => paragraphs.push(l));
      paraBefore += lines.length;
    } else if (b.type === 'image' && b.url) {
      const fname = (b.url.split('/').pop() || 'image').split('?')[0] || 'image';
      images.push({ url: b.url, alt: b.alt || '', paraIndex: paraBefore, filename: fname });
    }
  }
  return { paragraphs, images };
}

async function runPublish(payload) {
  const { title, blocks, description } = payload;
  state.description = description || '';
  const { paragraphs, images } = parseBlocks(blocks);

  progress('open', '打开小红书发布页…');
  const tabId = await openXhsTab();
  state.xhsTabId = tabId;

  await chrome.scripting.executeScript({ target: { tabId }, world: 'MAIN', files: ['publish-main.js'] });

  progress('start', '进入长文编辑器…');
  const start = await callMain(tabId, 'startArticle');
  if (!start || !start.ok) throw new Error('编辑器未就绪: ' + (start && start.error));

  progress('title', '填写标题…');
  await callMain(tabId, 'fillTitle', title || '无标题');

  progress('text', '填写正文…');
  await callMain(tabId, 'fillText', paragraphs);

  // 图片：逆序插入（先插靠后的，保证前面段落定位不被影响）
  let imgBtnIndex = -1;
  if (images.length) {
    const prep = await callMain(tabId, 'prepareImages');
    imgBtnIndex = prep && prep.ok ? prep.index : -1;
    if (imgBtnIndex < 0) {
      progress('image', '未找到图片按钮，跳过插图');
    } else {
      const ordered = [...images].sort((a, b) => b.paraIndex - a.paraIndex);
      let ok = 0;
      for (let i = 0; i < ordered.length; i++) {
        const img = ordered[i];
        progress('image', `上传图片 ${i + 1}/${ordered.length}…`);
        try {
          const { base64, mime } = await fetchAsBase64(img.url);
          const r = await callMain(tabId, 'uploadImage', {
            base64, mime, filename: img.filename, paraIndex: img.paraIndex, imgBtnIndex,
          });
          if (r && r.ok) ok++;
          else progress('image', `第 ${i + 1} 张失败: ${r && r.error}`);
        } catch (e) {
          progress('image', `第 ${i + 1} 张异常: ${e.message}`);
        }
      }
      progress('image', `图片完成 ${ok}/${ordered.length}`);
    }
  }

  progress('format', '一键排版…');
  const fmt = await callMain(tabId, 'autoFormat');
  if (!fmt || !fmt.ok) throw new Error('一键排版失败: ' + (fmt && fmt.error));

  progress('templates', '读取模板…');
  const tpl = await callMain(tabId, 'getTemplates');
  toPage({ type: 'templates', templates: (tpl && tpl.templates) || [] });
}

async function runSelectTemplate(name) {
  const tabId = state.xhsTabId;
  if (!tabId) throw new Error('会话已失效，请重新发起');
  progress('template', `应用模板「${name}」…`);
  const sel = await callMain(tabId, 'selectTemplate', name);
  if (!sel || !sel.ok) throw new Error('选择模板失败: ' + (sel && sel.error));

  progress('next', '进入发布页…');
  await callMain(tabId, 'nextStep');
  await callMain(tabId, 'fillDescription', state.description || '');

  // 安全起见 v1 不自动发布，提示用户自行确认
  toPage({ type: 'prepared' });
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (sender.tab) state.webTabId = sender.tab.id;

  if (msg.type === 'publish') {
    runPublish(msg.payload || {}).catch((e) => toPage({ type: 'error', error: e.message }));
    sendResponse({ type: 'accepted' });
  } else if (msg.type === 'selectTemplate') {
    runSelectTemplate((msg.payload || {}).name).catch((e) => toPage({ type: 'error', error: e.message }));
    sendResponse({ type: 'accepted' });
  } else if (msg.type === 'ping') {
    sendResponse({ type: 'pong' });
  }
  return false;
});
