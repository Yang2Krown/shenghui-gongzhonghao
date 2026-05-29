"""
小红书 CDP 调试端点 — 用于排查页面结构变化
"""
import asyncio
import logging

from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/page-dump")
async def page_dump(
    current_user: User = Depends(get_current_user),
):
    """导航到小红书发布页，点击写长文 tab，返回页面可见文本和按钮"""
    from app.services.xhs_publisher import ensure_chrome, XiaohongshuPublisher, CDPError
    import time

    def _run():
        ensure_chrome(headless=False)
        pub = XiaohongshuPublisher()
        pub.connect()

        # 导航
        pub._navigate("https://creator.xiaohongshu.com/publish/publish")
        time.sleep(3)

        # 拿当前 URL
        url = pub._evaluate("window.location.href")

        # 收集所有 tab 文本
        tabs = pub._evaluate("""
            (function() {
                var tabs = document.querySelectorAll('div.creator-tab');
                return Array.from(tabs).map(t => t.textContent.trim());
            })();
        """)

        # 点击写长文 tab
        pub._click_long_article_tab()
        time.sleep(3)

        url_after = pub._evaluate("window.location.href")

        # 收集页面上所有可点击元素的文本
        clickables = pub._evaluate("""
            (function() {
                var sels = 'button, [role="button"], a, [class*="btn"], [class*="creation"], [class*="new"]';
                var elems = document.querySelectorAll(sels);
                var result = [];
                for (var i = 0; i < elems.length; i++) {
                    var t = elems[i].textContent.trim();
                    var tag = elems[i].tagName;
                    var cls = elems[i].className || '';
                    if (t) result.push({text: t.substring(0, 80), tag: tag, class: cls.substring(0, 100)});
                }
                return result;
            })();
        """)

        # 检查是否已经有编辑器
        has_title_input = pub._evaluate("!!document.querySelector('textarea.d-text[placeholder=\"输入标题\"]')")
        has_editor = pub._evaluate("!!document.querySelector('div.tiptap.ProseMirror')")

        # 收集页面所有文本节点中包含"创作"或"新"的
        creation_texts = pub._evaluate("""
            (function() {
                var all = document.querySelectorAll('*');
                var result = [];
                for (var i = 0; i < all.length; i++) {
                    var t = all[i].textContent.trim();
                    if (t.length < 50 && (t.indexOf('创作') >= 0 || t.indexOf('新的') >= 0 || t.indexOf('开始') >= 0)) {
                        var tag = all[i].tagName;
                        var cls = all[i].className || '';
                        result.push({text: t, tag: tag, class: cls.substring(0, 80)});
                    }
                }
                return result.slice(0, 30);
            })();
        """)

        pub.disconnect()
        return {
            "url_before": url,
            "url_after": url_after,
            "tabs": tabs,
            "has_title_input": has_title_input,
            "has_editor": has_editor,
            "clickables": clickables[:30],
            "creation_texts": creation_texts,
        }

    result = await asyncio.to_thread(_run)
    return {"code": 200, "data": result}
