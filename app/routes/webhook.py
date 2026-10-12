"""LINE Webhook 路由。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, Response

from app.bot_handlers import handle_event
from app.db import mark_event_processed
from app.line_api import verify_signature

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/callback")
async def line_webhook(
    request: Request,
    x_line_signature: str = Header(None, alias="x-line-signature"),
) -> Response:
    """接收 LINE Messaging API Webhook 事件。"""
    body_bytes = await request.body()

    # 1. 簽章驗證
    if not x_line_signature or not verify_signature(body_bytes, x_line_signature):
        log.warning("簽章驗證失敗")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 2. 解析事件
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        log.error("無法解析 JSON: %s", e)
        raise HTTPException(status_code=400, detail="Malformed JSON") from e

    events = payload.get("events", [])

    # 3. 非同步分發處理（立即回傳 200，避免 LINE 逾時重送）
    for event in events:
        webhook_event_id = event.get("webhookEventId")
        if webhook_event_id:
            # 去重：若已處理過則跳過
            is_new = await mark_event_processed(webhook_event_id)
            if not is_new:
                log.info("忽略重複 Webhook 事件: %s", webhook_event_id)
                continue

        asyncio.create_task(safe_handle_event(event))

    return Response(status_code=200, content="OK")


async def safe_handle_event(event: dict[str, Any]) -> None:
    """包裝非同步例外處理。"""
    try:
        await handle_event(event)
    except Exception:
        log.exception("背景執行 handle_event 失敗")
