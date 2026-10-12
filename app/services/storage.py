"""Supabase Storage：上傳圖表/語音並產生 signed URL 給 LINE。"""

from __future__ import annotations

import uuid
from urllib.parse import urljoin

from app.config import get_settings
from app.db import db


async def upload(family_id: str, folder: str, data: bytes, content_type: str, ext: str) -> str:
    """上傳檔案，回傳 storage path。路徑用 UUID，不含任何個資。"""
    s = get_settings()
    path = f"{folder}/{family_id}/{uuid.uuid4().hex}.{ext}"
    c = await db()
    await c.storage.from_(s.storage_bucket).upload(
        path, data, {"content-type": content_type, "upsert": "false"}
    )
    return path


async def signed_url(path: str) -> str:
    """產生長效 signed URL（LINE 用戶端點開時才抓檔）。"""
    s = get_settings()
    c = await db()
    res = await c.storage.from_(s.storage_bucket).create_signed_url(path, s.signed_url_ttl_seconds)
    url = res.get("signedURL") or res.get("signedUrl") or res.get("signed_url")
    if not url:
        raise RuntimeError(f"無法產生 signed URL: {res}")
    if url.startswith("/"):
        url = urljoin(s.supabase_url.rstrip("/") + "/storage/v1/", url.lstrip("/"))
    return url


async def upload_and_sign(family_id: str, folder: str, data: bytes, content_type: str, ext: str) -> tuple[str, str]:
    """上傳並回傳 (path, url)。"""
    path = await upload(family_id, folder, data, content_type, ext)
    return path, await signed_url(path)
