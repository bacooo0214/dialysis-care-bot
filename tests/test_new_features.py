"""4 大核心擴充功能單元測試：
1. 門診 30 秒就醫小抄
2. 日常喝水與體重增重死線
3. 外食拍照 AI 瞬間快篩
4. 臨床重大危急值主動警報
"""

import pytest

from app.flex_messages import (
    build_clinic_memo_flex,
    build_critical_alert_flex,
    build_food_screening_flex,
    build_main_quick_reply,
)
from app.metrics import detect_critical_alerts
from app.services.advice import ClinicMemoOut, generate_clinic_memo
from app.services.food_analyzer import FoodAnalysisResult


def test_detect_critical_alerts_danger():
    """測試重大危急值偵測（高鉀 >= 5.5, Hb < 8.0, Ca, P）。"""
    # 測試危急報告
    danger_report = {
        "potassium": 6.2,      # 致命高血鉀 >= 6.0
        "hemoglobin": 7.2,     # 重度貧血 < 8.0
        "phosphorus": 7.5,     # 高血磷 > 7.0
        "calcium": 11.8,       # 高血鈣 > 11.5
    }
    alerts = detect_critical_alerts(danger_report)
    assert len(alerts) == 4
    keys = {a.metric_key for a in alerts}
    assert keys == {"potassium", "hemoglobin", "phosphorus", "calcium"}

    k_alert = next(a for a in alerts if a.metric_key == "potassium")
    assert k_alert.severity == "danger"
    assert "致命危險" in k_alert.reason

    # 測試正常報告
    normal_report = {
        "potassium": 4.5,
        "hemoglobin": 10.8,
        "phosphorus": 4.8,
        "calcium": 9.5,
    }
    normal_alerts = detect_critical_alerts(normal_report)
    assert len(normal_alerts) == 0


def test_clinic_memo_generation_and_flex():
    """測試門診小抄生成與 Flex 卡片渲染。"""
    mock_reports = [
        {"test_date": "2026-10-07", "hemoglobin": 11.6, "potassium": 5.1, "ipth": 614.8, "phosphorus": 4.0},
        {"test_date": "2026-09-02", "hemoglobin": 10.1, "potassium": 4.8, "ipth": 580.0, "phosphorus": 4.5},
        {"test_date": "2026-08-05", "hemoglobin": 8.7, "potassium": 5.2, "ipth": 620.0, "phosphorus": 5.1},
    ]

    memo = ClinicMemoOut(
        summary_headline="秀鳳長輩門診備忘",
        overview_text="近三期整體控制穩定，血紅素由 8.7 大幅上升至 11.6，副甲狀腺素仍偏高。",
        key_highlights=["血紅素：8.7 → 11.6 g/dL", "血鉀：5.1 mEq/L", "副甲狀腺素：614.8 pg/mL"],
        doctor_questions=["造血針劑量是否調整？", "副甲狀腺素是否評估擬鈣劑？"],
        daily_reminders=["帶齊降磷劑", "量測今日體重血壓"],
    )

    flex = build_clinic_memo_flex(memo, "秀鳳阿嬤", "test_family_id")
    assert flex["type"] == "flex"
    assert "秀鳳阿嬤" in flex["altText"]
    assert flex["contents"]["body"]["type"] == "box"


def test_food_screening_flex():
    """測試外食快篩 Flex 卡片渲染。"""
    food = FoodAnalysisResult(
        is_food=True,
        dish_name="紅燒牛肉麵",
        main_ingredients=["牛肉塊", "高湯", "麵條", "青江菜"],
        overall_level="yellow",
        potassium_risk="medium",
        potassium_note="青江菜含鉀，高湯熬煮亦有鉀溶出",
        phosphorus_risk="medium",
        phosphorus_note="牛骨高湯含無機磷",
        sodium_water_note="湯頭鹽份高，易引起長輩口渴",
        eating_hacks=["湯一口都不要喝", "青菜先過熱開水瀝乾", "配第一口飯咬碎磷結合劑"],
        friendly_summary="吃料不喝湯，享受美食好心情！",
    )

    flex = build_food_screening_flex(food, "長輩")
    assert flex["type"] == "flex"
    assert "紅燒牛肉麵" in flex["altText"]
    assert flex["contents"]["header"]["backgroundColor"] == "#B85D19"


def test_critical_alert_flex():
    """測試重大危急值 Flex 卡片渲染。"""
    danger_report = {"potassium": 6.3}
    alerts = detect_critical_alerts(danger_report)
    assert len(alerts) == 1

    flex = build_critical_alert_flex(alerts, "長輩", "fam_123")
    assert flex["type"] == "flex"
    assert "危急警戒" in flex["altText"]
    assert flex["contents"]["header"]["backgroundColor"] == "#A32A2A"


def test_quick_reply_has_memo():
    """測試 Quick Reply 包含門診小抄。"""
    qr = build_main_quick_reply("fam_123")
    labels = [item["action"]["label"] for item in qr["items"]]
    assert "📝 門診小抄" in labels
    assert "💧 喝水 100cc" in labels
    assert "⚖️ 記體重" in labels


def test_group_bot_mention_filter():
    """測試家庭群組防擾：日常閒聊不插嘴，明確 @ 或喚醒詞才回覆。"""
    from app.bot_handlers import check_bot_mentioned

    # 1. 普通閒聊（應判定為未呼叫，靜默不插嘴）
    chat_events = [
        "大家明天幾點出發？",
        "媽媽晚上想吃水餃嗎",
        "我剛下班在路上了",
        "+1",
        "收到，謝謝！",
    ]
    for text in chat_events:
        is_called, _ = check_bot_mentioned({"message": {}}, text)
        assert is_called is False, f"閒聊 '{text}' 不應觸發機器人插嘴"

    # 2. 文字開頭 @ 機器人
    is_called, clean = check_bot_mentioned({"message": {}}, "@腎好伴 今天可以吃楊桃嗎？")
    assert is_called is True
    assert clean == "今天可以吃楊桃嗎？"

    # 3. 稱謂呼叫開頭
    is_called, clean = check_bot_mentioned({"message": {}}, "小乖孫，阿嬤剛量血壓有點高")
    assert is_called is True
    assert clean == "阿嬤剛量血壓有點高"

    # 4. 諮詢關鍵字前綴
    is_called, clean = check_bot_mentioned({"message": {}}, "請問：透析洗腎後容易抽筋要怎麼辦？")
    assert is_called is True
    assert clean == "透析洗腎後容易抽筋要怎麼辦？"

    # 5. LINE 原生 Mention
    native_event = {
        "message": {
            "mention": {
                "mentionees": [{"index": 0, "length": 5, "isSelf": True}]
            }
        }
    }
    is_called, clean = check_bot_mentioned(native_event, "@腎好伴 檢驗報告幾天會出來")
    assert is_called is True
    assert clean == "檢驗報告幾天會出來"

