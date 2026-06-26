"""飞书 OAuth 客户端（原生 HTTP，设备码授权 + 读文档）。

不依赖 lark-cli / 系统钥匙串，纯 httpx 调飞书开放平台，Linux 生产可跑。
token 由调用方（service 层）持久化到 FeishuAuth 表，按 user_id 隔离、按需刷新。

设备码流程（经实测确认）：
  1) POST accounts.feishu.cn/oauth/v1/device_authorization (form: client_id+client_secret+scope)
     → device_code / user_code / verification_uri(_complete) / expires_in / interval
  2) 轮询 POST open.feishu.cn/open-apis/authen/v2/oauth/token
     grant_type=urn:ietf:params:oauth:grant-type:device_code
     → pending: error=authorization_pending；成功: access_token + refresh_token
  3) 刷新：同端点 grant_type=refresh_token
"""

import asyncio
import logging
import re

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

OAUTH_HOST = "https://accounts.feishu.cn"
OPEN_HOST = "https://open.feishu.cn"
DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"


class FeishuError(RuntimeError):
    """飞书接口调用失败。"""


class FeishuAuthPending(Exception):
    """设备码尚未被用户确认（轮询继续）。"""


class FeishuOAuthClient:
    def __init__(self) -> None:
        self.app_id = settings.FEISHU_APP_ID
        self.app_secret = settings.FEISHU_APP_SECRET
        self.scopes = settings.FEISHU_SCOPES

    def _require_config(self) -> None:
        if not self.app_id or not self.app_secret:
            raise FeishuError("飞书未配置：缺少 FEISHU_APP_ID / FEISHU_APP_SECRET")

    # ── 设备码授权 ────────────────────────────────────────

    async def device_authorization(self) -> dict:
        """发起设备码授权。返回 device_code / user_code / verification_uri(_complete) / expires_in / interval。"""
        self._require_config()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                f"{OAUTH_HOST}/oauth/v1/device_authorization",
                data={"client_id": self.app_id, "client_secret": self.app_secret, "scope": self.scopes},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        data = r.json()
        if "device_code" not in data:
            raise FeishuError(f"发起设备码失败: {data.get('error_description') or data}")
        return data

    async def poll_token(self, device_code: str) -> dict:
        """轮询一次换 token。未授权抛 FeishuAuthPending；成功返回 token dict。"""
        self._require_config()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                f"{OPEN_HOST}/open-apis/authen/v2/oauth/token",
                data={
                    "grant_type": DEVICE_GRANT,
                    "device_code": device_code,
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        data = r.json()
        err = data.get("error")
        if err in ("authorization_pending", "slow_down"):
            raise FeishuAuthPending()
        if err:
            raise FeishuError(data.get("error_description") or err)
        if not data.get("access_token"):
            raise FeishuError(f"换 token 失败: {data}")
        return data

    async def wait_for_authorization(self, device_code: str, interval: int = 5,
                                     expires_in: int = 600) -> dict:
        """阻塞轮询直到用户确认授权或超时。返回 token dict。"""
        deadline = asyncio.get_event_loop().time() + expires_in
        step = max(interval, 2)
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(step)
            try:
                return await self.poll_token(device_code)
            except FeishuAuthPending:
                continue
        raise FeishuError("授权超时，用户未在有效期内确认")

    async def refresh(self, refresh_token: str) -> dict:
        """用 refresh_token 续期。返回新的 token dict。"""
        self._require_config()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                f"{OPEN_HOST}/open-apis/authen/v2/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        data = r.json()
        if data.get("error") or not data.get("access_token"):
            raise FeishuError(data.get("error_description") or f"刷新 token 失败: {data}")
        return data

    # ── 用户信息 ──────────────────────────────────────────

    async def get_user_info(self, access_token: str) -> dict:
        """拿当前授权用户的基本信息 {name, open_id}。"""
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(
                f"{OPEN_HOST}/open-apis/authen/v1/user_info",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        data = r.json()
        d = data.get("data") or {}
        return {"name": d.get("name"), "open_id": d.get("open_id")}

    # ── 读文档 ────────────────────────────────────────────

    async def read_document(self, access_token: str, url: str) -> dict:
        """读飞书文档（docx / wiki 链接），返回 {title, content}（纯文本）。"""
        document_id, title = await self._resolve_doc(access_token, url)
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get(
                f"{OPEN_HOST}/open-apis/docx/v1/documents/{document_id}/raw_content",
                params={"lang": 0},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        data = r.json()
        if data.get("code") not in (0, None):
            raise FeishuError(f"读取文档内容失败: {data.get('msg') or data}")
        content = (data.get("data") or {}).get("content") or ""
        return {"title": title, "content": content, "document_id": document_id}

    async def _resolve_doc(self, access_token: str, url: str) -> tuple[str, str]:
        """从链接解析出 docx document_id（wiki 需先转 obj_token）。返回 (document_id, title)。"""
        u = url.strip()
        # 直接 docx
        m = re.search(r"/docx/([A-Za-z0-9]+)", u)
        if m:
            return m.group(1), ""
        # wiki：get_node 拿 obj_token
        m = re.search(r"/wiki/([A-Za-z0-9]+)", u)
        if m:
            node = await self._wiki_node(access_token, m.group(1))
            if node.get("obj_type") not in ("docx", "doc", None):
                raise FeishuError(f"暂不支持的 wiki 节点类型：{node.get('obj_type')}")
            return node["obj_token"], node.get("title", "")
        # 旧版 docs
        if re.search(r"/docs/([A-Za-z0-9]+)", u):
            raise FeishuError("暂不支持旧版 docs 链接，请用新版 docx 或 wiki 链接")
        raise FeishuError("无法识别的飞书文档链接")

    async def _wiki_node(self, access_token: str, wiki_token: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(
                f"{OPEN_HOST}/open-apis/wiki/v2/spaces/get_node",
                params={"token": wiki_token, "obj_type": "wiki"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        data = r.json()
        if data.get("code") not in (0, None):
            raise FeishuError(f"解析 wiki 节点失败: {data.get('msg') or data}")
        node = (data.get("data") or {}).get("node") or {}
        if not node.get("obj_token"):
            raise FeishuError("wiki 节点无 obj_token")
        return node


feishu_client = FeishuOAuthClient()
