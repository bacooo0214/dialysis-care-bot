"""LINE Bot 核心事件處理器與對話流程控制器。

支援：
1. 1:1 個人對話與多人家庭群組協作
2. 檢驗單照片 OCR -> 狀態卡片確認 -> 紅綠燈成績單 -> AI 白話建議 -> 語音播報
3. 異常指標主動 @ 標記家屬警報
4. 每日乾體重、血壓、水分攝取管理
5. 家屬專屬衛教經驗庫 (#經驗)
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date
from typing import Any

from app.config import get_settings
from app.db import (
    add_water,
    confirm_report,
    create_family,
    ensure_membership,
    get_advice,
    get_daily,
    get_family,
    get_family_by_group,
    get_report,
    get_state,
    get_user,
    insert_advice,
    insert_reports,
    insert_rule,
    latest_advice,
    list_confirmed_reports,
    list_members,
    list_rules,
    new_batch_id,
    set_state,
    clear_state,
    update_family,
    update_membership,
    update_report,
    upsert_daily,
    upsert_user,
)
from app.flex_messages import (
    build_charts_menu_flex,
    build_daily_quick_reply,
    build_disclaimer_flex,
    build_main_quick_reply,
    build_ocr_carousel,
    build_ocr_confirm_bubble,
    build_report_overview_flex,
)
from app.line_api import LineClient, line
from app.metrics import (
    CORE_METRICS,
    LEVEL_EMOJI,
    LEVEL_LABEL,
    Level,
    classify_bp,
    classify_water,
    classify_weight_gain,
    evaluate_report,
    get_metrics,
    worst_level,
)
from app.services import advice, charts, ocr, sheets, storage

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# 家庭與成員解析 Helper
# ---------------------------------------------------------------------


async def resolve_context(event: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    """從事件中解析出 (user, family, context_id)。"""
    source = event.get("source", {})
    user_id = source.get("userId") or "anonymous"
    group_id = source.get("groupId")
    room_id = source.get("roomId")

    context_id = group_id or room_id or user_id

    # 取或建立 User
    client = line()
    display_name = await client.get_display_name(user_id, group_id, room_id)
    user = await upsert_user(user_id, display_name)

    family = None
    if group_id:
        family = await get_family_by_group(group_id)
        if not family:
            group_name = await client.get_group_summary(group_id) or "家庭群組"
            family = await create_family(group_id, group_name)
    else:
        # 個人聊天：綁定 user 的 active_family_id 或建立個人家庭
        if user.get("active_family_id"):
            family = await get_family(user["active_family_id"])
        if not family:
            family = await create_family(None, f"{display_name or '長輩'}的家庭")
            await update_membership(family["id"], user["id"], role="elder")

    # 確保是成員
    await ensure_membership(family["id"], user["id"])
    return user, family, context_id


# ---------------------------------------------------------------------
# 主事件分發
# ---------------------------------------------------------------------


async def handle_event(event: dict[str, Any]) -> None:
    """處理單一 Webhook 事件。"""
    event_type = event.get("type")
    reply_token = event.get("replyToken")

    try:
        user, family, context_id = await resolve_context(event)

        if event_type == "message":
            msg = event.get("message", {})
            msg_type = msg.get("type")
            if msg_type == "text":
                await handle_text_message(event, user, family, context_id, msg.get("text", "").strip())
            elif msg_type == "image":
                await handle_image_message(event, user, family, context_id, msg.get("id"))

        elif event_type == "postback":
            await handle_postback(event, user, family, context_id)

        elif event_type in ("follow", "join"):
            await handle_welcome(event, family)

    except Exception:
        log.exception("處理事件失敗: %s", event)
        if reply_token and not reply_token.startswith("00000000"):
            try:
                await line().reply(
                    reply_token,
                    [{"type": "text", "text": "不好意思，系統剛剛稍微打了個瞌睡 🙇 請您再試一次！"}],
                )
            except Exception:
                pass


# ---------------------------------------------------------------------
# 歡迎與免責聲明
# ---------------------------------------------------------------------


async def handle_welcome(event: dict[str, Any], family: dict[str, Any]) -> None:
    """使用者加好友或機器人加入群組時的指引。"""
    reply_token = event.get("replyToken")
    if not reply_token:
        return

    welcome_text = (
        "您好！我是您的 AI 腎臟照護小幫手「腎好伴」🌱\n\n"
        "我可以幫您：\n"
        "📸 拍照辨識檢驗報告，自動轉為清晰紅綠燈成績單\n"
        "📈 繪製大字體的趨勢折線圖，掌握鉀、磷、血紅素變化\n"
        "💡 依據家庭經驗提供溫暖的白話飲食與生活建議\n"
        "⚖️ 快速紀錄每日體重、血壓與喝水量\n\n"
        "開始使用前，請點選下方按鈕確認服務說明："
    )

    messages = [
        {"type": "text", "text": welcome_text},
        build_disclaimer_flex(),
    ]
    await line().reply(reply_token, messages)


# ---------------------------------------------------------------------
# 照片上傳與 OCR
# ---------------------------------------------------------------------


async def handle_image_message(
    event: dict[str, Any],
    user: dict[str, Any],
    family: dict[str, Any],
    context_id: str,
    message_id: str,
) -> None:
    """處理照片上傳。"""
    reply_token = event.get("replyToken")
    user_id = user.get("line_user_id")

    # 1:1 對話觸發 loading 動畫
    await line().show_loading(user_id, seconds=30)

    # 下載圖片內容
    image_bytes, mime_type = await line().get_content(message_id)

    # 呼叫 Gemini Vision OCR 辨識
    try:
        ocr_result = await ocr.recognize(image_bytes, mime_type=mime_type)
    except Exception as e:
        log.exception("OCR 辨識失敗: %s", e)
        if reply_token:
            await line().reply(
                reply_token,
                [{"type": "text", "text": "辨識照片時發生問題，請確認照片清晰無反光後再拍一次看看喔！"}],
            )
        return

    if not ocr_result.is_lab_report or not ocr_result.reports:
        # 檢查是否為刻意上傳流程
        state = await get_state(user_id, context_id)
        if state and state.get("state") == "awaiting_report":
            await clear_state(user_id, context_id)
            if reply_token:
                await line().reply(
                    reply_token,
                    [{"type": "text", "text": "這張照片看起來不太像血液透析檢驗報告喔！請對準檢驗表格再拍一張試試看 📋"}],
                )
        return

    # 將辨識到的每筆報告存入 draft
    batch_id = new_batch_id()
    draft_rows: list[dict[str, Any]] = []
    for r in ocr_result.reports:
        row = ocr.report_to_row(r)
        row["family_id"] = family["id"]
        row["created_by"] = user["id"]
        row["status"] = "draft"
        row["batch_id"] = batch_id
        row["source"] = "ocr"
        draft_rows.append(row)

    saved_drafts = await insert_reports(draft_rows)

    # 產生確認卡片 (多期用 Carousel)
    overrides = family.get("metric_overrides")
    if len(saved_drafts) == 1:
        flex_msg = {
            "type": "flex",
            "altText": "檢驗單辨識結果確認",
            "contents": build_ocr_confirm_bubble(saved_drafts[0], overrides),
        }
    else:
        flex_msg = build_ocr_carousel(saved_drafts, overrides)

    prompt_text = (
        "✅ 已成功辨識檢驗報告！\n"
        "請核對下方卡片中的各項數值：\n"
        "👉 核對正確請直接點擊下方【數字正確，儲存】。\n"
        "⏳ 系統將於 3~5 秒內為您進行透析標準比對，生成紅綠燈成績單與專屬 AI 白話照護建議！"
    )
    if ocr_result.note:
        prompt_text += f"\n\n💡 備註：{ocr_result.note}"

    if reply_token:
        await line().reply(
            reply_token,
            [
                {
                    "type": "text",
                    "text": prompt_text,
                    "quickReply": build_main_quick_reply(),
                },
                flex_msg,
            ],
        )


# ---------------------------------------------------------------------
# Postback 事件處理
# ---------------------------------------------------------------------


async def handle_postback(
    event: dict[str, Any],
    user: dict[str, Any],
    family: dict[str, Any],
    context_id: str,
) -> None:
    """處理按鈕 Postback 回傳。"""
    reply_token = event.get("replyToken")
    data_str = event.get("postback", {}).get("data", "")
    params = dict(part.split("=", 1) for part in data_str.split("&") if "=" in part)
    action = params.get("action")
    user_id = user["line_user_id"]
    family_id = family["id"]
    patient_nickname = family.get("patient_nickname") or "長輩"

    if action == "confirm_report":
        report_id = params.get("id")
        # 立即啟動 LINE 官方載入中提示動畫
        await line().show_loading(user_id, seconds=30)

        draft = await get_report(report_id)
        if not draft:
            if reply_token:
                await line().reply(reply_token, [{"type": "text", "text": "找不到此份草稿或已處理過。"}])
            return

        # 1. 確認儲存
        confirmed = await confirm_report(draft)

        # 2. 抓取歷史以計算趨勢
        history = await list_confirmed_reports(family_id, limit=2)
        previous = history[0] if len(history) >= 2 else None

        # 3. 紅綠燈評估
        results = evaluate_report(confirmed, previous, family.get("metric_overrides"))

        # 4. 生成 AI 建議
        findings = advice.build_findings(results)
        rules = await list_rules(family_id)
        ai_res = await advice.generate_advice(patient_nickname, findings, rules)

        saved_advice = await insert_advice(
            {
                "family_id": family_id,
                "report_id": confirmed["id"],
                "text": ai_res.text,
                "speech_text": ai_res.speech,
            }
        )

        # 5. 背景非同步同步 Google Sheets
        if family.get("sheet_id"):
            asyncio.create_task(sheets.sync_report_to_sheet(family["sheet_id"], confirmed))

        # 6. 回傳成績單與 AI 建議卡片
        intro_msg = {
            "type": "text",
            "text": f"🎉 {patient_nickname} 的檢驗成績單分析完成！\n已為您對齊臨床透析安全標準，請參考下方紅綠燈評估：",
        }

        overview_flex = build_report_overview_flex(
            confirmed, results, patient_nickname, advice_id=saved_advice["id"]
        )

        advice_msg = {
            "type": "text",
            "text": f"💡 照護建議：\n\n{ai_res.text}",
            "quickReply": build_main_quick_reply(),
        }

        if reply_token:
            await line().reply(reply_token, [intro_msg, overview_flex, advice_msg])

        # 7. 異常警報：若有紅燈，主動在群組 @ 標記家屬
        red_findings = [f for f in findings if f.level == Level.RED]
        if red_findings and family.get("line_group_id"):
            asyncio.create_task(send_alert_mention(family, red_findings, patient_nickname))

    elif action == "edit_report_prompt":
        report_id = params.get("id")
        await set_state(user_id, context_id, "editing_report", {"report_id": report_id}, ttl_minutes=15)
        if reply_token:
            msg_text = (
                "請直接回覆您想修改的項目與數值，例如：\n"
                "👉 鉀 4.8\n"
                "👉 Hb 10.5\n"
                "👉 日期 2026-10-05\n\n"
                "（修改完畢後會重新為您產生成績單）"
            )
            await line().reply(reply_token, [{"type": "text", "text": msg_text}])

    elif action == "discard_report":
        report_id = params.get("id")
        if report_id:
            await update_report(report_id, status="discarded")
        if reply_token:
            await line().reply(reply_token, [{"type": "text", "text": "已捨棄該份辨識紀錄 🗑️"}])

    elif action == "view_charts_menu":
        if reply_token:
            await line().reply(reply_token, [build_charts_menu_flex(patient_nickname)])

    elif action == "render_chart":
        metric_key = params.get("metric", "summary")
        await line().show_loading(user_id, seconds=20)

        # 抓取歷史報告
        history = await list_confirmed_reports(family_id, limit=12)
        if not history:
            if reply_token:
                await line().reply(reply_token, [{"type": "text", "text": "目前還沒有已確認的檢驗紀錄喔！請先上傳報告照片 📸"}])
            return

        if metric_key == "summary":
            png_bytes = charts.render_summary_dashboard(history[-1], patient_nickname, family.get("metric_overrides"))
        else:
            png_bytes = charts.render_metric_trend(metric_key, history, patient_nickname, family.get("metric_overrides"))

        # 上傳並取得 signed URL
        _path, img_url = await storage.upload_and_sign(
            family_id=family_id,
            folder="charts",
            data=png_bytes,
            content_type="image/png",
            ext="png",
        )

        img_message = {
            "type": "image",
            "originalContentUrl": img_url,
            "previewImageUrl": img_url,
            "quickReply": build_daily_quick_reply(),
        }

        if reply_token:
            await line().reply(reply_token, [img_message])

    elif action == "play_tts":
        if reply_token:
            await line().reply(reply_token, [{"type": "text", "text": "語音播報功能目前已關閉。"}])

    elif action == "accept_disclaimer":
        from datetime import datetime, timezone
        await update_family(
            family_id,
            disclaimer_accepted_at=datetime.now(timezone.utc).isoformat(),
            disclaimer_accepted_by=user["id"],
        )
        if reply_token:
            await line().reply(
                reply_token,
                [
                    {
                        "type": "text",
                        "text": f"感謝您的信任！已完成綁定。隨時拍照上傳檢驗單，或點選下方選單開始使用囉 😊",
                        "quickReply": build_daily_quick_reply(),
                    }
                ],
            )

    elif action == "prompt_weight":
        await set_state(user_id, context_id, "awaiting_weight", ttl_minutes=5)
        if reply_token:
            await line().reply(reply_token, [{"type": "text", "text": "請輸入今日測量的體重（公斤），例如：58.5"}])

    elif action == "prompt_bp":
        await set_state(user_id, context_id, "awaiting_bp", ttl_minutes=5)
        if reply_token:
            await line().reply(reply_token, [{"type": "text", "text": "請輸入今日測量的血壓，例如：132/82"}])


# ---------------------------------------------------------------------
# 文字訊息處理
# ---------------------------------------------------------------------


async def handle_text_message(
    event: dict[str, Any],
    user: dict[str, Any],
    family: dict[str, Any],
    context_id: str,
    text: str,
) -> None:
    """處理使用者發送的文字訊息。"""
    reply_token = event.get("replyToken")
    user_id = user["line_user_id"]
    family_id = family["id"]
    today = date.today()
    patient_nickname = family.get("patient_nickname") or "長輩"

    # 1. 檢查對話狀態機 (FSM)
    state = await get_state(user_id, context_id)
    if state:
        st_name = state.get("state")
        payload = state.get("payload", {})

        if st_name == "editing_report":
            await handle_editing_report_text(reply_token, user_id, context_id, family, payload, text)
            return

        if st_name == "awaiting_weight":
            await clear_state(user_id, context_id)
            match = re.search(r"(\d{2,3}(?:\.\d{1,2})?)", text)
            if match:
                w_val = float(match.group(1))
                await record_weight(reply_token, family, user, w_val, today)
                return

        if st_name == "awaiting_bp":
            await clear_state(user_id, context_id)
            match = re.search(r"(\d{2,3})\s*[/, ]\s*(\d{2,3})", text)
            if match:
                sys_v, dia_v = int(match.group(1)), int(match.group(2))
                await record_bp(reply_token, family, user, sys_v, dia_v, today)
                return

    # 2. 喝水指令：「喝水 200」、「+100」、「喝了 150cc」
    water_match = re.search(r"(?:喝水|\+)\s*(\d{1,4})", text)
    if water_match:
        ml = int(water_match.group(1))
        total_ml = await add_water(family_id, today, ml, user["id"])
        limit_ml = family.get("daily_water_limit_ml") or 1000
        lv = classify_water(total_ml, limit_ml)
        pct = int(total_ml / limit_ml * 100) if limit_ml > 0 else 0

        reply_str = f"💧 已為{patient_nickname}記錄喝水 {ml} ml\n" f"今日累積：{total_ml} / {limit_ml} ml ({pct}%)\n"
        if lv == Level.GREEN:
            reply_str += "🟢 控制得很好，繼續保持！"
        elif lv == Level.YELLOW:
            reply_str += "🟡 水分已接近上限，口渴時可含冰塊或小口潤喉喔！"
        else:
            reply_str += "🔴 今日水分已超標，請多注意透析間體重增加，避免喝湯！"

        # 背景同步 Sheets
        if family.get("sheet_id"):
            asyncio.create_task(sync_daily_background(family_id, today, family["sheet_id"]))

        if reply_token:
            await line().reply(reply_token, [{"type": "text", "text": reply_str, "quickReply": build_daily_quick_reply()}])
        return

    # 3. 體重指令：「記體重 58.5」、「體重 58.5」
    weight_match = re.match(r"^(?:記體重|體重)\s*(\d{2,3}(?:\.\d{1,2})?)", text)
    if weight_match:
        w_val = float(weight_match.group(1))
        await record_weight(reply_token, family, user, w_val, today)
        return

    # 4. 血壓指令：「記血壓 130/80」、「血壓 130/80」
    bp_match = re.match(r"^(?:記血壓|血壓)\s*(\d{2,3})\s*[/, ]\s*(\d{2,3})", text)
    if bp_match:
        sys_v, dia_v = int(bp_match.group(1)), int(bp_match.group(2))
        await record_bp(reply_token, family, user, sys_v, dia_v, today)
        return

    # 5. 家屬自訂衛教經驗：「#經驗 ...」
    if text.startswith("#經驗") or text.startswith("＃經驗"):
        content = text[3:].strip()
        if not content:
            if reply_token:
                await line().reply(reply_token, [{"type": "text", "text": "請在 #經驗 後面輸入衛教內容，例如：\n#經驗 青菜切小段燙 3 分鐘去鉀"}])
            return

        cls_res = await advice.classify_rule(content)
        await insert_rule(
            {
                "family_id": family_id,
                "metric": cls_res.metric,
                "direction": cls_res.direction,
                "min_level": "yellow",
                "title": cls_res.title,
                "content": content,
                "priority": 10,  # 家屬自訂優先採用
                "created_by": user["id"],
            }
        )

        resp_msg = f"✅ 已成功收錄家庭專屬照護經驗！\n📌 標題：{cls_res.title}\n對應項目：{cls_res.metric or '通用'}\n\n未來產生成績單與建議時，AI 會優先融入這項寶貴經驗！"
        if reply_token:
            await line().reply(reply_token, [{"type": "text", "text": resp_msg}])
        return

    # 6. 基本設定指令
    # 「設定乾體重 55」
    set_dw_match = re.match(r"^設定乾體重\s*(\d{2,3}(?:\.\d{1,2})?)", text)
    if set_dw_match:
        dw = float(set_dw_match.group(1))
        await update_family(family_id, dry_weight_kg=dw)
        if reply_token:
            await line().reply(reply_token, [{"type": "text", "text": f"✅ 已將{patient_nickname}的基準乾體重設定為 {dw} kg"}])
        return

    # 「設定稱呼 爸爸」
    set_nick_match = re.match(r"^設定稱呼\s*(.+)", text)
    if set_nick_match:
        nick = set_nick_match.group(1).strip()
        await update_family(family_id, patient_nickname=nick)
        if reply_token:
            await line().reply(reply_token, [{"type": "text", "text": f"✅ 以後我會用「{nick}」來稱呼長輩喔！"}])
        return

    # 「設定限水 1200」
    set_water_match = re.match(r"^設定限水\s*(\d{3,4})", text)
    if set_water_match:
        limit = int(set_water_match.group(1))
        await update_family(family_id, daily_water_limit_ml=limit)
        if reply_token:
            await line().reply(reply_token, [{"type": "text", "text": f"✅ 已將每日水分上限設定為 {limit} ml"}])
        return

    # 7. 查詢指令
    if text in ("看報告", "成績單", "最新報告"):
        history = await list_confirmed_reports(family_id, limit=2)
        if not history:
            if reply_token:
                await line().reply(reply_token, [{"type": "text", "text": f"目前尚無{patient_nickname}的檢驗資料，請先拍照上傳檢驗單喔！"}])
            return
        latest = history[-1]
        prev = history[-2] if len(history) >= 2 else None
        results = evaluate_report(latest, prev, family.get("metric_overrides"))
        adv = await latest_advice(family_id)
        flex_msg = build_report_overview_flex(latest, results, patient_nickname, advice_id=adv.get("id") if adv else None)
        if reply_token:
            await line().reply(reply_token, [flex_msg])
        return

    if text in ("看趨勢", "看圖表", "趨勢圖"):
        if reply_token:
            await line().reply(reply_token, [build_charts_menu_flex(patient_nickname)])
        return

    if text in ("今日狀況", "今日紀錄", "今日數據"):
        rec = await get_daily(family_id, today)
        dw = family.get("dry_weight_kg")
        limit_ml = family.get("daily_water_limit_ml") or 1000

        w_str = f"{rec.get('weight_kg')} kg" if rec and rec.get("weight_kg") else "尚未測量"
        bp_str = f"{rec.get('systolic')}/{rec.get('diastolic')} mmHg" if rec and rec.get("systolic") else "尚未測量"
        water_str = f"{rec.get('water_ml', 0)} / {limit_ml} ml" if rec else f"0 / {limit_ml} ml"

        summary_text = (
            f"📅 {patient_nickname} 今日自主管理狀況 ({today.isoformat()})\n\n"
            f"⚖️ 體重：{w_str} (乾體重: {dw or '未設定'} kg)\n"
            f"❤️ 血壓：{bp_str}\n"
            f"💧 喝水量：{water_str}\n"
        )
        if reply_token:
            await line().reply(
                reply_token,
                [{"type": "text", "text": summary_text, "quickReply": build_daily_quick_reply()}],
            )
        return

    if text in ("上傳報告", "拍照上傳"):
        await set_state(user_id, context_id, "awaiting_report", ttl_minutes=5)
        if reply_token:
            await line().reply(reply_token, [{"type": "text", "text": "請直接拍下「血液透析檢驗紀錄表」並傳送到這裡 📷"}])
        return

    # 若在 1:1 個人對話，且輸入長輩問答，AI 友善回答
    if not family.get("line_group_id"):
        # 個人對話時提供通用說明
        if reply_token:
            await line().reply(
                reply_token,
                [
                    {
                        "type": "text",
                        "text": f"您好！您可以直接拍照上傳檢驗單，或點選下方快捷功能按鈕：",
                        "quickReply": build_daily_quick_reply(),
                    }
                ],
            )


# ---------------------------------------------------------------------
# 日常數據寫入 Helper
# ---------------------------------------------------------------------


async def record_weight(
    reply_token: str | None,
    family: dict[str, Any],
    user: dict[str, Any],
    weight: float,
    rec_date: date,
) -> None:
    """記錄體重並計算乾體重增幅。"""
    family_id = family["id"]
    patient_nickname = family.get("patient_nickname") or "長輩"
    dry_weight = family.get("dry_weight_kg")

    await upsert_daily(family_id, rec_date, user["id"], weight_kg=weight)

    lv, pct = classify_weight_gain(weight, dry_weight)
    resp = f"⚖️ 已記錄{patient_nickname}今日體重：{weight} kg\n"

    if dry_weight:
        diff = round(weight - dry_weight, 1)
        sign = "+" if diff > 0 else ""
        resp += f"與乾體重 ({dry_weight} kg) 相比：{sign}{diff} kg ({pct:.1f}%)\n"
        if lv == Level.GREEN:
            resp += "🟢 體重增加在 3% 以內，水份控制極佳！"
        elif lv == Level.YELLOW:
            resp += "🟡 體重稍微偏多，今天要注意飲食與喝水量喔！"
        else:
            resp += "🔴 體重增加超過 5%，心臟負擔較大，若躺下會喘請即時聯絡護理師！"
    else:
        resp += "💡 尚未設定基準乾體重，可輸入「設定乾體重 55」以啟用體重增幅警示功能。"

    if family.get("sheet_id"):
        asyncio.create_task(sync_daily_background(family_id, rec_date, family["sheet_id"]))

    if reply_token:
        await line().reply(reply_token, [{"type": "text", "text": resp, "quickReply": build_daily_quick_reply()}])


async def record_bp(
    reply_token: str | None,
    family: dict[str, Any],
    user: dict[str, Any],
    sys_v: int,
    dia_v: int,
    rec_date: date,
) -> None:
    """記錄血壓並判讀紅綠燈。"""
    family_id = family["id"]
    patient_nickname = family.get("patient_nickname") or "長輩"

    await upsert_daily(family_id, rec_date, user["id"], systolic=sys_v, diastolic=dia_v)
    lv, direction = classify_bp(sys_v, dia_v)

    resp = f"❤️ 已記錄{patient_nickname}今日血壓：{sys_v}/{dia_v} mmHg\n"
    if lv == Level.GREEN:
        resp += "🟢 血壓平穩，非常棒！"
    elif lv == Level.YELLOW:
        if direction == "high":
            resp += "🟡 血壓稍微偏高，少吃重口味，先坐著休息放鬆一下。"
        else:
            resp += "🟡 血壓稍微偏低，站起來時要慢慢來，避免頭暈跌倒。"
    else:
        if direction == "high":
            resp += "🔴 血壓偏高很多，若有劇烈頭痛或胸悶，請立即就醫！"
        else:
            resp += "🔴 血壓很低，請先躺平休息，補充少量水分並聯絡醫護人員！"

    if family.get("sheet_id"):
        asyncio.create_task(sync_daily_background(family_id, rec_date, family["sheet_id"]))

    if reply_token:
        await line().reply(reply_token, [{"type": "text", "text": resp, "quickReply": build_daily_quick_reply()}])


async def sync_daily_background(family_id: str, rec_date: date, sheet_id: str) -> None:
    """背景將最新每日紀錄同步至 Sheets。"""
    rec = await get_daily(family_id, rec_date)
    if rec:
        await sheets.sync_daily_to_sheet(sheet_id, rec)


# ---------------------------------------------------------------------
# 手動修改數值處理
# ---------------------------------------------------------------------


async def handle_editing_report_text(
    reply_token: str | None,
    user_id: str,
    context_id: str,
    family: dict[str, Any],
    payload: dict[str, Any],
    text: str,
) -> None:
    """處理修改報告數值的輸入。"""
    report_id = payload.get("report_id")
    draft = await get_report(report_id)
    if not draft:
        await clear_state(user_id, context_id)
        if reply_token:
            await line().reply(reply_token, [{"type": "text", "text": "找不到對應的報告草稿。"}])
        return

    # 解析文字中的項目與數值，例如「鉀 4.5」、「Hb 10.2」、「日期 2026-10-12」
    defs = get_metrics()
    updates: dict[str, Any] = {}

    # 日期檢查
    d_match = re.search(r"日期\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})", text)
    if d_match:
        updates["test_date"] = d_match.group(1).replace("/", "-").replace(".", "-")

    for k, m in defs.items():
        pattern = rf"(?:{m.name}|{m.code})\s*[:=]?\s*(\d+(?:\.\d+)?)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            updates[k] = float(match.group(1))

    if not updates:
        if reply_token:
            await line().reply(
                reply_token,
                [{"type": "text", "text": "無法識別您想修改的項目，請依照格式輸入，例如：「鉀 4.8」或「血紅素 10.2」"}],
            )
        return

    # 更新報告
    updated_draft = await update_report(report_id, **updates)
    await clear_state(user_id, context_id)

    # 重新送出確認卡片
    flex_msg = {
        "type": "flex",
        "altText": "已更新檢驗數據，請核對",
        "contents": build_ocr_confirm_bubble(updated_draft, family.get("metric_overrides")),
    }
    if reply_token:
        await line().reply(reply_token, [{"type": "text", "text": "✅ 數值已更新！請再次核對："}, flex_msg])


# ---------------------------------------------------------------------
# 異常警報主動 @ 家屬
# ---------------------------------------------------------------------


async def send_alert_mention(family: dict[str, Any], red_findings: list[Any], patient_nickname: str) -> None:
    """使用 LINE Messaging API (TextMessageV2) 標記群組中的家屬。"""
    group_id = family.get("line_group_id")
    if not group_id:
        return

    members = await list_members(family["id"])
    family_members = [
        m for m in members if m.get("role") == "family" and m.get("notify_alerts")
    ]
    if not family_members:
        return

    names = "、".join(f.name for f in red_findings)

    # 組建 TextMessageV2 格式
    substitutions: dict[str, Any] = {}
    mention_tokens: list[str] = []
    for idx, fm in enumerate(family_members[:5]):  # 最多一次標記 5 位
        u = fm.get("users", {})
        l_uid = u.get("line_user_id")
        if l_uid:
            key = f"user_{idx}"
            mention_tokens.append(f"${{{key}}}")
            substitutions[key] = {
                "type": "mention",
                "mentionee": {
                    "type": "user",
                    "userId": l_uid,
                },
            }

    if not mention_tokens:
        return

    mention_str = " ".join(mention_tokens)
    text_content = (
        f"🚨【異常數值提醒】\n"
        f"{mention_str}\n"
        f"{patient_nickname} 本次檢驗的【{names}】觸發紅燈警示，請家屬多加留意！\n"
        f"若有任何不適症狀，請儘速諮詢主治醫師或透析室護理師。"
    )

    message_payload = {
        "type": "textV2",
        "text": text_content,
        "substitution": substitutions,
    }

    try:
        await line().push(group_id, [message_payload])
    except Exception as e:
        log.warning("推播異常標記警報失敗: %s", e)
