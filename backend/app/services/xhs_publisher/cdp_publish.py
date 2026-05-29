"""
CDP-based Xiaohongshu publisher.
Adapted from post-to-xhs skill for backend integration.
"""

import json
import os
import time
import sys
from typing import Any, Optional

import requests
import websockets.sync.client as ws_client

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222

XHS_CREATOR_URL = "https://creator.xiaohongshu.com/publish/publish"
XHS_ARTICLE_URL = "https://creator.xiaohongshu.com/publish/publish?from=tab_switch&target=article"
XHS_HOME_URL = "https://www.xiaohongshu.com"
XHS_LOGIN_CHECK_URL = "https://creator.xiaohongshu.com"

SELECTORS = {
    "image_text_tab": "div.creator-tab",
    "image_text_tab_text": "上传图文",
    "upload_input": "input.upload-input",
    "upload_input_alt": 'input[type="file"]',
    "title_input": 'input[placeholder*="填写标题"]',
    "title_input_alt": "input.d-text",
    "content_editor": "div.tiptap.ProseMirror",
    "content_editor_alt": 'div.ProseMirror[contenteditable="true"]',
    "publish_button_text": "发布",
    "login_indicator": '.user-info, .creator-header, [class*="user"]',
    "long_article_tab_text": "写长文",
    "new_creation_btn_text": "新的创作",
    "long_title_input": 'textarea.d-text[placeholder="输入标题"]',
    "auto_format_btn_text": "一键排版",
    "next_step_btn_text": "下一步",
    "template_card": ".template-card-new, .template-card",
}

PAGE_LOAD_WAIT = 3
TAB_CLICK_WAIT = 2
UPLOAD_WAIT = 6
ACTION_INTERVAL = 1
AUTO_FORMAT_WAIT = 8
TEMPLATE_WAIT = 15


class CDPError(Exception):
    pass


class XiaohongshuPublisher:
    def __init__(self, host: str = CDP_HOST, port: int = CDP_PORT):
        self.host = host
        self.port = port
        self.ws = None
        self._msg_id = 0

    def _get_targets(self) -> list:
        url = f"http://{self.host}:{self.port}/json"
        for attempt in range(2):
            try:
                resp = requests.get(url, timeout=5)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                if attempt == 0:
                    print(f"[cdp_publish] CDP connection failed ({e}), restarting Chrome...")
                    from app.services.xhs_publisher.chrome_launcher import ensure_chrome
                    ensure_chrome(self.port)
                    time.sleep(2)
                else:
                    raise CDPError(f"Cannot reach Chrome on {self.host}:{self.port}: {e}")

    def _find_or_create_tab(self, target_url_prefix: str = "") -> str:
        targets = self._get_targets()
        pages = [t for t in targets if t.get("type") == "page"]

        if target_url_prefix:
            for t in pages:
                if t.get("url", "").startswith(target_url_prefix):
                    return t["webSocketDebuggerUrl"]

        resp = requests.put(f"http://{self.host}:{self.port}/json/new?{XHS_CREATOR_URL}", timeout=5)
        if resp.ok:
            return resp.json().get("webSocketDebuggerUrl", "")

        if pages:
            return pages[0]["webSocketDebuggerUrl"]

        raise CDPError("No browser tabs available.")

    def connect(self, target_url_prefix: str = ""):
        ws_url = self._find_or_create_tab(target_url_prefix)
        if not ws_url:
            raise CDPError("Could not obtain WebSocket URL for any tab.")
        self.ws = ws_client.connect(ws_url)

    def disconnect(self):
        if self.ws:
            self.ws.close()
            self.ws = None

    def _send(self, method: str, params: Optional[dict] = None) -> dict:
        if not self.ws:
            raise CDPError("Not connected.")
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))
        while True:
            raw = self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == self._msg_id:
                if "error" in data:
                    raise CDPError(f"CDP error: {data['error']}")
                return data.get("result", {})

    def _evaluate(self, expression: str) -> Any:
        result = self._send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        remote_obj = result.get("result", {})
        if remote_obj.get("subtype") == "error":
            raise CDPError(f"JS error: {remote_obj.get('description', remote_obj)}")
        return remote_obj.get("value")

    def _navigate(self, url: str):
        self._send("Page.enable")
        self._send("Page.navigate", {"url": url})
        time.sleep(PAGE_LOAD_WAIT)

    def check_login(self) -> bool:
        self._navigate(XHS_LOGIN_CHECK_URL)
        time.sleep(2)
        current_url = self._evaluate("window.location.href")
        if "login" in current_url.lower():
            return False
        return True

    def clear_cookies(self):
        self._send("Network.enable")
        self._send("Network.clearBrowserCookies")
        self._send("Storage.clearDataForOrigin", {
            "origin": "https://www.xiaohongshu.com",
            "storageTypes": "cookies,local_storage,session_storage",
        })
        self._send("Storage.clearDataForOrigin", {
            "origin": "https://creator.xiaohongshu.com",
            "storageTypes": "cookies,local_storage,session_storage",
        })

    def open_login_page(self):
        self._navigate(XHS_LOGIN_CHECK_URL)
        time.sleep(2)
        current_url = self._evaluate("window.location.href")
        if "login" not in current_url.lower():
            self._navigate("https://creator.xiaohongshu.com/login")
            time.sleep(2)

    def _fill_content(self, content: str):
        time.sleep(ACTION_INTERVAL)
        for selector in (SELECTORS["content_editor"], SELECTORS["content_editor_alt"]):
            found = self._evaluate(f"!!document.querySelector('{selector}')")
            if found:
                escaped = json.dumps(content)
                self._evaluate(f"""
                    (function() {{
                        var el = document.querySelector('{selector}');
                        el.focus();
                        var text = {escaped};
                        var paragraphs = text.split('\\n').filter(function(p) {{ return p.trim(); }});
                        var html = [];
                        for (var i = 0; i < paragraphs.length; i++) {{
                            html.push('<p>' + paragraphs[i] + '</p>');
                            if (i < paragraphs.length - 1) {{
                                html.push('<p><br></p>');
                            }}
                        }}
                        el.innerHTML = html.join('');
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }})();
                """)
                return
        raise CDPError("Could not find content editor element.")

    def _fill_text_from_blocks(self, blocks: list):
        """Fill only the text paragraphs from blocks via TipTap setContent (no images)."""
        time.sleep(ACTION_INTERVAL)
        found = self._evaluate(
            f"!!document.querySelector('{SELECTORS['content_editor']}')"
        )
        if not found:
            raise CDPError("Could not find content editor element.")

        nodes = []
        for block in blocks:
            if block.get("type") == "text" and block.get("content", "").strip():
                for line in block["content"].split("\n"):
                    line = line.strip()
                    if line:
                        nodes.append({"type": "paragraph", "content": [{"type": "text", "text": line}]})

        if not nodes:
            return

        doc = {"type": "doc", "content": nodes}
        escaped_doc = json.dumps(json.dumps(doc))

        self._evaluate(f"""
            (function() {{
                var pm = document.querySelector('{SELECTORS["content_editor"]}');
                if (!pm || !pm.editor) return false;
                pm.editor.commands.setContent(JSON.parse({escaped_doc}));
                return true;
            }})();
        """)

    # ------------------------------------------------------------------
    # 图片上传：走小红书工具栏「图片」按钮 → 拦截临时 file 输入框 →
    # CDP setFileInputFiles → 小红书自己上传到 ros-preview.xhscdn.com 并插入
    # 正确的 image 节点（attrs.imgs[].src）。必须在「一键排版」之前完成。
    # ------------------------------------------------------------------

    def _install_image_capture_hook(self):
        """劫持 document.createElement：小红书点图片按钮时会创建临时 <input type=file>
        并调用 .click() 弹系统选框。我们把这个 click 改成空操作，并把该 input 挂到
        body、打上固定 id，供 CDP setFileInputFiles 使用。"""
        self._send("DOM.enable")
        self._evaluate("""
            (function(){
                if (window.__xhsHookInstalled) return;
                window.__xhsHookInstalled = true;
                window.__xhsCapturedInput = null;
                var origCreate = document.createElement.bind(document);
                document.createElement = function(tag){
                    var el = origCreate(tag);
                    try {
                        if (String(tag).toLowerCase() === 'input') {
                            var origClick = el.click.bind(el);
                            el.click = function(){
                                if (el.type === 'file' && /image/i.test(el.accept || '')) {
                                    el.id = 'xhs-captured-file-input';
                                    el.style.display = 'none';
                                    if (!el.isConnected) document.body.appendChild(el);
                                    window.__xhsCapturedInput = el;
                                    return;  // 阻止弹出系统选文件框
                                }
                                return origClick();
                            };
                        }
                    } catch(e){}
                    return el;
                };
                // 完整鼠标事件序列点击：小红书按钮可能监听 pointerdown/mousedown，
                // 单纯 el.click() 只派发 click 事件，触发不了
                window.__xhsFireClick = function(el){
                    if (!el) return false;
                    var r = el.getBoundingClientRect();
                    var base = {bubbles:true, cancelable:true, view:window,
                                clientX:r.left + r.width/2, clientY:r.top + r.height/2};
                    ['pointerover','pointerenter','pointerdown','mousedown',
                     'pointerup','mouseup','click'].forEach(function(t){
                        try {
                            var Ev = (t.indexOf('pointer')===0 && window.PointerEvent) ? PointerEvent : MouseEvent;
                            el.dispatchEvent(new Ev(t, base));
                        } catch(e) {
                            try { el.dispatchEvent(new MouseEvent(t.replace('pointer','mouse'), base)); } catch(e2){}
                        }
                    });
                    return true;
                };
            })();
        """)

    def _image_node_count(self) -> int:
        return self._evaluate(f"""
            (function(){{
                var pm = document.querySelector('{SELECTORS["content_editor"]}');
                if (!pm || !pm.editor) return 0;
                var c = 0;
                pm.editor.state.doc.descendants(function(n){{ if (n.type.name === 'image') c++; }});
                return c;
            }})();
        """) or 0

    def _clear_captured_input(self):
        self._evaluate("""
            (function(){
                var el = document.getElementById('xhs-captured-file-input');
                if (el) el.remove();
                window.__xhsCapturedInput = null;
            })();
        """)

    # 图片按钮图标的 SVG path 指纹（风景图标里的"太阳"圆形），用于精确定位，
    # 不必盲点其它按钮（最右侧按钮疑似导出/退出，乱点危险）。
    IMAGE_ICON_PATH_SIG = "M6.91635 8.25017"

    def _find_image_button_index(self) -> int:
        """精确定位图片按钮：优先按图标 SVG path 指纹匹配，兜底用「从右数第 3 个」。"""
        idx = self._evaluate(f"""
            (function(){{
                var btns = document.querySelectorAll('button.menu-item');
                var SIG = {json.dumps(self.IMAGE_ICON_PATH_SIG)};
                for (var i = 0; i < btns.length; i++) {{
                    var p = btns[i].querySelector('svg path');
                    if (p && (p.getAttribute('d') || '').indexOf(SIG) === 0) return i;
                }}
                return btns.length >= 3 ? btns.length - 3 : -1;  // 兜底：右数第 3 个
            }})();
        """)
        idx = int(idx) if idx is not None and idx >= 0 else -1
        if idx >= 0:
            print(f"[XHS] 图片按钮 = menu-item[{idx}]")
        else:
            print("[XHS] 未能定位图片按钮")
        return idx

    def _set_selection_after_paragraph(self, para_index: int):
        """把光标放到第 para_index 个段落之后（para_index=0 表示文首），
        让小红书把图片插到这个位置。"""
        self._evaluate(f"""
            (function(){{
                var pm = document.querySelector('{SELECTORS["content_editor"]}');
                if (!pm || !pm.editor) return;
                var ed = pm.editor;
                var k = {para_index};
                var pos = null, count = 0;
                if (k <= 0) {{ pos = 1; }}
                else {{
                    ed.state.doc.forEach(function(node, offset){{
                        if (node.type.name === 'paragraph') {{
                            count++;
                            if (count === k) pos = offset + node.nodeSize - 1;
                        }}
                    }});
                }}
                if (pos === null) pos = Math.max(0, ed.state.doc.content.size - 1);
                ed.commands.focus();
                ed.commands.setTextSelection(pos);
            }})();
        """)

    def _upload_one_image(self, img_btn_index: int, abs_path: str, para_index: int) -> bool:
        """上传一张图：定位光标 → 点图片按钮 → 拦截 file 框 → setFileInputFiles →
        小红书自动上传并插入节点。轮询编辑器 image 节点数 +1 判定成功。"""
        self._set_selection_after_paragraph(para_index)
        before = self._image_node_count()

        self._clear_captured_input()
        self._evaluate(f"""
            (function(){{
                var btns = document.querySelectorAll('button.menu-item');
                if (btns[{img_btn_index}]) window.__xhsFireClick(btns[{img_btn_index}]);
            }})();
        """)
        time.sleep(0.4)

        self._send("DOM.enable")
        doc = self._send("DOM.getDocument")
        root_id = doc["root"]["nodeId"]
        res = self._send("DOM.querySelector", {"nodeId": root_id, "selector": "#xhs-captured-file-input"})
        node_id = res.get("nodeId", 0)
        if not node_id:
            print(f"[XHS] 未捕获到 file 输入框，跳过: {abs_path}")
            return False

        # setFileInputFiles 会原生触发 change 事件，小红书 onchange 处理器随即上传
        self._send("DOM.setFileInputFiles", {"nodeId": node_id, "files": [abs_path]})

        for _ in range(40):  # 最多等 20s
            time.sleep(0.5)
            if self._image_node_count() > before:
                self._clear_captured_input()
                return True
        self._clear_captured_input()
        return False

    def _resolve_image_abs_path(self, block: dict) -> Optional[str]:
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        for candidate in (block.get("local_path"), block.get("url")):
            if not candidate:
                continue
            if candidate.startswith("/uploads/") or (candidate.startswith("/") and not candidate.startswith("//")):
                p = os.path.join(backend_root, candidate.lstrip("/"))
                if os.path.isfile(p):
                    return p
            if os.path.isabs(candidate) and os.path.isfile(candidate):
                return candidate
        return None

    def insert_images_before_format(self, blocks: list, img_btn_index: int = -1):
        """在「一键排版」之前，按图片在原文中的位置，通过小红书工具栏逐张上传插入。
        只支持本地文件（小红书需要真实上传，外链不行）。
        img_btn_index 应在编辑器为空时探测好后传入；为 -1 时这里兜底探测一次。"""
        # 统计每张图前面有多少个文字段落（用于定位）
        images = []
        para_before = 0
        for b in blocks:
            if b.get("type") == "text" and b.get("content", "").strip():
                para_before += len([ln for ln in b["content"].split("\n") if ln.strip()])
            elif b.get("type") == "image":
                abs_path = self._resolve_image_abs_path(b)
                if abs_path:
                    images.append((para_before, abs_path))
                else:
                    print(f"[XHS] 图片本地文件未找到，跳过: {b.get('local_path') or b.get('url')}")

        if not images:
            print("[XHS] 没有可上传的本地图片")
            return

        print(f"[XHS] 准备上传 {len(images)} 张图片（排版前）")
        self._install_image_capture_hook()
        idx = img_btn_index
        if idx < 0:
            idx = self._find_image_button_index()
        if idx < 0:
            print("[XHS] 找不到图片按钮，放弃插图")
            return

        # 逆序插入（先插靠后的图），保证前面段落的位置不被已插入的图节点影响
        ok_count = 0
        for para_index, abs_path in sorted(images, key=lambda x: x[0], reverse=True):
            print(f"[XHS] 上传图片 (段落{para_index}后): {os.path.basename(abs_path)}")
            if self._upload_one_image(idx, abs_path, para_index):
                ok_count += 1
                print(f"[XHS]   ✓ 成功")
                time.sleep(0.5)
            else:
                print(f"[XHS]   ✗ 失败")
        print(f"[XHS] 图片上传完成: {ok_count}/{len(images)}")

    def _click_long_article_tab(self):
        tab_text = SELECTORS["long_article_tab_text"]
        selector = SELECTORS["image_text_tab"]
        clicked = self._evaluate(f"""
            (function() {{
                var tabs = document.querySelectorAll('{selector}[data-hp-bound]');
                if (!tabs.length) tabs = document.querySelectorAll('{selector}');
                for (var i = 0; i < tabs.length; i++) {{
                    if (tabs[i].textContent.trim() === '{tab_text}') {{
                        tabs[i].click();
                        return true;
                    }}
                }}
                return false;
            }})();
        """)
        if not clicked:
            raise CDPError(f"Could not find '{tab_text}' tab.")
        time.sleep(TAB_CLICK_WAIT)

    def _click_new_creation(self):
        btn_text = SELECTORS["new_creation_btn_text"]
        clicked = self._evaluate(f"""
            (function() {{
                var btns = document.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {{
                    if (btns[i].textContent.trim() === '{btn_text}') {{
                        btns[i].click();
                        return true;
                    }}
                }}
                var candidates = document.querySelectorAll(
                    '[role="button"], [class*="btn"], [class*="creation"], span, div, a'
                );
                for (var i = 0; i < candidates.length; i++) {{
                    if (candidates[i].textContent.trim() === '{btn_text}') {{
                        candidates[i].click();
                        return true;
                    }}
                }}
                return false;
            }})();
        """)
        if not clicked:
            raise CDPError(f"Could not find '{btn_text}' button.")
        time.sleep(PAGE_LOAD_WAIT)

    def _fill_long_title(self, title: str):
        time.sleep(ACTION_INTERVAL)
        selector = SELECTORS["long_title_input"]
        found = self._evaluate(f"!!document.querySelector('{selector}')")
        if not found:
            raise CDPError(f"Could not find long title textarea.")
        escaped_title = json.dumps(title)
        self._evaluate(f"""
            (function() {{
                var el = document.querySelector('{selector}');
                var nativeSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value'
                ).set;
                el.focus();
                nativeSetter.call(el, {escaped_title});
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }})();
        """)

    def _click_auto_format(self):
        btn_text = SELECTORS["auto_format_btn_text"]
        clicked = self._evaluate(f"""
            (function() {{
                var elems = document.querySelectorAll(
                    'button, [role="button"], span, div, a, [class*="btn"]'
                );
                for (var i = 0; i < elems.length; i++) {{
                    if (elems[i].textContent.trim() === '{btn_text}') {{
                        elems[i].click();
                        return true;
                    }}
                }}
                return false;
            }})();
        """)
        if not clicked:
            raise CDPError(f"Could not find '{btn_text}' button.")
        time.sleep(AUTO_FORMAT_WAIT)

    def _wait_for_templates(self) -> bool:
        selector = SELECTORS["template_card"]
        for _ in range(TEMPLATE_WAIT):
            found = self._evaluate(f"document.querySelectorAll('{selector}').length")
            if found and found > 0:
                return True
            time.sleep(1)
        return False

    def get_template_names(self) -> list:
        selector = SELECTORS["template_card"]
        names = self._evaluate(f"""
            (function() {{
                var cards = document.querySelectorAll('{selector}');
                var names = [];
                for (var i = 0; i < cards.length; i++) {{
                    var title = cards[i].querySelector('.template-title');
                    names.push(title ? title.textContent.trim() : 'Template ' + i);
                }}
                return names;
            }})();
        """)
        return names or []

    def select_template(self, name: str) -> bool:
        selector = SELECTORS["template_card"]
        clicked = self._evaluate(f"""
            (function() {{
                var cards = document.querySelectorAll('{selector}');
                for (var i = 0; i < cards.length; i++) {{
                    var title = cards[i].querySelector('.template-title');
                    if (title && title.textContent.trim() === {json.dumps(name)}) {{
                        cards[i].click();
                        return true;
                    }}
                }}
                return false;
            }})();
        """)
        if clicked:
            time.sleep(ACTION_INTERVAL)
        return bool(clicked)

    def _click_next_step(self):
        btn_text = SELECTORS["next_step_btn_text"]
        clicked = self._evaluate(f"""
            (function() {{
                var elems = document.querySelectorAll(
                    'button, [role="button"], span, div, a, [class*="btn"]'
                );
                for (var i = 0; i < elems.length; i++) {{
                    if (elems[i].textContent.trim() === '{btn_text}') {{
                        elems[i].click();
                        return true;
                    }}
                }}
                return false;
            }})();
        """)
        if not clicked:
            raise CDPError(f"Could not find '{btn_text}' button.")
        time.sleep(PAGE_LOAD_WAIT)

    def _click_publish(self):
        time.sleep(ACTION_INTERVAL)
        btn_text = SELECTORS["publish_button_text"]
        clicked = self._evaluate(f"""
            (function() {{
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {{
                    var t = buttons[i].textContent.trim();
                    if (t === '{btn_text}') {{
                        buttons[i].click();
                        return true;
                    }}
                }}
                var spans = document.querySelectorAll('.d-button-content .d-text, .d-button-content span');
                for (var i = 0; i < spans.length; i++) {{
                    if (spans[i].textContent.trim() === '{btn_text}') {{
                        var el = spans[i].closest('button, [role="button"], .d-button, [class*="btn"], [class*="button"]');
                        if (!el) el = spans[i].closest('.d-button-content');
                        if (!el) el = spans[i];
                        el.click();
                        return true;
                    }}
                }}
                return false;
            }})();
        """)
        if not clicked:
            raise CDPError("Could not find publish button.")

    def publish_long_article(self, title: str, content: str,
                             image_paths: Optional[list] = None,
                             blocks: Optional[list] = None) -> list:
        if not self.ws:
            raise CDPError("Not connected.")

        self._navigate(XHS_ARTICLE_URL)
        time.sleep(3)
        self._click_new_creation()
        self._fill_long_title(title)

        # 先探测图片按钮（此刻编辑器为空，探测副作用会被下面 setContent 覆盖）
        img_btn_index = -1
        if blocks and any(b.get("type") == "image" for b in blocks):
            self._install_image_capture_hook()
            img_btn_index = self._find_image_button_index()

        if blocks:
            self._fill_text_from_blocks(blocks)
        else:
            self._fill_content(content)

        # 排版前插入图片：此时只有 1 个编辑器，图片随后会被一键排版一起分页。
        # （一键排版会把正文拆成多个分页编辑器，排版后再插图会插错地方）
        if blocks and img_btn_index >= 0:
            self.insert_images_before_format(blocks, img_btn_index=img_btn_index)

        self._click_auto_format()
        self._wait_for_templates()
        return self.get_template_names()

    def click_next_and_prepare_publish(self, content: str = ""):
        self._click_next_step()
        if content:
            time.sleep(ACTION_INTERVAL)
            self._fill_content(content)
