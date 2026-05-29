// 在小红书页面的 MAIN world 执行：直接访问 TipTap 编辑器实例 (pm.editor)，
// 完成 新建/填标题/填正文/插图/一键排版/选模板/下一步/填描述。
// 由 background.js 通过 chrome.scripting.executeScript({world:'MAIN'}) 注入并逐步调用。
// 这里不能使用任何 chrome.* API（MAIN world 没有）。图片字节由后台 fetch 后以 base64 传入。

(function () {
  if (window.__gzhXhs) return; // 防重复注入

  const SEL = {
    editor: 'div.tiptap.ProseMirror',
    editorAlt: 'div.ProseMirror[contenteditable="true"]',
    title: 'textarea.d-text[placeholder="输入标题"]',
    newCreation: '新的创作',
    autoFormat: '一键排版',
    nextStep: '下一步',
    templateCard: '.template-card-new, .template-card',
    publishBtn: '发布',
  };
  // 图片按钮图标的 SVG path 指纹（风景图标里的“太阳”圆形）
  const IMG_ICON_SIG = 'M6.91635 8.25017';

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function editor() {
    const pm = document.querySelector(SEL.editor) || document.querySelector(SEL.editorAlt);
    return pm && pm.editor ? pm.editor : null;
  }

  function fireClick(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    const base = { bubbles: true, cancelable: true, view: window,
                   clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 };
    ['pointerover', 'pointerenter', 'pointerdown', 'mousedown',
     'pointerup', 'mouseup', 'click'].forEach((t) => {
      try {
        const Ev = (t.indexOf('pointer') === 0 && window.PointerEvent) ? PointerEvent : MouseEvent;
        el.dispatchEvent(new Ev(t, base));
      } catch (e) {
        try { el.dispatchEvent(new MouseEvent(t.replace('pointer', 'mouse'), base)); } catch (e2) {}
      }
    });
    return true;
  }

  function clickByText(text) {
    const els = document.querySelectorAll('button, [role="button"], span, div, a, [class*="btn"]');
    for (const el of els) {
      if (el.textContent.trim() === text) { fireClick(el); return true; }
    }
    return false;
  }

  function installHook() {
    if (window.__xhsHookInstalled) return;
    window.__xhsHookInstalled = true;
    window.__xhsCapturedInput = null;
    const origCreate = document.createElement.bind(document);
    document.createElement = function (tag) {
      const el = origCreate(tag);
      try {
        if (String(tag).toLowerCase() === 'input') {
          const origClick = el.click.bind(el);
          el.click = function () {
            if (el.type === 'file' && /image/i.test(el.accept || '')) {
              window.__xhsCapturedInput = el;
              return; // 阻止系统选文件框
            }
            return origClick();
          };
        }
      } catch (e) {}
      return el;
    };
  }

  function findImageBtnIndex() {
    const btns = document.querySelectorAll('button.menu-item');
    for (let i = 0; i < btns.length; i++) {
      const p = btns[i].querySelector('svg path');
      if (p && (p.getAttribute('d') || '').indexOf(IMG_ICON_SIG) === 0) return i;
    }
    return btns.length >= 3 ? btns.length - 3 : -1; // 兜底：右数第 3 个
  }

  function imageCount() {
    const ed = editor();
    if (!ed) return 0;
    let c = 0;
    ed.state.doc.descendants((n) => { if (n.type.name === 'image') c++; });
    return c;
  }

  function setSelectionAfterPara(k) {
    const ed = editor();
    if (!ed) return;
    let pos = null, count = 0;
    if (k <= 0) { pos = 1; }
    else {
      ed.state.doc.forEach((node, offset) => {
        if (node.type.name === 'paragraph') {
          count++;
          if (count === k) pos = offset + node.nodeSize - 1;
        }
      });
    }
    if (pos === null) pos = Math.max(0, ed.state.doc.content.size - 1);
    ed.commands.focus();
    ed.commands.setTextSelection(pos);
  }

  function b64ToFile(b64, mime, name) {
    const bin = atob(b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    return new File([arr], name || 'image', { type: mime || 'image/jpeg' });
  }

  // ---- 对外暴露的步骤函数（均返回 JSON 可序列化结果）----
  window.__gzhXhs = {
    async waitReady(timeoutMs = 20000) {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        if (document.querySelector(SEL.title) && editor()) return { ok: true };
        await sleep(400);
      }
      return { ok: false, error: 'editor_not_ready' };
    },

    async startArticle() {
      // 若有「新的创作」按钮先点
      clickByText(SEL.newCreation);
      await sleep(1500);
      return this.waitReady();
    },

    fillTitle(title) {
      const el = document.querySelector(SEL.title);
      if (!el) return { ok: false, error: 'no_title_input' };
      const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
      el.focus();
      setter.call(el, title);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return { ok: true };
    },

    fillText(paragraphs) {
      const ed = editor();
      if (!ed) return { ok: false, error: 'no_editor' };
      const nodes = (paragraphs || [])
        .filter((p) => p && p.trim())
        .map((p) => ({ type: 'paragraph', content: [{ type: 'text', text: p }] }));
      if (nodes.length === 0) return { ok: true, empty: true };
      ed.commands.setContent({ type: 'doc', content: nodes });
      return { ok: true, paragraphs: nodes.length };
    },

    prepareImages() {
      installHook();
      const idx = findImageBtnIndex();
      return { ok: idx >= 0, index: idx };
    },

    async uploadImage({ base64, mime, filename, paraIndex, imgBtnIndex }) {
      const ed = editor();
      if (!ed) return { ok: false, error: 'no_editor' };
      installHook();
      const idx = (typeof imgBtnIndex === 'number' && imgBtnIndex >= 0) ? imgBtnIndex : findImageBtnIndex();
      if (idx < 0) return { ok: false, error: 'no_image_button' };

      setSelectionAfterPara(paraIndex || 0);
      const before = imageCount();

      window.__xhsCapturedInput = null;
      const btns = document.querySelectorAll('button.menu-item');
      if (!btns[idx]) return { ok: false, error: 'image_button_gone' };
      fireClick(btns[idx]);

      // 等待小红书创建出 file 输入框
      let input = null;
      for (let i = 0; i < 20; i++) {
        await sleep(150);
        if (window.__xhsCapturedInput) { input = window.__xhsCapturedInput; break; }
      }
      if (!input) return { ok: false, error: 'file_input_not_captured' };

      // 在页面realm构造 File 并塞进输入框
      try {
        const file = b64ToFile(base64, mime, filename);
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      } catch (e) {
        return { ok: false, error: 'set_files_failed: ' + (e && e.message) };
      }

      // 轮询编辑器图片节点 +1（小红书上传完成后会插入 image 节点）
      for (let i = 0; i < 40; i++) {
        await sleep(500);
        if (imageCount() > before) {
          window.__xhsCapturedInput = null;
          return { ok: true };
        }
      }
      window.__xhsCapturedInput = null;
      return { ok: false, error: 'image_node_not_appeared' };
    },

    async autoFormat() {
      const ok = clickByText(SEL.autoFormat);
      if (!ok) return { ok: false, error: 'no_auto_format_button' };
      await sleep(8000);
      return { ok: true };
    },

    async getTemplates(timeoutMs = 15000) {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        const cards = document.querySelectorAll(SEL.templateCard);
        if (cards.length > 0) {
          const names = [];
          cards.forEach((c) => {
            const t = c.querySelector('.template-title');
            names.push(t ? t.textContent.trim() : '');
          });
          return { ok: true, templates: names.filter(Boolean) };
        }
        await sleep(500);
      }
      return { ok: false, error: 'no_templates', templates: [] };
    },

    selectTemplate(name) {
      const cards = document.querySelectorAll(SEL.templateCard);
      for (const c of cards) {
        const t = c.querySelector('.template-title');
        if (t && t.textContent.trim() === name) { fireClick(c); return { ok: true }; }
      }
      return { ok: false, error: 'template_not_found' };
    },

    async nextStep() {
      const ok = clickByText(SEL.nextStep);
      if (!ok) return { ok: false, error: 'no_next_step_button' };
      await sleep(2500);
      return { ok: true };
    },

    fillDescription(text) {
      // 发布页有独立的正文描述编辑器（同样是 ProseMirror）
      const ed = editor();
      if (!ed) return { ok: false, error: 'no_desc_editor' };
      const paras = (text || '').split('\n').filter((p) => p.trim());
      const nodes = paras.map((p) => ({ type: 'paragraph', content: [{ type: 'text', text: p }] }));
      if (nodes.length) ed.commands.setContent({ type: 'doc', content: nodes });
      return { ok: true };
    },

    publish() {
      // v1 默认不自动发布；保留此函数供将来使用
      const ok = clickByText(SEL.publishBtn);
      return { ok };
    },
  };
})();
