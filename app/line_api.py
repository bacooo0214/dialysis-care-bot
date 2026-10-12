"""LINE Messaging API 薄封裝（直接打 REST）。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import uuid
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

API = "https://api.line.me/v2/bot"
DATA_API = "https://api-data.line.me/v2/bot"


def verify_signature(body: bytes, signature: str) -> bool:
    """驗證 X-Line-Signature。"""
    secret = get_settings().line_channel_secret.encode()
    digest = hmac.new(secret, body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature or "")


class LineApiError(RuntimeError):
    """LINE API 錯誤。"""

    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"LINE API {status}: {body}")
        self.status = status
        self.body = body


class LineClient:
    """非同步 LINE 用戶端。"""

    def __init__(self) -> None:
        token = get_settings().line_channel_access_token
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(20.0, connect=5.0),
        )

    async def aclose(self) -> None:
        """關閉連線池。"""
        await self._http.aclose()

    async def _post(self, url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> Any:
        r = await self._http.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            raise LineApiError(r.status_code, r.text)
        return r.json() if r.content else None

    async def reply(self, reply_token: str, messages: list[dict[str, Any]]) -> None:
        """回覆訊息（免費，不計入推播額度）。"""
        await self._post(f"{API}/message/reply", {"replyToken": reply_token, "messages": messages[:5]})

    async def push(self, to: str, messages: list[dict[str, Any]]) -> None:
        """主動推播（計入額度；群組按人頭計）。帶 Retry-Key 避免重試造成重複推播。"""
        for i in range(0, len(messages), 5):
            await self._post(
                f"{API}/message/push",
                {"to": to, "messages": messages[i : i + 5]},
                headers={"X-Line-Retry-Key": str(uuid.uuid4())},
            )

    async def get_content(self, message_id: str) -> tuple[bytes, str]:
        """下載使用者傳的圖片。"""
        r = await self._http.get(f"{DATA_API}/message/{message_id}/content", timeout=60)
        if r.status_code >= 400:
            raise LineApiError(r.status_code, r.text)
        return r.content, r.headers.get("content-type", "image/jpeg")

    async def show_loading(self, user_id: str, seconds: int = 30) -> None:
        """1:1 聊天才有效的「輸入中」動畫。"""
        try:
            await self._post(f"{API}/chat/loading/start", {"chatId": user_id, "loadingSeconds": seconds})
        except LineApiError as e:
            log.debug("loading animation failed: %s", e)

    async def get_display_name(self, user_id: str, group_id: str | None = None, room_id: str | None = None) -> str | None:
        """取得暱稱；拿不到（未加好友等）回 None。"""
        if group_id:
            url = f"{API}/group/{group_id}/member/{user_id}"
        elif room_id:
            url = f"{API}/room/{room_id}/member/{user_id}"
        else:
            url = f"{API}/profile/{user_id}"
        r = await self._http.get(url)
        if r.status_code >= 400:
            return None
        return r.json().get("displayName")

    async def get_group_summary(self, group_id: str) -> str | None:
        """群組名稱。"""
        r = await self._http.get(f"{API}/group/{group_id}/summary")
        return r.json().get("groupName") if r.status_code < 400 else None

    # ---------- Rich menu ----------
    async def create_rich_menu(self, body: dict[str, Any]) -> str:
        """建立 rich menu，回傳 id。"""
        data = await self._post(f"{API}/richmenu", body)
        return data["richMenuId"]

    async def upload_rich_menu_image(self, rich_menu_id: str, png: bytes) -> None:
        """上傳 rich menu 圖片。"""
        r = await self._http.post(
            f"{DATA_API}/richmenu/{rich_menu_id}/content",
            content=png,
            headers={"Content-Type": "image/png"},
            timeout=60,
        )
        if r.status_code >= 400:
            raise LineApiError(r.status_code, r.text)

    async def set_default_rich_menu(self, rich_menu_id: str) -> None:
        """設為所有使用者預設選單。"""
        r = await self._http.post(f"{API}/user/all/richmenu/{rich_menu_id}")
        if r.status_code >= 400:
            raise LineApiError(r.status_code, r.text)

    async def list_rich_menus(self) -> list[dict[str, Any]]:
        """列出 rich menu。"""
        r = await self._http.get(f"{API}/richmenu/list")
        return r.json().get("richmenus", [])

    async def delete_rich_menu(self, rich_menu_id: str) -> None:
        """刪除 rich menu。"""
        await self._http.delete(f"{API}/richmenu/{rich_menu_id}")


_client: LineClient | None = None


def line() -> LineClient:
    """全域 LineClient。"""
    global _client
    if _client is None:
        _client = LineClient()
    return _client
