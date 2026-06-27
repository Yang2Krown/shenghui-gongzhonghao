"""
抖音视频信息提取服务 - 移植自 Java 版本（保险 Agent 项目）
支持多种提取策略：
  A. 解析分享文本（无需网络）
  B. 机领网第三方 API（最可靠）
  C. Web API + X-Bogus 签名（备选）
  D. HTML 页面解析（RENDER_DATA）
  E. iesdouyin play 重定向（获取视频直链）
  F. yt-dlp 命令行兜底
  G. 火山方舟（豆包）API 提取视频内容
"""
import os
import re
import json
import logging
import time
import hashlib
import struct
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import unquote

import httpx
from dotenv import load_dotenv

# 加载 .env 文件
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

logger = logging.getLogger(__name__)

# 常量
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# X-Bogus 字符集
CHARSET_STR = "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe="
UA_KEY = bytes([0x00, 0x01, 0x0c])


class XBogus:
    """抖音 X-Bogus 请求签名生成器 - 移植自 Java 版本"""

    def __init__(self, ua: str = None):
        self.user_agent = ua or CHROME_UA

    def generate(self, query_string: str) -> str:
        """
        对查询字符串生成 X-Bogus 值
        :param query_string: param1=v1&param2=v2...
        :return: X-Bogus 值
        """
        # array1: RC4(UA_KEY, user_agent) -> base64 -> md5
        ua_encrypted = self._rc4(UA_KEY, self.user_agent.encode('iso-8859-1'))
        import base64
        ua_base64 = base64.b64encode(ua_encrypted).decode('iso-8859-1')
        array1 = self._hex_to_bytes(self._md5_hex(ua_base64.encode('iso-8859-1')))

        # array2: MD5 of hex-decoded constant (MD5 of empty string)
        array2 = self._hex_to_bytes(self._md5_hex(self._hex_to_bytes("d41d8cd98f00b204e9800998ecf8427e")))

        # urlPathArray: 双重 MD5
        url_path_array = self._hex_to_bytes(self._md5_hex(self._hex_to_bytes(self._md5_hex(query_string.encode('iso-8859-1')))))

        # 时间戳和固定常量
        timer = int(time.time())
        ct = 536919696

        # 18 个基础值
        v = [
            64, 0, 1, 12,
            url_path_array[14] & 0xFF, url_path_array[15] & 0xFF,
            array2[14] & 0xFF, array2[15] & 0xFF,
            array1[14] & 0xFF, array1[15] & 0xFF,
            (timer >> 24) & 255, (timer >> 16) & 255, (timer >> 8) & 255, timer & 255,
            (ct >> 24) & 255, (ct >> 16) & 255, (ct >> 8) & 255, ct & 255
        ]

        # XOR 校验和
        xor_result = v[0]
        for i in range(1, len(v)):
            xor_result ^= v[i]

        # 19 字节 payload
        payload = bytes(v + [xor_result & 0xFF])

        # RC4-encrypt with key [0xFF]，再在头部拼 [2, 255]
        encrypted = self._rc4(bytes([0xFF]), payload)
        garbled = bytes([2, 255]) + encrypted

        # 自定义 base64
        result = []
        for i in range(0, len(garbled), 3):
            a = garbled[i] & 0xFF
            b = garbled[i + 1] & 0xFF if i + 1 < len(garbled) else 0
            c = garbled[i + 2] & 0xFF if i + 2 < len(garbled) else 0
            result.append(self._encode3(a, b, c))
        return ''.join(result)

    def _encode3(self, a: int, b: int, c: int) -> str:
        x = (a << 16) | (b << 8) | c
        return (
            CHARSET_STR[(x >> 18) & 63] +
            CHARSET_STR[(x >> 12) & 63] +
            CHARSET_STR[(x >> 6) & 63] +
            CHARSET_STR[x & 63]
        )

    @staticmethod
    def _rc4(key: bytes, data: bytes) -> bytes:
        S = list(range(256))
        j = 0
        for i in range(256):
            j = (j + S[i] + (key[i % len(key)] & 0xFF)) % 256
            S[i], S[j] = S[j], S[i]

        out = bytearray(len(data))
        i = j = 0
        for k in range(len(data)):
            i = (i + 1) % 256
            j = (j + S[i]) % 256
            S[i], S[j] = S[j], S[i]
            out[k] = (data[k] & 0xFF) ^ S[(S[i] + S[j]) % 256]
        return bytes(out)

    @staticmethod
    def _hex_to_bytes(hex_str: str) -> bytes:
        return bytes(int(hex_str[i:i+2], 16) for i in range(0, len(hex_str), 2))

    @staticmethod
    def _md5_hex(data: bytes) -> str:
        return hashlib.md5(data).hexdigest()


class DouyinExtractor:
    """抖音视频信息提取器"""

    def __init__(self, cookie: str = None):
        self.cookie = cookie or os.getenv('DOUYIN_COOKIE', '')
        self.xbogus = XBogus(CHROME_UA)

        # 从环境变量读取 API 密钥
        self.jlwz_api_id = os.getenv('DOUYIN_JLWZ_API_ID', '')
        self.jlwz_api_key = os.getenv('DOUYIN_JLWZ_API_KEY', '')

        self.ark_api_key = os.getenv('ARK_API_KEY', '')
        self.ark_base_url = os.getenv('ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
        self.ark_model = os.getenv('ARK_MODEL', 'doubao-seed-2-0-mini-260215')
        self.ark_fps = int(os.getenv('ARK_FPS', '1'))

    async def extract(self, input_text: str) -> Dict[str, Any]:
        """
        提取抖音视频信息
        :param input_text: 链接或分享文本
        :return: {title, content, author, tags, platform, video_url, stats}
        """
        if not input_text or not input_text.strip():
            raise ValueError("请粘贴抖音作品链接或完整分享文本")

        # 验证链接格式
        raw_url = self._find_douyin_url(input_text)
        if raw_url and not self._is_valid_work_url(raw_url):
            raise ValueError("链接格式不正确！请使用作品页链接或短链接")

        # 策略 A：直接解析分享文本（最可靠，无需网络）
        share_note = self._parse_share_text(input_text)
        if share_note and share_note.get('content'):
            logger.info(f"从分享文本提取成功: content_len={len(share_note['content'])}")

        # 从输入中找到链接，解析 aweme_id
        aweme_id = self._extract_aweme_id_from_url(raw_url) if raw_url else None

        # 如果是短链接，尝试解析获取 aweme_id
        if raw_url and not aweme_id and ('v.douyin.com' in raw_url or 'iesdouyin.com' in raw_url):
            try:
                aweme_id = await self._resolve_short_url(raw_url)
                if aweme_id:
                    logger.info(f"短链接解析成功, aweme_id={aweme_id}")
            except Exception as e:
                logger.warning(f"短链接解析失败: {e}")

        # 填充基础字段
        result = share_note or {}
        if aweme_id:
            result['aweme_id'] = aweme_id
            result['work_url'] = f"https://www.douyin.com/video/{aweme_id}"

        # 策略 B：机领网第三方 API（最可靠，无需签名）
        if aweme_id and not result.get('video_url'):
            try:
                # 优先使用完整链接，如果是短链接则使用 aweme_id 构建完整链接
                api_url = raw_url if raw_url and 'douyin.com/video/' in raw_url else f"https://www.douyin.com/video/{aweme_id}"
                jlwz_note = await self._extract_via_jlwz_api(api_url)
                if jlwz_note:
                    if not result.get('content') and jlwz_note.get('content'):
                        result['content'] = jlwz_note['content']
                    if jlwz_note.get('video_url'):
                        result['video_url'] = jlwz_note['video_url']
                    if not result.get('author') and jlwz_note.get('author'):
                        result['author'] = jlwz_note['author']
                    if not result.get('tags') and jlwz_note.get('tags'):
                        result['tags'] = jlwz_note['tags']
                    if jlwz_note.get('stats'):
                        result['stats'] = jlwz_note['stats']
                    logger.info(f"机领网 API 提取成功, video_url={'有' if result.get('video_url') else '无'}")
            except Exception as e:
                logger.warning(f"机领网 API 提取失败: {e}")

        # 策略 C：Web API + X-Bogus 签名（备选）
        if aweme_id and not result.get('video_url'):
            try:
                api_note = await self._extract_via_web_api(aweme_id)
                if api_note:
                    if not result.get('content') and api_note.get('content'):
                        result['content'] = api_note['content']
                    if api_note.get('video_url'):
                        result['video_url'] = api_note['video_url']
                    if not result.get('author') and api_note.get('author'):
                        result['author'] = api_note['author']
                    if not result.get('tags') and api_note.get('tags'):
                        result['tags'] = api_note['tags']
                    if api_note.get('stats'):
                        result['stats'] = api_note['stats']
                    logger.info(f"Web API 提取成功, video_url={'有' if result.get('video_url') else '无'}")
            except Exception as e:
                logger.warning(f"Web API 提取失败: {e}")

        # 策略 C：HTML 页面解析
        if aweme_id and (not result.get('content') or not result.get('video_url')):
            try:
                html_note = await self._extract_via_html(aweme_id)
                if html_note:
                    if not result.get('content') and html_note.get('content'):
                        result['content'] = html_note['content']
                    if not result.get('video_url') and html_note.get('video_url'):
                        result['video_url'] = html_note['video_url']
                    if not result.get('author') and html_note.get('author'):
                        result['author'] = html_note['author']
                    logger.info(f"HTML 解析成功, video_url={'有' if result.get('video_url') else '无'}")
            except Exception as e:
                logger.warning(f"HTML 解析失败: {e}")

        # 策略 D：iesdouyin play 重定向
        if aweme_id and not result.get('video_url'):
            cdn_url = await self._try_iesdouyin_play_url(aweme_id)
            if cdn_url:
                result['video_url'] = cdn_url

        # 策略 F：yt-dlp 兜底
        if aweme_id and not result.get('video_url'):
            yt_url = self._try_yt_dlp(f"https://www.douyin.com/video/{aweme_id}")
            if yt_url:
                result['video_url'] = yt_url

        # 策略 G：使用火山方舟 API 提取视频内容（如果有视频直链）
        # 用户只需要视频的内容，不需要对视频进行分析
        if result.get('video_url'):
            try:
                video_content = await self._extract_video_content_via_ark(result['video_url'])
                if video_content:
                    # 保留原始的标题和标签，但用视频实际内容替换 content
                    original_title = result.get('title', '')
                    original_tags = result.get('tags', [])
                    result['content'] = video_content
                    # 如果原始标题较短，使用视频内容的前100个字符作为标题
                    if len(original_title) < 20:
                        result['title'] = video_content[:100] if len(video_content) > 100 else video_content
                    else:
                        result['title'] = original_title
                    result['tags'] = original_tags
                    logger.info(f"火山方舟 API 提取视频内容成功, content_len={len(video_content)}")
            except Exception as e:
                logger.warning(f"火山方舟 API 提取视频内容失败: {e}")

        if not result.get('content'):
            raise RuntimeError("提取失败，建议从抖音 App 复制完整分享文本")

        result['platform'] = 'douyin'
        return result

    def _find_douyin_url(self, text: str) -> Optional[str]:
        """从文本中提取抖音链接"""
        match = re.search(r'https://\S*douyin[^\s）】》\)"\']+', text)
        if match:
            url = match.group(0)
            # 清理末尾标点
            url = re.sub(r'[）】》\)"\']+$', '', url)
            return url
        return None

    def _is_valid_work_url(self, url: str) -> bool:
        """验证是否为有效的抖音作品链接"""
        lower = url.lower()
        return ('/video/' in lower or
                '/note/' in lower or
                'v.douyin.com' in lower or
                'iesdouyin.com' in lower)

    def _extract_aweme_id_from_url(self, url: str) -> Optional[str]:
        """从 URL 中提取 aweme_id"""
        patterns = [
            r'/video/(\d{15,19})',
            r'/note/(\d{15,19})',
            r'[?&]modal_id=(\d{15,19})',
            r'item_ids=(\d{15,19})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def _resolve_short_url(self, url: str) -> Optional[str]:
        """解析抖音短链接获取 aweme_id"""
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
                    location = resp.headers.get('Location', '')
                    return self._extract_aweme_id_from_url(location)
                return None
        except Exception as e:
            logger.warning(f"短链接解析失败: {e}")
            return None

    def _parse_share_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        解析抖音 App 分享文本
        格式示例：
        "5.69 k@p.Du 06/23 III:/ 回复 @xxx的评论 比较重要的三款保险... # 内容过于真实 # 每日分享 https://v.douyin.com/xxx/ 复制此链接..."
        """
        if 'douyin.com' not in text:
            return None

        # 去除用户误带的字段标签前缀
        original = text
        while True:
            stripped = text
            text = re.sub(r'^[^#\d\n]{2,60}[：:]\s*', '', text)
            if text == stripped:
                break

        # 找到 URL 的起始位置
        url_match = re.search(r'https://\S*douyin\S*', text)
        url_start = url_match.start() if url_match else len(text)

        # 提取话题标签
        topics = []
        tag_pattern = re.compile(r'#\s*([^#\s，。！？、\r\n]{1,30})')
        first_tag_pos = len(text)
        for tag_match in tag_pattern.finditer(text):
            tag = tag_match.group(1).strip()
            if tag:
                topics.append(tag)
                first_tag_pos = min(first_tag_pos, tag_match.start())

        # 文案取"第一个话题标签之前"和"URL 之前"的较小值
        desc_end = min(first_tag_pos, url_start)
        raw_desc = text[:desc_end].strip()

        # 去除分享文本特有噪声
        raw_desc = re.sub(
            r'^[\d.,]+\s*[kKwWmM]?(?:@\S+)?(?:\s+[\d/]+){0,2}[^\n一-龥]*',
            '', raw_desc
        )
        # 去除"复制打开抖音，看看【xxx的作品】"这类前缀
        raw_desc = re.sub(r'复制打开抖音，看看【[^】]*的作品】\s*', '', raw_desc)
        raw_desc = re.sub(r'回复\s+@\S+的评论\s*', '', raw_desc)
        raw_desc = re.sub(r'@\S+', '', raw_desc)
        raw_desc = re.sub(r'[\r\n]+', ' ', raw_desc)
        raw_desc = re.sub(r'\s{2,}', ' ', raw_desc).strip()

        if not raw_desc:
            return None

        result = {
            'content': raw_desc,
            'title': raw_desc,
            'tags': topics,
            'work_type': '视频',
        }
        return result

    async def _extract_via_jlwz_api(self, douyin_url: str) -> Optional[Dict[str, Any]]:
        """
        调用机领网抖音解析 API（https://api.jlwz.cn/dy/api.php）
        可靠获取视频直链和基础信息
        """
        from urllib.parse import quote

        api_url = (
            f"https://api.jlwz.cn/dy/api.php"
            f"?id={self.jlwz_api_id}"
            f"&key={self.jlwz_api_key}"
            f"&type=dy"
            f"&url={quote(douyin_url)}"
        )

        logger.info("机领网 API 请求开始")

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
            resp = await client.get(
                api_url,
                headers={"User-Agent": CHROME_UA}
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get('code') != 200:
            logger.warning(f"机领网 API code={data.get('code')} msg={data.get('msg')}")
            return None

        result = {
            'content': data.get('desc', ''),
            'title': data.get('desc', ''),
            'video_url': data.get('video', ''),
            'author': data.get('nickname', ''),
            'user_id': data.get('uid', ''),
        }

        # 互动数据
        stats = {}
        if data.get('digg_count'):
            stats['like'] = data['digg_count']
        if data.get('comment_count'):
            stats['comment'] = data['comment_count']
        if data.get('share_count'):
            stats['share'] = data['share_count']
        if data.get('collect_count'):
            stats['collect'] = data['collect_count']
        if stats:
            result['stats'] = stats

        logger.info(f"机领网 API 提取成功, video_url={'有' if result.get('video_url') else '无'}")
        return result

    async def _extract_via_web_api(self, aweme_id: str) -> Optional[Dict[str, Any]]:
        """
        调用抖音 Web API 获取视频信息
        需要 X-Bogus 签名
        """
        # 构造参数（顺序与签名算法一致）
        params = (
            "device_platform=webapp"
            "&aid=6383"
            "&channel=channel_pc_web"
            f"&aweme_id={aweme_id}"
            "&pc_client_type=1"
            "&version_code=290100"
            "&version_name=29.1.0"
            "&cookie_enabled=true"
            "&browser_language=zh-CN"
            "&browser_platform=Win32"
            "&browser_name=Chrome"
            "&browser_version=130.0.0.0"
            "&browser_online=true"
            "&engine_name=Blink"
            "&engine_version=130.0.0.0"
            "&os_name=Windows"
            "&os_version=10"
            "&platform=PC"
            "&msToken="
        )

        # 生成 X-Bogus 签名
        xbogus = self.xbogus.generate(params)
        url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?{params}&X-Bogus={xbogus}"

        # 预热 cookie
        await self._warm_up_cookies()

        headers = {
            "User-Agent": CHROME_UA,
            "Referer": f"https://www.douyin.com/video/{aweme_id}",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cookie": self.cookie or "",
        }

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        status_code = data.get('status_code')
        if status_code != 0:
            logger.warning(f"Web API status_code={status_code} msg={data.get('status_msg')}")
            return None

        aweme_detail = data.get('aweme_detail')
        if not aweme_detail:
            return None

        return self._build_from_web_api_detail(aweme_detail, aweme_id)

    def _build_from_web_api_detail(self, detail: dict, aweme_id: str) -> Dict[str, Any]:
        """从 Web API 响应构建结果"""
        result = {
            'aweme_id': aweme_id,
            'work_url': f"https://www.douyin.com/video/{aweme_id}",
            'content': detail.get('desc', ''),
            'title': detail.get('desc', ''),
        }

        # 作品类型
        aweme_type = detail.get('aweme_type')
        if aweme_type is not None:
            result['work_type'] = '图集' if aweme_type == 68 else '视频'

        # 互动数据
        stats = detail.get('statistics')
        if stats:
            result['stats'] = {
                'like': self._fmt_count(stats.get('digg_count')),
                'comment': self._fmt_count(stats.get('comment_count')),
                'collect': self._fmt_count(stats.get('collect_count')),
                'share': self._fmt_count(stats.get('share_count')),
            }

        # 作者信息
        author = detail.get('author')
        if author:
            result['author'] = author.get('nickname', '')
            result['user_id'] = author.get('unique_id', '')
            result['user_desc'] = author.get('signature', '')
            result['follower_count'] = self._fmt_count(author.get('follower_count'))

        # 话题标签
        text_extra = detail.get('text_extra')
        if text_extra and isinstance(text_extra, list):
            topics = []
            for item in text_extra:
                if isinstance(item, dict) and item.get('hashtag_name'):
                    topics.append(item['hashtag_name'])
            if topics:
                result['tags'] = topics

        # 发布时间
        create_time = detail.get('create_time')
        if create_time:
            from datetime import datetime
            result['publish_time'] = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')

        # 视频直链
        video_url = self._extract_video_url_from_web_api(detail.get('video'))
        if video_url:
            result['video_url'] = video_url

        return result

    def _extract_video_url_from_web_api(self, video_obj: Optional[dict]) -> Optional[str]:
        """从 Web API 响应中提取视频直链"""
        if not video_obj or not isinstance(video_obj, dict):
            return None

        # 方法1：bit_rate 列表
        bit_rate_list = video_obj.get('bit_rate')
        if bit_rate_list and isinstance(bit_rate_list, list):
            for br in bit_rate_list:
                if isinstance(br, dict):
                    pa = br.get('play_addr')
                    if isinstance(pa, dict):
                        url_list = pa.get('url_list')
                        if url_list and isinstance(url_list, list) and url_list:
                            url = url_list[0]
                            if url:
                                return url.replace('playwm', 'play')

        # 方法2：play_addr 直接拿
        for addr_key in ['play_addr', 'download_addr']:
            addr = video_obj.get(addr_key)
            if isinstance(addr, dict):
                url_list = addr.get('url_list')
                if url_list and isinstance(url_list, list) and url_list:
                    url = url_list[0]
                    if url:
                        return url.replace('playwm', 'play')

        return None

    async def _extract_via_html(self, aweme_id: str) -> Optional[Dict[str, Any]]:
        """通过 HTML 页面解析提取"""
        url = f"https://www.douyin.com/video/{aweme_id}"

        headers = {
            "User-Agent": CHROME_UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.douyin.com/",
        }

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, verify=False) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text

        return self._parse_render_data(html, aweme_id)

    def _parse_render_data(self, html: str, aweme_id: str) -> Optional[Dict[str, Any]]:
        """从 RENDER_DATA 中解析视频信息"""
        # 查找 RENDER_DATA 或 __NEXT_DATA__
        for selector in ['RENDER_DATA', '__NEXT_DATA__']:
            pattern = rf'<script[^>]*id="{selector}"[^>]*>(.*?)</script>'
            match = re.search(pattern, html, re.DOTALL)
            if not match:
                continue

            try:
                raw = match.group(1)
                decoded = unquote(raw) if 'RENDER_DATA' in selector else raw
                data = json.loads(decoded)

                # 搜索 aweme 数据
                detail = self._find_aweme_detail(data)
                if detail:
                    result = {
                        'aweme_id': aweme_id,
                        'work_url': f"https://www.douyin.com/video/{aweme_id}",
                    }
                    self._fill_from_detail(result, detail)
                    if result.get('content'):
                        return result
            except Exception as e:
                logger.warning(f"{selector} 解析失败: {e}")
                continue

        # OG tags fallback
        og_title = self._og_content(html, 'og:title')
        if og_title:
            return {
                'aweme_id': aweme_id,
                'work_url': f"https://www.douyin.com/video/{aweme_id}",
                'content': og_title,
                'title': og_title,
            }

        return None

    def _find_aweme_detail(self, data: dict) -> Optional[dict]:
        """在嵌套数据中搜索 aweme 信息"""
        paths = [
            ['app', 'initialState', 'aweme', 'detailInfo', 'awemeDetail'],
            ['app', 'initialState', 'videoDetail', 'awemeDetail'],
            ['props', 'pageProps', 'awemeDetail'],
        ]

        for path in paths:
            found = self._deep_get(data, *path)
            if isinstance(found, dict) and ('desc' in found or 'statistics' in found):
                return found

        return self._deep_search(data, 'desc', 'statistics')

    def _fill_from_detail(self, result: dict, detail: dict):
        """从详情数据填充结果"""
        result['content'] = detail.get('desc', '')
        result['title'] = detail.get('desc', '')

        aweme_type = detail.get('aweme_type') or detail.get('awemeType')
        if aweme_type is not None:
            result['work_type'] = '图集' if aweme_type == 68 else '视频'

        # 互动数据
        stats = detail.get('statistics')
        if stats and isinstance(stats, dict):
            result['stats'] = {
                'like': self._fmt_count(stats.get('digg_count') or stats.get('diggCount')),
                'comment': self._fmt_count(stats.get('comment_count') or stats.get('commentCount')),
                'collect': self._fmt_count(stats.get('collect_count') or stats.get('collectCount')),
                'share': self._fmt_count(stats.get('share_count') or stats.get('shareCount')),
            }

        # 作者信息
        author = detail.get('author')
        if author and isinstance(author, dict):
            result['author'] = author.get('nickname', '')
            result['user_id'] = author.get('unique_id') or author.get('uniqueId', '')
            result['user_desc'] = author.get('signature', '')
            result['follower_count'] = self._fmt_count(author.get('follower_count') or author.get('followerCount'))

        # 话题标签
        text_extra = detail.get('text_extra') or detail.get('textExtra')
        if text_extra and isinstance(text_extra, list):
            topics = []
            for item in text_extra:
                if isinstance(item, dict):
                    name = item.get('hashtag_name') or item.get('hashtagName')
                    if name:
                        topics.append(name)
            if topics:
                result['tags'] = topics

        # 发布时间
        create_time = detail.get('create_time') or detail.get('createTime')
        if create_time:
            from datetime import datetime
            result['publish_time'] = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')

        # 视频直链
        if not result.get('video_url'):
            video_url = self._extract_video_url(detail.get('video'))
            if video_url:
                result['video_url'] = video_url

    def _extract_video_url(self, video_obj: Optional[dict]) -> Optional[str]:
        """从视频对象中提取直链"""
        if not video_obj or not isinstance(video_obj, dict):
            return None

        # playAddr 格式
        for key in ['playAddr', 'play_addr', 'downloadAddr', 'download_addr']:
            addr = video_obj.get(key)
            if isinstance(addr, list):
                for item in addr:
                    if isinstance(item, dict):
                        src = item.get('src')
                        if src:
                            return src
            elif isinstance(addr, dict):
                url_list = addr.get('url_list')
                if url_list and isinstance(url_list, list) and url_list:
                    return url_list[0]

        # bitrateInfo 格式
        bitrate_info = video_obj.get('bitrateInfo')
        if bitrate_info and isinstance(bitrate_info, list) and bitrate_info:
            first = bitrate_info[0]
            if isinstance(first, dict):
                pa = first.get('PlayAddr')
                if isinstance(pa, dict):
                    url_list = pa.get('UrlList')
                    if url_list and isinstance(url_list, list) and url_list:
                        return url_list[0]

        return None

    async def _warm_up_cookies(self):
        """预热 cookie（访问首页获取 ttwid）"""
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, verify=False) as client:
                await client.get(
                    "https://www.douyin.com/",
                    headers={"User-Agent": CHROME_UA}
                )
        except Exception as e:
            logger.warning(f"Cookie 预热失败: {e}")

    async def _try_iesdouyin_play_url(self, aweme_id: str) -> Optional[str]:
        """尝试通过 iesdouyin 重定向获取视频直链"""
        play_url = (
            f"https://www.iesdouyin.com/aweme/v1/play/"
            f"?video_id={aweme_id}&ratio=720p&line=0&media_type=4&vr_type=0"
        )
        try:
            async with httpx.AsyncClient(
                timeout=12.0,
                follow_redirects=False,
                verify=False
            ) as client:
                resp = await client.get(
                    play_url,
                    headers={
                        "User-Agent": "com.ss.android.ugc.aweme/230501 (Android 11)",
                        "Referer": "https://www.iesdouyin.com/",
                    }
                )
                final_url = str(resp.url)
                if final_url != play_url and any(domain in final_url for domain in [
                    'douyinvod.com', 'snssdk.com', 'bytecdn.cn'
                ]):
                    logger.info("iesdouyin play 重定向成功")
                    return final_url
        except Exception as e:
            logger.debug(f"iesdouyin play 重定向失败: {e}")
        return None

    def _try_yt_dlp(self, work_url: str) -> Optional[str]:
        """使用 yt-dlp 提取视频直链（兜底方案）"""
        try:
            result = subprocess.run(
                [
                    'yt-dlp', '--get-url',
                    '-f', 'best[ext=mp4]/best[vcodec!=none]/best',
                    '--no-playlist', '--quiet', '--no-warnings',
                    work_url
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and result.stdout.strip().startswith('http'):
                logger.info("yt-dlp 提取成功")
                return result.stdout.strip()
        except FileNotFoundError:
            logger.debug("yt-dlp 未安装")
        except Exception as e:
            logger.debug(f"yt-dlp 提取失败: {e}")
        return None

    async def _extract_video_content_via_ark(self, video_url: str, max_retries: int = 3) -> Optional[str]:
        """
        使用火山方舟（豆包）Responses API 提取视频内容
        这是用户只需要视频内容，不需要视频分析时使用的方法
        """
        import asyncio

        api_url = f"{self.ark_base_url}/responses"

        body = {
            "model": self.ark_model,
            "stream": False,
            "max_output_tokens": 12000,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_video",
                            "video_url": video_url,
                            "fps": self.ark_fps,
                        },
                        {
                            "type": "input_text",
                            "text": """请分析这个视频，完成以下两个部分：

【一、视频内容总结】
用 2-3 句话概括这个视频的核心内容和主题。

【二、视频口播/字幕内容】
尽可能完整地还原视频中所有口播、旁白、字幕的文字内容，按时间顺序排列，保持原话。

要求：
- 不要编造看不到或听不到的信息
- 如果无法逐字转写，请给出尽可能接近原话的内容纪要
- 输出 Markdown 格式"""
                        }
                    ]
                }
            ]
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.ark_api_key}",
        }

        # 添加重试机制处理 429 错误
        for attempt in range(max_retries):
            try:
                logger.info(f"火山方舟 API 请求开始 (尝试 {attempt + 1}/{max_retries})")

                async with httpx.AsyncClient(timeout=300.0, follow_redirects=True, verify=False) as client:
                    resp = await client.post(api_url, json=body, headers=headers)

                    if resp.status_code == 429:
                        # 429 Too Many Requests - 等待后重试
                        wait_time = (attempt + 1) * 10  # 10, 20, 30 秒
                        logger.warning(f"火山方舟 API 返回 429，等待 {wait_time} 秒后重试")
                        await asyncio.sleep(wait_time)
                        continue

                    resp.raise_for_status()
                    data = resp.json()

                    # 从响应中提取文本
                    transcript = self._extract_transcript_from_response(data)
                    if transcript:
                        return transcript
                    else:
                        logger.warning("火山方舟 API 未返回有效内容")
                        return None

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 10
                    logger.warning(f"火山方舟 API 返回 429，等待 {wait_time} 秒后重试")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise
            except Exception as e:
                logger.error(f"火山方舟 API 请求失败: {e}")
                raise

        logger.error("火山方舟 API 重试次数已用完")
        return None
        if transcript:
            logger.info(f"火山方舟 API 提取成功, content_len={len(transcript)}")
            return transcript

        logger.warning("火山方舟 API 未返回有效内容")
        return None

    def _extract_transcript_from_response(self, data: dict) -> Optional[str]:
        """从火山方舟 API 响应中提取文本内容"""
        # 尝试从 output 数组中提取
        output = data.get('output')
        if isinstance(output, list):
            texts = []
            for item in output:
                content = item.get('content')
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get('type')
                            if block_type in ('output_text', 'text'):
                                text = block.get('text', '')
                                if text:
                                    texts.append(text)
            if texts:
                return '\n'.join(texts)

        # 尝试其他字段
        for key in ['transcript', 'text', 'content', 'result', 'data']:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            elif isinstance(value, dict):
                for sub_key in ['transcript', 'text', 'content', 'result']:
                    sub_value = value.get(sub_key)
                    if isinstance(sub_value, str) and sub_value.strip():
                        return sub_value.strip()

        return None

    def _og_content(self, html: str, property_name: str) -> Optional[str]:
        """从 meta 标签提取 OG 内容"""
        match = re.search(
            rf'<meta[^>]*property="{property_name}"[^>]*content="([^"]*)"',
            html
        )
        return match.group(1) if match else None

    def _deep_get(self, obj: Any, *keys: str) -> Any:
        for key in keys:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
        return obj

    def _deep_search(self, data: dict, *required_keys: str) -> Optional[dict]:
        if all(k in data for k in required_keys):
            return data
        for v in data.values():
            if isinstance(v, dict):
                found = self._deep_search(v, *required_keys)
                if found:
                    return found
        return None

    @staticmethod
    def _fmt_count(v: Any) -> Optional[str]:
        if v is None:
            return None
        n = int(v)
        if n >= 10000:
            return f"{n / 10000:.1f}w"
        return str(n)


# 统一入口函数
async def extract_douyin_content(url: str, cookie: str = None) -> Dict[str, Any]:
    """
    提取抖音视频信息（统一入口）
    :param url: 链接或分享文本
    :param cookie: 可选的 cookie
    :return: {title, content, author, tags, platform, video_url, stats}
    """
    extractor = DouyinExtractor(cookie)
    try:
        return await extractor.extract(url)
    except ValueError as e:
        return {
            "title": "",
            "content": str(e),
            "author": "",
            "tags": [],
            "platform": "douyin"
        }
    except Exception as e:
        logger.error(f"抖音提取失败: {e}")
        return {
            "title": "",
            "content": f"提取失败: {str(e)[:200]}",
            "author": "",
            "tags": [],
            "platform": "douyin"
        }
