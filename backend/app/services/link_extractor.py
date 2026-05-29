"""
链接内容提取服务
支持：小红书、微信公众号、抖音
"""
import re
import json
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, unquote

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag

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
    if 'douyin.com' in lower or 'iesdouyin.com' in lower:
        return 'douyin'
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

    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=True,
        verify=False
    ) as client:
        resp = await client.get(url, headers=headers)
        logger.info(f"响应状态码: {resp.status_code}")
        resp.raise_for_status()
        return resp.text


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
    提取抖音视频文案 - 参考保险 Agent 项目，多策略级联
    :param url: 抖音链接或分享文本
    :param cookie: 可选的 cookie
    :return: {title, content, author, tags, platform}
    """
    try:
        # 如果是分享文本，先提取 URL 和文案
        actual_url = extract_url_from_text(url)
        share_text = url if actual_url else ''

        if actual_url:
            url = actual_url

        # 策略 A：直接解析分享文本（最可靠，无需网络）
        if share_text:
            share_result = _parse_douyin_share_text(share_text)
            if share_result and share_result.get('content'):
                logger.info(f"从分享文本提取成功: content_len={len(share_result['content'])}")
                return share_result

        # 处理短链接
        if 'v.douyin.com' in url or 'iesdouyin.com' in url:
            url = await _resolve_douyin_short_url(url)
            logger.info(f"抖音短链接解析后: {url}")

        # 提取 aweme_id
        aweme_id = _extract_aweme_id(url)
        if not aweme_id:
            return {"title": "", "content": "无法解析抖音链接，请检查链接格式", "author": "", "tags": [], "platform": "douyin"}

        logger.info(f"抖音 aweme_id: {aweme_id}")

        # 策略 B：获取页面内容并解析
        html = await fetch_html(url, cookie=cookie)
        logger.info(f"抖音 HTML 长度: {len(html)}")

        # 尝试从 RENDER_DATA 提取
        result = _parse_douyin_render_data(html, aweme_id)
        if result and result.get('content'):
            logger.info(f"抖音 RENDER_DATA 提取成功, content_len={len(result.get('content', ''))}")
            return result

        # 策略 C：从 meta 标签提取
        result = _parse_douyin_meta(html, url)
        if result and result.get('content'):
            logger.info(f"抖音 meta 提取成功: content_len={len(result.get('content', ''))}")
            return result

        # 策略 D：从 HTML 中正则提取
        result = _parse_douyin_html_regex(html)
        if result and result.get('content'):
            logger.info(f"抖音正则提取成功: content_len={len(result.get('content', ''))}")
            return result

        # 最后回退到分享文本
        if share_text:
            return _parse_douyin_share_text(share_text)

        return {"title": "", "content": "提取失败，请使用「粘贴文字」方式添加", "author": "", "tags": [], "platform": "douyin"}

    except httpx.HTTPStatusError as e:
        logger.error(f"抖音请求失败: {e.response.status_code}")
        return {"title": "", "content": f"请求失败，状态码: {e.response.status_code}，可能需要登录或链接已失效", "author": "", "tags": [], "platform": "douyin"}
    except Exception as e:
        logger.error(f"抖音提取失败: {e}")
        return {"title": "", "content": f"提取失败: {str(e)[:200]}", "author": "", "tags": [], "platform": "douyin"}


def _parse_douyin_html_regex(html: str) -> dict:
    """从 HTML 中正则提取抖音内容"""
    # 提取 desc 字段（视频描述）
    desc_patterns = [
        r'"desc"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"',
    ]

    for pattern in desc_patterns:
        match = re.search(pattern, html)
        if match:
            desc = match.group(1)
            # 处理转义字符
            desc = desc.replace('\\n', '\n').replace('\\"', '"')
            if desc and len(desc) > 5:
                return {"title": "", "content": desc, "author": "", "tags": [], "platform": "douyin"}

    return {"title": "", "content": "", "author": "", "tags": [], "platform": "douyin"}


async def _resolve_douyin_short_url(url: str) -> str:
    """解析抖音短链接"""
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=False,
            verify=False
        ) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": CHROME_UA},
                follow_redirects=False
            )
            if resp.status_code in (301, 302):
                return resp.headers.get('Location', url)
            return url
    except Exception:
        return url


def _extract_aweme_id(url: str) -> Optional[str]:
    """从 URL 中提取 aweme_id"""
    patterns = [
        r'/video/(\d+)',
        r'/note/(\d+)',
        r'aweme_id=(\d+)',
        r'modal_id=(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _parse_douyin_share_text(text: str) -> dict:
    """从分享文本中提取内容"""
    # 移除 URL
    text = re.sub(r'https?://[^\s]+', '', text)
    # 移除抖音分享前缀（如 "5.69 k@p.Du 06/23 III:/"）
    text = re.sub(r'^[\d.]+\s*\S+\s*\d{2}/\d{2}\s*\S+\s*/\s*', '', text)
    # 移除 @ 提及
    text = re.sub(r'@\S+\s*', '', text)

    # 提取话题标签
    tags = re.findall(r'#(\S+?)(?:\s|$|#)', text)
    # 从文本中移除话题标签（保留文案）
    content = re.sub(r'#\S+\s*', '', text).strip()

    return {
        "title": "",
        "content": content,
        "author": "",
        "tags": tags,
        "platform": "douyin"
    }


def _parse_douyin_render_data(html: str, aweme_id: str) -> Optional[dict]:
    """从 RENDER_DATA 中提取抖音视频信息"""
    try:
        # 查找 RENDER_DATA 或 __NEXT_DATA__
        patterns = [
            r'<script[^>]*id="RENDER_DATA"[^>]*>(.*?)</script>',
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                data_text = unquote(match.group(1))
                try:
                    data = json.loads(data_text)
                    # 搜索 aweme 数据
                    result = _find_aweme_in_data(data, aweme_id)
                    if result:
                        return result
                except json.JSONDecodeError:
                    continue

        return None
    except Exception as e:
        logger.warning(f"RENDER_DATA 解析失败: {e}")
        return None


def _find_aweme_in_data(data: Any, aweme_id: str) -> Optional[dict]:
    """在嵌套数据中搜索 aweme 信息"""
    if isinstance(data, dict):
        # 检查是否有 desc 字段（视频描述）
        if 'desc' in data and isinstance(data['desc'], str):
            desc = data['desc']
            # 提取作者
            author = ''
            if 'author' in data and isinstance(data['author'], dict):
                author = data['author'].get('nickname', '')

            # 提取话题标签
            tags = []
            if 'text_extra' in data:
                for item in data['text_extra']:
                    if isinstance(item, dict) and 'hashtag_name' in item:
                        tags.append(item['hashtag_name'])

            if desc:
                return {
                    "title": "",
                    "content": desc,
                    "author": author,
                    "tags": tags,
                    "platform": "douyin"
                }

        # 递归搜索
        for value in data.values():
            result = _find_aweme_in_data(value, aweme_id)
            if result:
                return result

    elif isinstance(data, list):
        for item in data:
            result = _find_aweme_in_data(item, aweme_id)
            if result:
                return result

    return None


def _parse_douyin_meta(html: str, url: str) -> dict:
    """从 meta 标签中提取抖音信息"""
    title = ''
    content = ''

    # 提取 og:title
    title_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', html)
    if title_match:
        title = title_match.group(1)

    # 提取 og:description
    desc_match = re.search(r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"', html)
    if desc_match:
        content = desc_match.group(1)

    # 提取 author
    author = ''
    author_match = re.search(r'"nickname"\s*:\s*"([^"]+)"', html)
    if author_match:
        author = author_match.group(1)

    return {
        "title": title,
        "content": content,
        "author": author,
        "tags": [],
        "platform": "douyin"
    }


# ========== 统一入口 ==========

async def extract_link_content(url: str, cookie: str = None) -> Dict[str, Any]:
    """
    自动识别链接平台并提取内容
    :param url: 链接或分享文本
    :param cookie: 可选的 cookie
    :return: {title, content, author, tags, platform}
    """
    # 提取实际 URL
    actual_url = extract_url_from_text(url) or url

    platform = detect_platform(actual_url)

    if platform == 'xhs':
        return await extract_xhs(actual_url, cookie)
    elif platform == 'gzh':
        return await extract_wechat(actual_url, cookie)
    elif platform == 'douyin':
        return await extract_douyin(url, cookie)
    else:
        return {
            "title": "",
            "content": "暂不支持该链接类型，建议使用「粘贴文字」方式添加",
            "author": "",
            "tags": [],
            "platform": "unknown"
        }
