"""Supabase 資料存取層（service role，僅後端）。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from supabase import AsyncClient, acreate_client

from app.config import get_settings

_client: AsyncClient | None = None
_lock = asyncio.Lock()


async def db() -> AsyncClient:
    """取得 Supabase async client。"""
    global _client
    if _client is None:
        async with _lock:
            if _client is None:
                s = get_settings()
                _client = await acreate_client(s.supabase_url, s.supabase_service_role_key)
    return _client


def _first(data: Any) -> dict[str, Any] | None:
    if isinstance(data, list):
        return data[0] if data else None
    return data


def _iso(d: date | datetime) -> str:
    return d.isoformat()


# ---------------------------------------------------------------------
# webhook 去重
# ---------------------------------------------------------------------


async def mark_event_processed(event_id: str) -> bool:
    """首次看到回 True；重送的事件回 False。"""
    c = await db()
    res = await (
        c.table("webhook_events")
        .upsert({"event_id": event_id}, on_conflict="event_id", ignore_duplicates=True)
        .execute()
    )
    return bool(res.data)


# ---------------------------------------------------------------------
# users / families / members
# ---------------------------------------------------------------------


async def get_user(line_user_id: str) -> dict[str, Any] | None:
    """依 LINE ID 取使用者。"""
    c = await db()
    res = await c.table("users").select("*").eq("line_user_id", line_user_id).limit(1).execute()
    return _first(res.data)


async def upsert_user(line_user_id: str, display_name: str | None) -> dict[str, Any]:
    """建立或更新使用者。"""
    c = await db()
    row: dict[str, Any] = {"line_user_id": line_user_id}
    if display_name:
        row["display_name"] = display_name
    res = await c.table("users").upsert(row, on_conflict="line_user_id").execute()
    return res.data[0]


async def update_user(user_id: str, **fields: Any) -> None:
    """更新使用者欄位。"""
    c = await db()
    await c.table("users").update(fields).eq("id", user_id).execute()


async def get_family(family_id: str) -> dict[str, Any] | None:
    """取家庭。"""
    c = await db()
    res = await c.table("families").select("*").eq("id", family_id).limit(1).execute()
    return _first(res.data)


async def get_family_by_group(group_id: str) -> dict[str, Any] | None:
    """依群組 ID 取家庭。"""
    c = await db()
    res = await c.table("families").select("*").eq("line_group_id", group_id).limit(1).execute()
    return _first(res.data)


async def create_family(group_id: str | None, display_name: str | None) -> dict[str, Any]:
    """建立家庭。"""
    c = await db()
    row = {"line_group_id": group_id, "display_name": display_name}
    if group_id:
        res = await c.table("families").upsert(row, on_conflict="line_group_id").execute()
    else:
        res = await c.table("families").insert(row).execute()
    return res.data[0]


async def update_family(family_id: str, **fields: Any) -> dict[str, Any]:
    """更新家庭欄位。"""
    c = await db()
    res = await c.table("families").update(fields).eq("id", family_id).execute()
    return res.data[0]


async def list_families_with_sheet() -> list[dict[str, Any]]:
    """有綁定試算表的家庭。"""
    c = await db()
    res = await c.table("families").select("*").not_.is_("sheet_id", "null").execute()
    return res.data


async def get_membership(family_id: str, user_id: str) -> dict[str, Any] | None:
    """取成員關係。"""
    c = await db()
    res = await (
        c.table("family_members").select("*").eq("family_id", family_id).eq("user_id", user_id).limit(1).execute()
    )
    return _first(res.data)


async def ensure_membership(family_id: str, user_id: str) -> dict[str, Any]:
    """確保使用者是家庭成員（不覆寫既有角色）。"""
    existing = await get_membership(family_id, user_id)
    if existing:
        return existing
    c = await db()
    res = await (
        c.table("family_members")
        .upsert({"family_id": family_id, "user_id": user_id}, on_conflict="family_id,user_id", ignore_duplicates=True)
        .execute()
    )
    return _first(res.data) or (await get_membership(family_id, user_id)) or {}


async def update_membership(family_id: str, user_id: str, **fields: Any) -> None:
    """更新成員角色/通知設定。"""
    c = await db()
    await c.table("family_members").update(fields).eq("family_id", family_id).eq("user_id", user_id).execute()


async def list_members(family_id: str) -> list[dict[str, Any]]:
    """家庭成員（含 users 欄位）。"""
    c = await db()
    res = await (
        c.table("family_members")
        .select("role, notify_alerts, users(id, line_user_id, display_name)")
        .eq("family_id", family_id)
        .execute()
    )
    return res.data


async def remove_member(family_id: str, line_user_id: str) -> None:
    """成員離開群組。"""
    user = await get_user(line_user_id)
    if not user:
        return
    c = await db()
    await c.table("family_members").delete().eq("family_id", family_id).eq("user_id", user["id"]).execute()


async def list_user_memberships(user_id: str) -> list[dict[str, Any]]:
    """取使用者的所有家庭成員關係。"""
    c = await db()
    res = await c.table("family_members").select("*").eq("user_id", user_id).order("created_at").execute()
    return res.data


# ---------------------------------------------------------------------
# medical_reports
# ---------------------------------------------------------------------

REPORT_FIELDS = [
    "potassium", "phosphorus", "calcium", "hemoglobin", "sodium",
    "albumin", "bun", "creatinine", "kt_v", "ipth",
]


async def insert_reports(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """新增報告（草稿或確認）。"""
    c = await db()
    res = await c.table("medical_reports").insert(rows).execute()
    return res.data


async def get_report(report_id: str) -> dict[str, Any] | None:
    """取單筆報告。"""
    c = await db()
    res = await c.table("medical_reports").select("*").eq("id", report_id).limit(1).execute()
    return _first(res.data)


async def list_batch(batch_id: str) -> list[dict[str, Any]]:
    """同一張照片辨識出的報告（依日期）。"""
    c = await db()
    res = await c.table("medical_reports").select("*").eq("batch_id", batch_id).order("test_date").execute()
    return res.data


async def update_report(report_id: str, **fields: Any) -> dict[str, Any]:
    """更新報告。"""
    c = await db()
    res = await c.table("medical_reports").update(fields).eq("id", report_id).execute()
    return res.data[0]


async def find_confirmed(family_id: str, test_date: str) -> dict[str, Any] | None:
    """同日已確認的報告。"""
    c = await db()
    res = await (
        c.table("medical_reports")
        .select("*")
        .eq("family_id", family_id)
        .eq("test_date", test_date)
        .eq("status", "confirmed")
        .limit(1)
        .execute()
    )
    return _first(res.data)


async def confirm_report(draft: dict[str, Any]) -> dict[str, Any]:
    """確認草稿。若同日已有確認資料 → 以新值補上/覆寫，草稿標為 discarded。"""
    now = datetime.now(timezone.utc).isoformat()
    existing = await find_confirmed(draft["family_id"], draft["test_date"])
    if existing and existing["id"] != draft["id"]:
        patch = {k: draft[k] for k in REPORT_FIELDS if draft.get(k) is not None}
        patch["confirmed_at"] = now
        merged = await update_report(existing["id"], **patch)
        await update_report(draft["id"], status="discarded")
        return merged
    return await update_report(draft["id"], status="confirmed", confirmed_at=now)


async def list_confirmed_reports(family_id: str, limit: int = 12) -> list[dict[str, Any]]:
    """最近 N 期已確認報告（舊→新）。"""
    c = await db()
    res = await (
        c.table("medical_reports")
        .select("*")
        .eq("family_id", family_id)
        .eq("status", "confirmed")
        .order("test_date", desc=True)
        .limit(limit)
        .execute()
    )
    return list(reversed(res.data))


async def upsert_confirmed_report(family_id: str, test_date: str, fields: dict[str, Any], source: str) -> dict[str, Any]:
    """（Sheets 匯入用）同日有就更新，沒有就新增確認資料。partial unique index 無法用 PostgREST upsert。"""
    existing = await find_confirmed(family_id, test_date)
    if existing:
        return await update_report(existing["id"], **fields, source=source)
    rows = await insert_reports(
        [{
            "family_id": family_id,
            "test_date": test_date,
            "status": "confirmed",
            "source": source,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            **fields,
        }]
    )
    return rows[0]


# ---------------------------------------------------------------------
# daily_records
# ---------------------------------------------------------------------


async def upsert_daily(family_id: str, record_date: date, user_id: str | None, **fields: Any) -> dict[str, Any]:
    """寫入當日紀錄（只更新給定欄位）。"""
    c = await db()
    row = {"family_id": family_id, "record_date": _iso(record_date), "updated_by": user_id, **fields}
    res = await c.table("daily_records").upsert(row, on_conflict="family_id,record_date").execute()
    return res.data[0]


async def add_water(family_id: str, record_date: date, ml: int, user_id: str | None) -> int:
    """原子累加喝水量，回傳當日總量。"""
    c = await db()
    res = await c.rpc(
        "add_water",
        {"p_family_id": family_id, "p_date": _iso(record_date), "p_ml": ml, "p_user_id": user_id},
    ).execute()
    return int(res.data or 0)


async def get_daily(family_id: str, record_date: date) -> dict[str, Any] | None:
    """取當日紀錄。"""
    c = await db()
    res = await (
        c.table("daily_records")
        .select("*")
        .eq("family_id", family_id)
        .eq("record_date", _iso(record_date))
        .limit(1)
        .execute()
    )
    return _first(res.data)


async def list_daily(family_id: str, since: date) -> list[dict[str, Any]]:
    """某日之後的日常紀錄（舊→新）。"""
    c = await db()
    res = await (
        c.table("daily_records")
        .select("*")
        .eq("family_id", family_id)
        .gte("record_date", _iso(since))
        .order("record_date")
        .execute()
    )
    return res.data


async def last_weight(family_id: str) -> float | None:
    """最近一次體重。"""
    c = await db()
    res = await (
        c.table("daily_records")
        .select("weight_kg")
        .eq("family_id", family_id)
        .not_.is_("weight_kg", "null")
        .order("record_date", desc=True)
        .limit(1)
        .execute()
    )
    row = _first(res.data)
    return float(row["weight_kg"]) if row else None


# ---------------------------------------------------------------------
# care_rules / ai_advices
# ---------------------------------------------------------------------


async def list_rules(family_id: str) -> list[dict[str, Any]]:
    """全域 + 家庭專屬規則（priority 小者優先）。"""
    c = await db()
    res = await (
        c.table("care_rules")
        .select("*")
        .eq("is_active", True)
        .or_(f"family_id.eq.{family_id},family_id.is.null")
        .order("priority")
        .execute()
    )
    return res.data


async def insert_rule(row: dict[str, Any]) -> dict[str, Any]:
    """新增規則。"""
    c = await db()
    res = await c.table("care_rules").insert(row).execute()
    return res.data[0]


async def list_family_rules(family_id: str) -> list[dict[str, Any]]:
    """家庭自訂規則。"""
    c = await db()
    res = await (
        c.table("care_rules").select("*").eq("family_id", family_id).eq("is_active", True).order("created_at").execute()
    )
    return res.data


async def deactivate_rule(rule_id: str, family_id: str) -> None:
    """停用自訂規則。"""
    c = await db()
    await c.table("care_rules").update({"is_active": False}).eq("id", rule_id).eq("family_id", family_id).execute()


async def insert_advice(row: dict[str, Any]) -> dict[str, Any]:
    """儲存 AI 建議。"""
    c = await db()
    res = await c.table("ai_advices").insert(row).execute()
    return res.data[0]


async def get_advice(advice_id: str) -> dict[str, Any] | None:
    """取 AI 建議。"""
    c = await db()
    res = await c.table("ai_advices").select("*").eq("id", advice_id).limit(1).execute()
    return _first(res.data)


async def latest_advice(family_id: str) -> dict[str, Any] | None:
    """最近一則建議。"""
    c = await db()
    res = await (
        c.table("ai_advices").select("*").eq("family_id", family_id).order("created_at", desc=True).limit(1).execute()
    )
    return _first(res.data)


async def update_advice(advice_id: str, **fields: Any) -> None:
    """更新建議（語音路徑）。"""
    c = await db()
    await c.table("ai_advices").update(fields).eq("id", advice_id).execute()


# ---------------------------------------------------------------------
# conversation_states
# ---------------------------------------------------------------------


async def get_state(line_user_id: str, context_id: str) -> dict[str, Any] | None:
    """取未過期的對話狀態。"""
    c = await db()
    res = await (
        c.table("conversation_states")
        .select("*")
        .eq("line_user_id", line_user_id)
        .eq("context_id", context_id)
        .gt("expires_at", datetime.now(timezone.utc).isoformat())
        .limit(1)
        .execute()
    )
    return _first(res.data)


async def set_state(
    line_user_id: str, context_id: str, state: str, payload: dict[str, Any] | None = None, ttl_minutes: int = 10
) -> None:
    """設定對話狀態。"""
    c = await db()
    await c.table("conversation_states").upsert(
        {
            "line_user_id": line_user_id,
            "context_id": context_id,
            "state": state,
            "payload": payload or {},
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat(),
        },
        on_conflict="line_user_id,context_id",
    ).execute()


async def clear_state(line_user_id: str, context_id: str) -> None:
    """清除對話狀態。"""
    c = await db()
    await c.table("conversation_states").delete().eq("line_user_id", line_user_id).eq("context_id", context_id).execute()


async def group_has_pending_upload(context_id: str) -> bool:
    """群組內是否有人剛按「上傳報告」。"""
    c = await db()
    res = await (
        c.table("conversation_states")
        .select("line_user_id")
        .eq("context_id", context_id)
        .eq("state", "awaiting_report")
        .gt("expires_at", datetime.now(timezone.utc).isoformat())
        .limit(1)
        .execute()
    )
    return bool(res.data)


async def cleanup() -> None:
    """清理過期狀態與舊 webhook 紀錄。"""
    c = await db()
    now = datetime.now(timezone.utc)
    await c.table("conversation_states").delete().lt("expires_at", now.isoformat()).execute()
    await c.table("webhook_events").delete().lt("received_at", (now - timedelta(days=3)).isoformat()).execute()


# ---------------------------------------------------------------------
# reminders
# ---------------------------------------------------------------------


async def list_reminders(family_id: str) -> list[dict[str, Any]]:
    """家庭的提醒設定。"""
    c = await db()
    res = await c.table("reminders").select("*").eq("family_id", family_id).order("kind").execute()
    return res.data


async def list_active_reminders() -> list[dict[str, Any]]:
    """所有啟用中的提醒（含家庭資訊）。"""
    c = await db()
    res = await c.table("reminders").select("*, families(*)").eq("is_active", True).execute()
    return res.data


async def upsert_reminder(family_id: str, kind: str, **fields: Any) -> dict[str, Any]:
    """建立或更新提醒。"""
    c = await db()
    res = await (
        c.table("reminders")
        .upsert({"family_id": family_id, "kind": kind, **fields}, on_conflict="family_id,kind")
        .execute()
    )
    return res.data[0]


async def mark_reminder_sent(reminder_id: str, sent_on: date) -> None:
    """標記今天已送出。"""
    c = await db()
    await c.table("reminders").update({"last_sent_on": _iso(sent_on)}).eq("id", reminder_id).execute()


def new_batch_id() -> str:
    """產生 batch id。"""
    return str(uuid.uuid4())
