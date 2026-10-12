"""排程端點（供 Google Cloud Scheduler 或定時服務呼叫）。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.db import cleanup, list_active_reminders, mark_reminder_sent
from app.flex_messages import build_daily_quick_reply
from app.line_api import line

log = logging.getLogger(__name__)
router = APIRouter(prefix="/cron")


def verify_cron_auth(authorization: str | None = Header(None)) -> None:
    """檢查 Cron Bearer Token。"""
    secret = get_settings().cron_secret
    expected = f"Bearer {secret}"
    if not authorization or authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized cron trigger")


@router.post("/daily-reminders")
async def trigger_daily_reminders(authorization: str | None = Header(None)) -> dict[str, Any]:
    """定時發送提醒（量體重、喝水、透析日提醒）。"""
    verify_cron_auth(authorization)

    today = date.today()
    weekday = today.isoweekday()  # 1=週一, 7=週日
    now_time = datetime.now(get_settings().tz).time()

    reminders = await list_active_reminders()
    sent_count = 0

    for rem in reminders:
        # 檢查星期
        days = rem.get("days_of_week") or [1, 2, 3, 4, 5, 6, 7]
        if weekday not in days:
            continue

        # 檢查今天是否已發過
        if rem.get("last_sent_on") == today.isoformat():
            continue

        family = rem.get("families") or {}
        patient_nickname = family.get("patient_nickname") or "長輩"
        target_id = family.get("line_group_id")

        if not target_id:
            continue

        kind = rem.get("kind")
        text = rem.get("message")

        if not text:
            if kind == "weight":
                text = f"☀️ 早安！提醒{patient_nickname}量一下晨起體重喔！記得先上完洗手間、穿輕便衣物再測量 ⚖️"
            elif kind == "dialysis":
                text = f"🏥 提醒：今天是{patient_nickname}的透析日！出門前別忘了帶健保卡、透析手冊與保暖外套喔！"
            elif kind == "water":
                text = f"💧 下午茶時間到了！記得控制喝水量，口渴的話可以含一小片檸檬或小冰塊潤潤喉嚨 🍋"
            else:
                text = f"🔔 貼心提醒時間到了，祝{patient_nickname}今天精神飽滿！"

        try:
            msg: dict[str, Any] = {
                "type": "text",
                "text": text,
                "quickReply": build_daily_quick_reply(),
            }
            await line().push(target_id, [msg])
            await mark_reminder_sent(rem["id"], today)
            sent_count += 1
        except Exception as e:
            log.warning("推播提醒失敗 reminder_id=%s: %s", rem.get("id"), e)

    return {"status": "ok", "sent_reminders": sent_count}


@router.post("/cleanup")
async def trigger_cleanup(authorization: str | None = Header(None)) -> dict[str, str]:
    """定期清理過期的對話狀態與舊 webhook 去重紀錄。"""
    verify_cron_auth(authorization)
    await cleanup()
    return {"status": "cleaned"}
