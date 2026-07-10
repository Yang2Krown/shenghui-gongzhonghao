"""
链接内容提取服务
支持：小红书、微信公众号、抖音、知乎
"""
import asyncio
import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, unquote

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag
from app.core.url_security import UnsafeURL, resolve_redirect_url, validate_public_http_url

logger = logging.getLogger(__name__)

# User-Agent 模拟 - 参考保险 Agent 项目
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
)

WECHAT_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.42(0x18002a2e) "
    "NetType/WIFI Language/zh_CN"
)


def extract_url_from_text(text: str) -> Optional[str]:
    """从分享文本中提取 URL"""
    if not text:
        return None
    m = re.search(r'https?://[^\s]+', text)
    if m:
        return m.group(0).rstrip('.,;:!?。，；：！？')
    return None


def detect_platform(url: str) -> Optional[str]:
    """检测链接平台"""
    if not url:
        return None
    lower = url.lower()
    if 'xiaohongshu.com' in lower or 'xhslink.com' in lower:
        return 'xhs'
    if 'mp.weixin.qq.com' in lower or 'weixin.qq.com' in lower:
        return 'gzh'
    if 'douyin.com' in lower or 'iesdouyin.com' in lower or 'v.douyin.com' in lower:
        return 'douyin'
    if 'zhihu.com' in lower:
        return 'zhihu'
    return None


async def fetch_html(url: str, cookie: str = None, ua: str = None, referer: str = None) -> str:
    """获取网页 HTML"""
    headers = {
        "User-Agent": ua or CHROME_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    # 根据平台设置不同的 Referer
    if referer:
        headers["Referer"] = referer
    elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
        headers["Referer"] = "https://www.xiaohongshu.com/explore"
    elif 'mp.weixin.qq.com' in url or 'weixin.qq.com' in url:
        headers["Referer"] = "https://mp.weixin.qq.com/"
    elif 'douyin.com' in url or 'iesdouyin.com' in url:
        headers["Referer"] = "https://www.douyin.com/"
    else:
        headers["Referer"] = "https://www.google.com/"

    if cookie:
        headers["Cookie"] = cookie

    logger.info(f"正在获取链接: {url}")

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False, verify=False) as client:
        resp = await _get_with_checked_redirects(client, url, headers=headers)
        logger.info(f"响应状态码: {resp.status_code}")
        resp.raise_for_status()
        return resp.text


async def _get_with_checked_redirects(
    client: httpx.AsyncClient,
    url: str,
    headers: Optional[dict] = None,
    max_redirects: int = 5,
) -> httpx.Response:
    """GET a URL while validating the initial URL and every redirect target."""
    current_url = validate_public_http_url(url)
    for _ in range(max_redirects + 1):
        resp = await client.get(current_url, headers=headers)
        if resp.status_code not in {301, 302, 303, 307, 308}:
            return resp
        location = resp.headers.get("location")
        if not location:
            return resp
        current_url = resolve_redirect_url(current_url, location)
    raise UnsafeURL("链接重定向次数过多")


# ========== 小红书提取 ==========

INITIAL_STATE_PREFIX = "window.__INITIAL_STATE__="

async def extract_xhs(url: str, cookie: str = None) -> Dict[str, Any]:
    """
    提取小红书笔记内容
    :param url: 小红书链接
    :param cookie: 可选的 cookie
    :return: {title, content, author, tags, platform}
    """
    try:
        html = await fetch_html(url, cookie=cookie)
        logger.info(f"小红书 HTML 长度: {len(html)}")

        # 查找 window.__INITIAL_STATE__ 脚本
        script_text = _find_xhs_initial_state(html)
        if script_text:
            # 清理 JS 数据
            body = script_text[len(INITIAL_STATE_PREFIX):]
            # 移除控制字符
            body = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', body)
            # 移除末尾分号
            if body.endswith(';'):
                body = body[:-1]
            # 替换 undefined 为 null
            body = body.replace(':undefined', ':null').replace(': undefined', ': null')

            try:
                state = json.loads(body)
                return _parse_xhs_state(state, url)
            except json.JSONDecodeError as e:
                logger.warning(f"小红书 INITIAL_STATE JSON 解析失败: {e}")
                # 尝试用更宽松的方式提取
                return _parse_xhs_html(html, url)

        # 回退：正则提取
        result = _parse_xhs_html(html, url)
        logger.info(f"正则提取结果: title={result.get('title')[:50] if result.get('title') else ''}, content_len={len(result.get('content', ''))}")
        return result

    except httpx.HTTPStatusError as e:
        logger.error(f"小红书请求失败: {e.response.status_code}")
        return {"title": "", "content": f"请求失败，状态码: {e.response.status_code}，可能需要登录或链接已失效", "author": "", "tags": [], "platform": "xhs"}
    except Exception as e:
        logger.error(f"小红书提取失败: {e}")
        return {"title": "", "content": f"提取失败: {str(e)[:200]}", "author": "", "tags": [], "platform": "xhs"}


def _find_xhs_initial_state(html: str) -> Optional[str]:
    """从 HTML 中查找 window.__INITIAL_STATE__ 脚本"""
    for match in re.finditer(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
        text = match.group(1)
        if text and text.strip().startswith(INITIAL_STATE_PREFIX):
            return text.strip()
    return None


def _parse_xhs_state(state: dict, url: str) -> dict:
    """从 INITIAL_STATE 中提取笔记数据"""
    # 尝试不同路径
    note_data = None
    if 'note' in state and 'noteDetailMap' in state['note']:
        detail_map = state['note']['noteDetailMap']
        if detail_map:
            first_key = list(detail_map.keys())[0]
            note_data = detail_map[first_key].get('note', {})
    elif 'noteData' in state:
        note_data = state.get('noteData', {}).get('data', {}).get('noteData', {})

    if not note_data:
        return {"title": "", "content": "", "author": "", "tags": [], "platform": "xhs"}

    # 提取内容
    title = note_data.get('title', '') or note_data.get('desc', '')
    content = note_data.get('desc', '') or note_data.get('content', '')
    author = note_data.get('user', {}).get('nickname', '') if isinstance(note_data.get('user'), dict) else ''

    # 提取标签
    tags = []
    interact_info = note_data.get('interactInfo', {})
    if isinstance(interact_info, dict):
        tag_list = interact_info.get('tagList', [])
        if isinstance(tag_list, list):
            tags = [t.get('name', '') for t in tag_list if isinstance(t, dict) and t.get('name')]

    # 如果 title 和 content 相同，只保留一个
    if title == content:
        title = ''

    return {
        "title": title,
        "content": content,
        "author": author,
        "tags": tags,
        "platform": "xhs"
    }


def _parse_xhs_html(html: str, url: str) -> dict:
    """从 HTML 中正则提取小红书内容"""
    # 提取标题
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html)
    title = title_match.group(1).strip() if title_match else ''
    # 清理标题中的 " - 小红书" 后缀
    title = re.sub(r'\s*[-–—]\s*小红书\s*$', '', title)

    # 提取描述内容
    desc_match = re.search(r'content="([^"]*?)"', html)
    content = desc_match.group(1).strip() if desc_match else ''

    # 提取作者
    author = ''
    author_match = re.search(r'"nickname"\s*:\s*"([^"]+)"', html)
    if author_match:
        author = author_match.group(1)

    return {
        "title": title,
        "content": content,
        "author": author,
        "tags": [],
        "platform": "xhs"
    }


# ========== 微信公众号提取 ==========

async def extract_wechat(url: str, cookie: str = None) -> Dict[str, Any]:
    """
    提取微信公众号文章内容
    :param url: 公众号文章链接
    :param cookie: 可选的 cookie
    :return: {title, content, author, tags, platform}
    """
    try:
        # 清理 URL
        url = url.strip().split(' ')[0]

        # 验证域名
        parsed = urlparse(url)
        if not parsed.hostname or ('mp.weixin.qq.com' not in parsed.hostname and 'weixin.qq.com' not in parsed.hostname):
            return {"title": "", "content": "请输入有效的微信公众号链接", "author": "", "tags": [], "platform": "gzh"}

        html = await fetch_html(url, cookie=cookie, ua=WECHAT_UA)
        logger.info(f"公众号 HTML 长度: {len(html)}")

        # 检查文章是否失效
        if '该内容已被发布者删除' in html or 'global_error_msg' in html:
            return {"title": "", "content": "文章已失效或被删除", "author": "", "tags": [], "platform": "gzh"}

        # 提取标题
        title = _extract_wechat_var(html, 'msg_title') or ''
        if not title:
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html)
            title = title_match.group(1).strip() if title_match else ''

        # 提取作者/公众号名称
        author = _extract_wechat_var(html, 'nickname') or ''

        # 提取正文内容
        content = _extract_wechat_content(html)

        # 提取标签
        tags = []
        tag_matches = re.findall(r'#([^#]+)#', content)
        if tag_matches:
            tags = [t.strip() for t in tag_matches if t.strip()]
            # 从正文中移除标签格式
            for tag in tag_matches:
                content = content.replace(f'#{tag}#', '')

        logger.info(f"公众号提取结果: title={title[:50] if title else ''}, content_len={len(content)}")

        return {
            "title": title.strip(),
            "content": content.strip(),
            "author": author.strip(),
            "tags": tags,
            "platform": "gzh"
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"公众号请求失败: {e.response.status_code}")
        return {"title": "", "content": f"请求失败，状态码: {e.response.status_code}，可能需要登录或链接已失效", "author": "", "tags": [], "platform": "gzh"}
    except Exception as e:
        logger.error(f"公众号提取失败: {e}")
        return {"title": "", "content": f"提取失败: {str(e)[:200]}", "author": "", "tags": [], "platform": "gzh"}


async def extract_wechat_with_images(url: str, cookie: str = None) -> Dict[str, Any]:
    """
    提取微信公众号文章内容，包含图片及其在文中的位置。
    返回结构化的 blocks 列表，每个 block 为 text 或 image 类型。
    """
    try:
        url = url.strip().split(' ')[0]
        parsed = urlparse(url)
        if not parsed.hostname or ('mp.weixin.qq.com' not in parsed.hostname and 'weixin.qq.com' not in parsed.hostname):
            return {"title": "", "blocks": [], "author": "", "tags": [], "platform": "gzh", "error": "请输入有效的微信公众号链接"}

        html = await fetch_html(url, cookie=cookie, ua=WECHAT_UA)

        if '该内容已被发布者删除' in html or 'global_error_msg' in html:
            return {"title": "", "blocks": [], "author": "", "tags": [], "platform": "gzh", "error": "文章已失效或被删除"}

        title = _extract_wechat_var(html, 'msg_title') or ''
        if not title:
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html)
            title = title_match.group(1).strip() if title_match else ''

        author = _extract_wechat_var(html, 'nickname') or ''

        blocks = _extract_wechat_blocks(html)

        tags = []
        full_text = ' '.join(b['content'] for b in blocks if b['type'] == 'text')
        tag_matches = re.findall(r'#([^#]+)#', full_text)
        if tag_matches:
            tags = [t.strip() for t in tag_matches if t.strip()]

        logger.info(f"公众号图文提取: title={title[:50] if title else ''}, blocks={len(blocks)}, images={sum(1 for b in blocks if b['type'] == 'image')}")

        return {
            "title": title.strip(),
            "blocks": blocks,
            "author": author.strip(),
            "tags": tags,
            "platform": "gzh",
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"公众号请求失败: {e.response.status_code}")
        return {"title": "", "blocks": [], "author": "", "tags": [], "platform": "gzh", "error": f"请求失败，状态码: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"公众号图文提取失败: {e}")
        return {"title": "", "blocks": [], "author": "", "tags": [], "platform": "gzh", "error": f"提取失败: {str(e)[:200]}"}


def _extract_wechat_blocks(html: str) -> List[Dict[str, Any]]:
    """从公众号 HTML 中提取结构化的图文 blocks"""
    soup = BeautifulSoup(html, 'html.parser')
    content_div = soup.find('div', id='js_content')
    if not content_div:
        return []

    blocks: List[Dict[str, Any]] = []
    current_text_lines: List[str] = []

    def flush_text():
        text = '\n'.join(current_text_lines).strip()
        if text:
            blocks.append({"type": "text", "content": text})
        current_text_lines.clear()

    def walk(element):
        for child in element.children:
            if isinstance(child, NavigableString):
                text = child.strip()
                if text:
                    current_text_lines.append(text)
                continue

            if not isinstance(child, Tag):
                continue

            if child.name == 'img':
                img_url = child.get('data-src') or child.get('src') or ''
                if img_url and not img_url.startswith('data:'):
                    flush_text()
                    blocks.append({
                        "type": "image",
                        "url": img_url,
                        "alt": child.get('alt', ''),
                    })
                continue

            if child.name in ('p', 'div', 'section', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                inner_text = child.get_text(separator=' ', strip=True)
                inner_imgs = child.find_all('img')

                if not inner_imgs:
                    if inner_text:
                        current_text_lines.append(inner_text)
                else:
                    walk(child)

                if child.name in ('p', 'div', 'section', 'blockquote') and current_text_lines:
                    pass
                continue

            if child.name == 'br':
                continue

            walk(child)

    walk(content_div)
    flush_text()

    return blocks


def _extract_wechat_var(html: str, var_name: str) -> Optional[str]:
    """从 HTML 中提取微信内嵌 JS 变量 - 参考保险 Agent 项目"""
    # 使用更精确的正则表达式
    patterns = [
        # var msg_title = 'xxx' 或 var msg_title = "xxx"
        re.compile(rf"var\s+{var_name}\s*=\s*'((?:[^'\\]|\\.)*)'"),
        re.compile(rf'var\s+{var_name}\s*=\s*"((?:[^"\\]|\\.)*)"'),
        # htmlDecode("xxx") 格式
        re.compile(rf'{var_name}\s*=\s*htmlDecode\("((?:[^"\\]|\\.)*)"\)'),
    ]

    for pattern in patterns:
        match = pattern.search(html)
        if match:
            value = match.group(1)
            if value and value != 'undefined' and value != 'null':
                # 处理转义字符
                value = value.replace('\\\'', "'").replace('\\"', '"').replace('\\n', '\n')
                return unquote(value) if '%' in value else value
    return None


def _extract_wechat_content(html: str) -> str:
    """提取公众号正文内容 - 参考保险 Agent 项目"""
    # 尝试提取 #js_content 中的内容
    content_match = re.search(
        r'<div[^>]*id="js_content"[^>]*>(.*?)</div>\s*(?=<div[^>]*class="rich_media_tool"|<script)',
        html,
        re.DOTALL
    )

    if content_match:
        content_html = content_match.group(1)
        # 使用更精确的方式提取文本
        # 1. 先处理换行
        content = re.sub(r'<br\s*/?>', '\n', content_html)
        # 2. 处理段落
        content = re.sub(r'<p[^>]*>', '\n', content)
        content = re.sub(r'</p>', '', content)
        # 3. 处理图片描述
        content = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*/>', r'[\1]', content)
        # 4. 移除其他 HTML 标签
        content = re.sub(r'<[^>]+>', '', content)
        # 5. 处理 HTML 实体
        content = re.sub(r'&nbsp;', ' ', content)
        content = re.sub(r'&amp;', '&', content)
        content = re.sub(r'&lt;', '<', content)
        content = re.sub(r'&gt;', '>', content)
        content = re.sub(r'&quot;', '"', content)
        content = re.sub(r'&#39;', "'", content)
        # 6. 清理多余空行
        content = re.sub(r'\n{3,}', '\n\n', content)
        return content.strip()

    # 回退：提取 meta description
    meta_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
    if meta_match:
        return meta_match.group(1).strip()

    return ""


# ========== 抖音提取 ==========

async def extract_douyin(url: str, cookie: str = None) -> Dict[str, Any]:
    """
    提取抖音视频内容 - 复用增强版 DouyinExtractor
    支持：分享文本解析、机领网 API、火山方舟视频内容提取
    :param url: 抖音链接或分享文本
    :param cookie: 可选的 cookie
    :return: {title, content, author, tags, platform, video_url, stats}
    """
    try:
        from app.utils.douyin_extractor import DouyinExtractor

        extractor = DouyinExtractor(cookie)
        result = await extractor.extract(url)

        # 统一返回格式
        return {
            "title": result.get('title', ''),
            "content": result.get('content', ''),
            "author": result.get('author', ''),
            "tags": result.get('tags', []),
            "platform": "douyin",
            "video_url": result.get('video_url', ''),
            "stats": result.get('stats', {}),
        }

    except Exception as e:
        logger.error(f"抖音提取失败: {e}")
        return {"title": "", "content": f"提取失败: {str(e)[:200]}", "author": "", "tags": [], "platform": "douyin"}


# ========== 知乎提取 ==========

# 知乎配置文件路径
ZHIHU_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "zhihu.json"

def _load_zhihu_config() -> dict:
    """加载知乎配置"""
    try:
        if ZHIHU_CONFIG_PATH.exists():
            return json.loads(ZHIHU_CONFIG_PATH.read_text(encoding='utf-8'))
    except Exception as e:
        logger.warning(f"加载知乎配置失败: {e}")
    return {}

def _get_zhihu_cookie() -> str:
    """获取知乎 cookie"""
    config = _load_zhihu_config()
    cookie_parts = []
    for key in ['zhihu_session', 'z_c0', '_xsrf', '_zap', 'd_c0']:
        value = config.get('cookie', {}).get(key, '')
        if value:
            cookie_parts.append(f"{key}={value}")
    return '; '.join(cookie_parts)

def _extract_zhihu_ids(url: str) -> Dict[str, Optional[str]]:
    """从 URL 中提取知乎 ID"""
    patterns = [
        # 问题回答
        (r'zhihu\.com/question/(\d+)/answer/(\d+)', 'answer'),
        (r'zhihu\.com/answer/(\d+)', 'answer'),
        # 专栏文章
        (r'zhihu\.com/p/(\d+)', 'article'),
        (r'zhuanlan\.zhihu\.com/p/(\d+)', 'article'),
        # 问题页面
        (r'zhihu\.com/question/(\d+)', 'question'),
    ]

    for pattern, content_type in patterns:
        match = re.search(pattern, url)
        if match:
            groups = match.groups()
            return {
                'type': content_type,
                'question_id': groups[0] if content_type in ('answer', 'question') and len(groups) > 0 else None,
                'answer_id': groups[1] if content_type == 'answer' and len(groups) > 1 else groups[0] if content_type == 'answer' else None,
                'article_id': groups[0] if content_type == 'article' else None,
            }

    return {'type': 'unknown'}

def _html_to_text(html: str) -> str:
    """将 HTML 转换为纯文本"""
    text = html
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p[^>]*>', '\n', text)
    text = re.sub(r'</p>', '', text)
    text = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*/>', r'[\1]', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

async def _extract_via_jina(url: str) -> Dict[str, Any]:
    """使用 Jina Reader 提取知乎内容（无需 cookie）"""
    try:
        # 直接使用 httpx 调用 Jina Reader
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            "Accept": "text/markdown",
            "User-Agent": "Mozilla/5.0",
        }

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            resp = await _get_with_checked_redirects(client, jina_url, headers=headers)
            resp.raise_for_status()
            markdown = resp.text

        # 解析 Markdown 提取标题和内容
        title = ""
        content = ""
        author = ""

        # 提取标题（# 开头的行）
        title_match = re.search(r'^#\s+(.+)$', markdown, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            # 移除标题行
            markdown = markdown[:title_match.start()] + markdown[title_match.end():]

        # 提取作者（**作者：xxx** 或 作者：xxx）
        author_match = re.search(r'(?:\*\*|)作者[：:]\s*(.+?)(?:\*\*|$)', markdown, re.MULTILINE)
        if author_match:
            author = author_match.group(1).strip()

        # 清理内容
        content = markdown.strip()
        # 移除多余的空行
        content = re.sub(r'\n{3,}', '\n\n', content)

        return {
            "title": title,
            "content": content or "提取失败，请使用「粘贴文字」方式添加",
            "author": author,
            "tags": [],
            "platform": "zhihu"
        }

    except Exception as e:
        logger.error(f"Jina Reader 提取知乎失败: {e}")
        return {"title": "", "content": f"提取失败: {str(e)[:200]}", "author": "", "tags": [], "platform": "zhihu"}


async def _extract_via_api(url: str, cookie: str = None) -> Dict[str, Any]:
    """使用知乎移动端 API 提取（无需 cookie）"""
    try:
        # 解析 URL 获取 ID
        ids = _extract_zhihu_ids(url)
        logger.info(f"知乎链接解析: {ids}")

        title = ""
        content = ""
        author = ""

        # 使用移动端 API（无需登录）
        headers = {
            "User-Agent": "osee2unifiedRel498/5.8.0 iOS/16.0 (iPhone14,2)",
            "Accept": "application/json",
            "x-api-version": "3.0.91",
        }

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False, verify=False) as client:
            if ids['type'] == 'answer' and ids.get('answer_id'):
                api_url = f"https://api.zhihu.com/answers/{ids['answer_id']}?include=content,excerpt,author"
                resp = await _get_with_checked_redirects(client, api_url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                title = data.get('question', {}).get('title', '')
                content_html = data.get('content', '') or data.get('excerpt', '')
                content = _html_to_text(content_html)
                author = data.get('author', {}).get('name', '')

            elif ids['type'] == 'article' and ids.get('article_id'):
                api_url = f"https://api.zhihu.com/articles/{ids['article_id']}?include=content,excerpt,author"
                resp = await _get_with_checked_redirects(client, api_url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                title = data.get('title', '')
                content_html = data.get('content', '') or data.get('excerpt', '')
                content = _html_to_text(content_html)
                author = data.get('author', {}).get('name', '')

            elif ids['type'] == 'question':
                question_id = ids.get('question_id')
                if question_id:
                    api_url = f"https://api.zhihu.com/questions/{question_id}?include=detail,excerpt"
                    resp = await client.get(api_url, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    title = data.get('title', '')
                    content_html = data.get('detail', '') or data.get('excerpt', '')
                    content = _html_to_text(content_html)

        return {
            "title": title,
            "content": content or "提取失败，请使用「粘贴文字」方式添加",
            "author": author,
            "tags": [],
            "platform": "zhihu"
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"知乎 API 请求失败: {e.response.status_code}")
        return {"title": "", "content": f"API 请求失败，状态码: {e.response.status_code}", "author": "", "tags": [], "platform": "zhihu"}


async def extract_zhihu(url: str, cookie: str = None) -> Dict[str, Any]:
    """
    提取知乎内容（回答或文章）
    优先使用移动端 API（无需 cookie），失败则尝试其他方式
    :param url: 知乎链接
    :param cookie: 可选的 cookie
    :return: {title, content, author, tags, platform}
    """
    # 方案 1: 使用知乎移动端 API（无需 cookie，推荐）
    result = await _extract_via_api(url)
    if result.get('content') and "提取失败" not in result['content'] and "请求失败" not in result['content']:
        return result

    # 方案 2: 使用 Jina Reader
    result = await _extract_via_jina(url)
    if result.get('content') and "提取失败" not in result['content']:
        return result

    # 方案 3: 使用页面解析（需要 cookie）
    if not cookie:
        cookie = _get_zhihu_cookie()
    return await _extract_zhihu_page(url, cookie)


async def _extract_zhihu_page(url: str, cookie: str = None) -> Dict[str, Any]:
    """页面解析方式提取知乎内容（备用方案）"""
    try:
        clean_url = url.split('?')[0] if '?' in url else url

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.zhihu.com/",
        }
        if cookie:
            headers["Cookie"] = cookie

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False, verify=False) as client:
            resp = await _get_with_checked_redirects(client, clean_url, headers=headers)
            resp.raise_for_status()
            html = resp.text

        title = ""
        content = ""
        author = ""

        # 提取标题
        title_match = re.search(r'<h1[^>]*class="QuestionHeader-title"[^>]*>(.*?)</h1>', html)
        if not title_match:
            title_match = re.search(r'<h1[^>]*class="Post-Title"[^>]*>(.*?)</h1>', html)
        if not title_match:
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html)
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            title = re.sub(r'\s*[-–]\s*知乎\s*$', '', title)

        # 提取作者
        author_match = re.search(r'<a[^>]*class="UserLink-link"[^>]*>(.*?)</a>', html)
        if not author_match:
            author_match = re.search(r'<span[^>]*class="AuthorInfo-name"[^>]*>(.*?)</span>', html)
        if author_match:
            author = re.sub(r'<[^>]+>', '', author_match.group(1)).strip()

        # 提取内容
        content_match = re.search(r'<div[^>]*class="RichContent-inner"[^>]*>(.*?)</div>\s*(?=<div[^>]*class="ContentItem-actions")', html, re.DOTALL)
        if not content_match:
            content_match = re.search(r'<div[^>]*class="Post-RichTextContainer"[^>]*>(.*?)</div>\s*(?=<div[^>]*class="ContentItem-actions")', html, re.DOTALL)
        if not content_match:
            content_match = re.search(r'class="RichText[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)

        if content_match:
            content = _html_to_text(content_match.group(1))

        if not content:
            meta_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
            if meta_match:
                content = meta_match.group(1).strip()

        return {
            "title": title,
            "content": content or "提取失败，请使用「粘贴文字」方式添加",
            "author": author,
            "tags": [],
            "platform": "zhihu"
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"知乎页面请求失败: {e.response.status_code}")
        return {"title": "", "content": f"请求失败，状态码: {e.response.status_code}", "author": "", "tags": [], "platform": "zhihu"}
    except Exception as e:
        logger.error(f"知乎页面提取失败: {e}")
        return {"title": "", "content": f"提取失败: {str(e)[:200]}", "author": "", "tags": [], "platform": "zhihu"}


# ========== 统一入口 ==========

async def extract_link_content(url: str, cookie: str = None) -> Dict[str, Any]:
    """
    自动识别链接平台并提取内容
    :param url: 链接或分享文本（支持带文字的分享格式）
    :param cookie: 可选的 cookie
    :return: {title, content, author, tags, platform}
    """
    # 提取实际 URL
    actual_url = extract_url_from_text(url) or url
    actual_url = validate_public_http_url(actual_url)

    platform = detect_platform(actual_url)

    if platform == 'xhs':
        return await extract_xhs(actual_url, cookie)
    elif platform == 'gzh':
        return await extract_wechat(actual_url, cookie)
    elif platform == 'douyin':
        # 抖音需要传入原始分享文本（包含文案）
        return await extract_douyin(url, cookie)
    elif platform == 'zhihu':
        return await extract_zhihu(actual_url, cookie)
    else:
        return {
            "title": "",
            "content": "暂不支持该链接类型，建议使用「粘贴文字」方式添加",
            "author": "",
            "tags": [],
            "platform": "unknown"
        }
