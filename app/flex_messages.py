"""LINE Flex Message 與訊息樣板建構器。

專為高齡友善介面設計：
- 高對比、大字體、清楚色塊
- 盡量使用按鈕與快速回覆取代打字
- 清楚的紅綠燈視覺提示
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.metrics import (
    CORE_METRICS,
    LEVEL_COLOR,
    LEVEL_EMOJI,
    LEVEL_LABEL,
    Level,
    MetricDef,
    MetricResult,
    get_metrics,
    worst_level,
)


def build_ocr_confirm_bubble(report: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """建立單期辨識結果確認卡片 (Flex Bubble)。"""
    defs = get_metrics(overrides)
    report_id = str(report["id"])
    test_date = str(report.get("test_date") or "未知日期")
    uncertain: list[str] = report.get("uncertain_fields") or []

    rows: list[dict[str, Any]] = []
    # 列出各個數值
    for k in CORE_METRICS:
        m = defs[k]
        val = report.get(k)
        if val is None:
            continue
        v_float = float(val)
        level = m.classify(v_float)
        is_uncertain = k in uncertain

        name_text = f"{m.name} ({m.code})"
        if is_uncertain:
            name_text += " ⚠️"

        rows.append(
            {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{LEVEL_EMOJI[level]} {name_text}",
                        "size": "md",
                        "color": "#1F2937",
                        "flex": 4,
                        "weight": "bold",
                    },
                    {
                        "type": "text",
                        "text": f"{m.fmt(v_float)} {m.unit}".strip(),
                        "size": "md",
                        "color": LEVEL_COLOR[level],
                        "align": "end",
                        "flex": 3,
                        "weight": "bold",
                    },
                ],
                "margin": "sm",
            }
        )

    # 補充項目 (BUN / Cr 等)
    for extra_key in ["bun", "creatinine"]:
        if report.get(extra_key) is not None:
            m = defs[extra_key]
            rows.append(
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"⚪ {m.name} ({m.code})",
                            "size": "sm",
                            "color": "#4B5563",
                            "flex": 4,
                        },
                        {
                            "type": "text",
                            "text": f"{m.fmt(float(report[extra_key]))} {m.unit}".strip(),
                            "size": "sm",
                            "color": "#4B5563",
                            "align": "end",
                            "flex": 3,
                        },
                    ],
                    "margin": "xs",
                }
            )

    body_contents: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": "📋 檢驗單辨識確認",
            "weight": "bold",
            "size": "xl",
            "color": "#111827",
        },
        {
            "type": "text",
            "text": f"採檢日期：{test_date}",
            "size": "sm",
            "color": "#6B7280",
            "margin": "xs",
        },
        {"type": "separator", "margin": "md", "color": "#E5E7EB"},
        {
            "type": "box",
            "layout": "vertical",
            "contents": rows if rows else [{"type": "text", "text": "未擷取到主要數值", "color": "#9CA3AF"}],
            "margin": "md",
        },
    ]

    if uncertain:
        body_contents.append(
            {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": "⚠️ 標註項目可能因字跡折痕不確定，請特別核對",
                        "size": "xs",
                        "color": "#D97706",
                        "wrap": True,
                    }
                ],
                "backgroundColor": "#FEF3C7",
                "cornerRadius": "md",
                "paddingAll": "sm",
                "margin": "md",
            }
        )

    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "paddingAll": "lg",
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#10B981",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "✅ 數字正確，儲存",
                        "data": f"action=confirm_report&id={report_id}",
                        "displayText": "確認此份檢驗報告數值無誤",
                    },
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "✏️ 手動修改數值",
                        "data": f"action=edit_report_prompt&id={report_id}",
                        "displayText": "我要修改這份報告的數值",
                    },
                },
                {
                    "type": "button",
                    "style": "link",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "捨棄這張",
                        "data": f"action=discard_report&id={report_id}",
                        "displayText": "捨棄此報告",
                    },
                },
            ],
            "paddingAll": "md",
        },
    }


def build_ocr_carousel(reports: list[dict[str, Any]], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """多期辨識結果 Carousel。"""
    bubbles = [build_ocr_confirm_bubble(r, overrides) for r in reports]
    return {
        "type": "flex",
        "altText": "檢驗單辨識結果確認",
        "contents": {
            "type": "carousel",
            "contents": bubbles,
        },
    }


def build_report_overview_flex(
    report: dict[str, Any],
    results: list[MetricResult],
    patient_nickname: str = "長輩",
    advice_id: str | None = None,
) -> dict[str, Any]:
    """報告確認後的高齡友善總覽卡片。"""
    test_date = str(report.get("test_date") or "")
    overall = worst_level([r.level for r in results])

    badge_bg = LEVEL_COLOR[overall]
    badge_label = LEVEL_LABEL[overall]

    metric_rows: list[dict[str, Any]] = []
    for r in results:
        if r.value is None:
            continue
        trend_symbol = r.trend if r.trend else "-"
        trend_color = "#10B981" if trend_symbol == "↓" and r.direction == "high" else "#6B7280"

        metric_rows.append(
            {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{LEVEL_EMOJI[r.level]} {r.metric.name}",
                        "size": "lg",
                        "weight": "bold",
                        "color": "#111827",
                        "flex": 4,
                    },
                    {
                        "type": "text",
                        "text": f"{r.metric.fmt(r.value)} {r.metric.unit}".strip(),
                        "size": "lg",
                        "weight": "bold",
                        "color": LEVEL_COLOR[r.level],
                        "align": "end",
                        "flex": 4,
                    },
                    {
                        "type": "text",
                        "text": f"{trend_symbol}",
                        "size": "lg",
                        "weight": "bold",
                        "color": trend_color,
                        "align": "end",
                        "flex": 1,
                    },
                ],
                "margin": "md",
            }
        )

    body_contents: list[dict[str, Any]] = [
        {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": f"📊 {patient_nickname} 的檢驗成績單",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#111827",
                    "flex": 6,
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": badge_label,
                            "size": "xs",
                            "color": "#FFFFFF",
                            "weight": "bold",
                            "align": "center",
                        }
                    ],
                    "backgroundColor": badge_bg,
                    "cornerRadius": "sm",
                    "paddingAll": "xs",
                    "flex": 2,
                    "justifyContent": "center",
                },
            ],
        },
        {
            "type": "text",
            "text": f"採檢日期：{test_date}｜綠燈表示落在安全目標",
            "size": "xs",
            "color": "#6B7280",
            "margin": "xs",
        },
        {"type": "separator", "margin": "md", "color": "#E5E7EB"},
        {
            "type": "box",
            "layout": "vertical",
            "contents": metric_rows,
            "margin": "sm",
        },
    ]

    footer_buttons: list[dict[str, Any]] = [
        {
            "type": "button",
            "style": "primary",
            "color": "#3B82F6",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": "📈 查看趨勢折線圖",
                "data": "action=view_charts_menu",
                "displayText": "我想看數據趨勢圖",
            },
        }
    ]


    return {
        "type": "flex",
        "altText": f"{patient_nickname} 的檢驗成績單已更新",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": body_contents,
                "paddingAll": "lg",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": footer_buttons,
                "paddingAll": "md",
            },
        },
    }


def build_charts_menu_flex(patient_nickname: str = "長輩", family_id: str | None = None) -> dict[str, Any]:
    """圖表選單卡片。"""
    dash_url = get_settings().get_dashboard_url(family_id)

    buttons = [
        ("綜合儀表板", "summary", "#4F46E5"),
        ("鉀離子 (K)", "potassium", "#059669"),
        ("磷 (P)", "phosphorus", "#D97706"),
        ("血紅素 (Hb)", "hemoglobin", "#DC2626"),
        ("白蛋白 (Alb)", "albumin", "#2563EB"),
        ("透析效率 (Kt/V)", "kt_v", "#7C3AED"),
    ]

    btn_rows: list[dict[str, Any]] = [
        # 推薦：直接開啟網頁版數據中心
        {
            "type": "button",
            "style": "primary",
            "height": "sm",
            "color": "#245A44",
            "action": {
                "type": "uri",
                "label": "🌿 開啟線上照護手札 (推薦)",
                "uri": dash_url,
            },
            "margin": "xs",
        },
        {"type": "separator", "margin": "sm"},
    ]
    for label, metric_key, color in buttons:
        btn_rows.append(
            {
                "type": "button",
                "style": "secondary",
                "height": "sm",
                "action": {
                    "type": "postback",
                    "label": f"📊 在 LINE 看 {label}",
                    "data": f"action=render_chart&metric={metric_key}",
                    "displayText": f"查看 {label} 趨勢圖",
                },
                "margin": "xs",
            }
        )

    return {
        "type": "flex",
        "altText": "請選擇要查看的趨勢圖表",
        "contents": {
            "type": "bubble",
            "size": "kilo",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"📈 {patient_nickname} 的趨勢圖表",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#111827",
                    },
                    {
                        "type": "text",
                        "text": "支援網頁全螢幕互動縮放或 LINE 圖卡檢視：",
                        "size": "sm",
                        "color": "#6B7280",
                        "margin": "xs",
                    },
                    {"type": "separator", "margin": "sm"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": btn_rows,
                        "margin": "md",
                    },
                ],
                "paddingAll": "lg",
            },
        },
    }


def build_main_quick_reply(family_id: str | None = None) -> dict[str, Any]:
    """主快捷鍵 Quick Reply 清單（浮動在對話視窗下方的實體按鈕）。"""
    dash_url = get_settings().get_dashboard_url(family_id)
    return {
        "items": [
            {
                "type": "action",
                "action": {
                    "type": "uri",
                    "label": "🌿 照護手札中心",
                    "uri": dash_url,
                },
            },
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "📸 上傳報告",
                    "text": "上傳報告",
                },
            },
            {
                "type": "action",
                "action": {
                    "type": "postback",
                    "label": "📝 門診小抄",
                    "data": "action=clinic_memo",
                    "displayText": "我想看門診就醫小抄",
                },
            },
            {
                "type": "action",
                "action": {
                    "type": "postback",
                    "label": "📈 趨勢折線圖",
                    "data": "action=view_charts_menu",
                    "displayText": "我想看數據趨勢圖",
                },
            },
            {
                "type": "action",
                "action": {
                    "type": "postback",
                    "label": "⚖️ 記體重",
                    "data": "action=prompt_weight",
                    "displayText": "我要記錄體重",
                },
            },
            {
                "type": "action",
                "action": {
                    "type": "postback",
                    "label": "❤️ 記血壓",
                    "data": "action=prompt_bp",
                    "displayText": "我要記錄血壓",
                },
            },
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "💧 喝水 100cc",
                    "text": "喝水 100",
                },
            },
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "💧 喝水 200cc",
                    "text": "喝水 200",
                },
            },
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": "📋 今日總覽",
                    "text": "今日狀況",
                },
            },
        ]
    }


def build_daily_quick_reply() -> dict[str, Any]:
    """日常紀錄 Quick Reply 項目清單。"""
    return build_main_quick_reply()


def build_disclaimer_flex() -> dict[str, Any]:
    """免責聲明與隱私授權卡片。"""
    return {
        "type": "flex",
        "altText": "服務使用條款與免責聲明",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "🛡️ 醫療隱私與服務免責說明",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#111827",
                    },
                    {
                        "type": "text",
                        "text": "1. 本系統為「輔助照護與數據視覺化」工具，所有 AI 建議均非醫療診斷，無法取代主治醫師、透析室護理師與營養師的專業指導。\n2. 檢驗單影像辨識僅擷取數值，不儲存姓名與病歷號。\n3. 若長輩出現任何身體急性不適（如胸悶、氣喘、手腳發麻），請立即就醫！",
                        "size": "sm",
                        "color": "#4B5563",
                        "wrap": True,
                        "margin": "md",
                    },
                ],
                "paddingAll": "lg",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#10B981",
                        "action": {
                            "type": "postback",
                            "label": "我已了解並同意",
                            "data": "action=accept_disclaimer",
                            "displayText": "我同意服務條款",
                        },
                    }
                ],
            },
        },
    }


def build_changelog_flex() -> dict[str, Any]:
    """版本更新紀錄 Flex 互動卡片。"""
    return {
        "type": "flex",
        "altText": "雲端小乖孫 最新版本更新紀錄",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "🚀 系統版本歷程",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#10B981",
                    },
                    {
                        "type": "text",
                        "text": "最新版本：v1.2.0 (2026-10-13)",
                        "size": "xs",
                        "color": "#6B7280",
                        "margin": "xs",
                    },
                ],
                "paddingBottom": "none",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "【v1.2.0】最新更新亮點 ✨",
                                "weight": "bold",
                                "size": "md",
                                "color": "#111827",
                            },
                            {
                                "type": "text",
                                "text": "• 浮動實體快捷鍵：對話自帶 7 大圓角按鈕\n• 辨識進度預估：分析即時提示預估時間\n• 雲端熱修復：解決趨勢退件問題",
                                "size": "sm",
                                "color": "#4B5563",
                                "wrap": True,
                                "margin": "sm",
                            },
                        ],
                        "backgroundColor": "#F0FDF4",
                        "cornerRadius": "md",
                        "paddingAll": "md",
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "【v1.1.0】雲端正式託管 ☁️ (2026-10-13)",
                                "weight": "bold",
                                "size": "sm",
                                "color": "#1F2937",
                            },
                            {
                                "type": "text",
                                "text": "• 遷移 Render.com 雲端常駐容器\n• UptimeRobot 24/7 永不休眠雙保險\n• 家庭群組協同模式全開",
                                "size": "xs",
                                "color": "#6B7280",
                                "wrap": True,
                                "margin": "xs",
                            },
                        ],
                        "margin": "md",
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "【v1.0.0】核心發布 🎉 (2026-10-12)",
                                "weight": "bold",
                                "size": "sm",
                                "color": "#1F2937",
                            },
                            {
                                "type": "text",
                                "text": "• Gemini 視覺 OCR、紅綠燈成績單\n• 大字體趨勢圖、AI 白話照護建議",
                                "size": "xs",
                                "color": "#6B7280",
                                "wrap": True,
                                "margin": "xs",
                            },
                        ],
                        "margin": "md",
                    },
                ],
                "paddingAll": "lg",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#10B981",
                        "action": {
                            "type": "uri",
                            "label": "🌐 查看完整網頁版歷程",
                            "uri": "https://dialysis-care-bot.onrender.com/changelog",
                        },
                    }
                ],
                "paddingAll": "md",
            },
        },
    }


# ---------------------------------------------------------------------
# 1. 門診專用「30 秒就醫小抄 / 醫師問診備忘錄」Flex 卡片
# ---------------------------------------------------------------------


def build_clinic_memo_flex(memo: Any, patient_nickname: str, family_id: str | None = None) -> dict[str, Any]:
    """生成門診 30 秒就醫小抄 Flex 卡片。"""
    headline = getattr(memo, "summary_headline", "") or memo.get("summary_headline", "門診 30 秒問診備忘小抄")
    overview = getattr(memo, "overview_text", "") or memo.get("overview_text", "")
    highlights = getattr(memo, "key_highlights", []) or memo.get("key_highlights", [])
    questions = getattr(memo, "doctor_questions", []) or memo.get("doctor_questions", [])
    reminders = getattr(memo, "daily_reminders", []) or memo.get("daily_reminders", [])

    dash_url = get_settings().get_dashboard_url(family_id)

    # 亮點清單
    highlight_boxes = []
    for h in highlights[:4]:
        highlight_boxes.append(
            {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {"type": "text", "text": "✦", "size": "sm", "color": "#245A44", "flex": 1},
                    {"type": "text", "text": str(h), "size": "sm", "color": "#2C302E", "wrap": True, "flex": 12},
                ],
                "margin": "sm",
            }
        )

    # 提問清單
    question_boxes = []
    for q in questions[:3]:
        question_boxes.append(
            {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {"type": "text", "text": "💬", "size": "sm", "flex": 1},
                    {"type": "text", "text": str(q), "size": "sm", "color": "#1F2937", "wrap": True, "weight": "bold", "flex": 12},
                ],
                "margin": "sm",
            }
        )

    # 備忘叮嚀
    reminder_boxes = []
    for r in reminders[:2]:
        reminder_boxes.append(
            {
                "type": "text",
                "text": f"• {r}",
                "size": "xs",
                "color": "#5F6A64",
                "wrap": True,
                "margin": "xs",
            }
        )

    return {
        "type": "flex",
        "altText": f"📝 {patient_nickname} 的門診 30 秒就醫小抄",
        "contents": {
            "type": "bubble",
            "size": "giga",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#FBF9F5",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": "📝 門診 30 秒就醫備忘小抄",
                                "weight": "bold",
                                "size": "lg",
                                "color": "#245A44",
                                "flex": 8,
                            },
                            {
                                "type": "text",
                                "text": "醫師快速瀏覽",
                                "size": "xs",
                                "color": "#B85D19",
                                "align": "end",
                                "flex": 4,
                                "weight": "bold",
                            },
                        ],
                    },
                    {
                        "type": "text",
                        "text": f"{patient_nickname} · 跨期檢驗走勢與診間提問",
                        "size": "xs",
                        "color": "#5F6A64",
                        "margin": "xs",
                    },
                ],
                "paddingAll": "lg",
                "paddingBottom": "sm",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#FFFFFF",
                "contents": [
                    # 概述框
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#EDF5F0",
                        "cornerRadius": "md",
                        "paddingAll": "md",
                        "contents": [
                            {
                                "type": "text",
                                "text": "【30 秒狀態簡報】",
                                "weight": "bold",
                                "size": "xs",
                                "color": "#245A44",
                            },
                            {
                                "type": "text",
                                "text": overview,
                                "size": "sm",
                                "color": "#2C302E",
                                "wrap": True,
                                "margin": "xs",
                            },
                        ],
                    },
                    # 亮點區
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "lg",
                        "contents": [
                            {
                                "type": "text",
                                "text": "📈 近期關鍵數據走勢",
                                "weight": "bold",
                                "size": "sm",
                                "color": "#2C302E",
                            },
                            {"type": "separator", "margin": "xs", "color": "#E6DFD3"},
                            {"type": "box", "layout": "vertical", "contents": highlight_boxes, "margin": "sm"},
                        ],
                    },
                    # 問診問題區
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#FDF5ED",
                        "cornerRadius": "md",
                        "paddingAll": "md",
                        "margin": "lg",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🩺 建議請教醫師的關鍵問診",
                                "weight": "bold",
                                "size": "sm",
                                "color": "#B85D19",
                            },
                            {"type": "box", "layout": "vertical", "contents": question_boxes, "margin": "sm"},
                        ],
                    },
                    # 隨身備忘
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "text",
                                "text": "💡 陪診日常叮嚀：",
                                "size": "xs",
                                "weight": "bold",
                                "color": "#5F6A64",
                            },
                            {"type": "box", "layout": "vertical", "contents": reminder_boxes, "margin": "xs"},
                        ],
                    },
                ],
                "paddingAll": "lg",
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "spacing": "md",
                "backgroundColor": "#FBF9F5",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#245A44",
                        "height": "sm",
                        "action": {
                            "type": "uri",
                            "label": "🌐 線上完整好日札",
                            "uri": dash_url,
                        },
                        "flex": 1,
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {
                            "type": "postback",
                            "label": "🔄 重整小抄",
                            "data": "action=clinic_memo",
                            "displayText": "我想重新整理門診小抄",
                        },
                        "flex": 1,
                    },
                ],
                "paddingAll": "md",
            },
        },
    }


# ---------------------------------------------------------------------
# 2. 外食與飲食「拍照 AI 瞬間快篩」Flex 卡片
# ---------------------------------------------------------------------


def build_food_screening_flex(food: Any, patient_nickname: str) -> dict[str, Any]:
    """生成外食與料理拍照 AI 避雷快篩 Flex 卡片。"""
    dish_name = getattr(food, "dish_name", "") or food.get("dish_name", "今日餐點料理")
    ingredients = getattr(food, "main_ingredients", []) or food.get("main_ingredients", [])
    level = getattr(food, "overall_level", "yellow") or food.get("overall_level", "yellow")
    k_risk = getattr(food, "potassium_risk", "medium") or food.get("potassium_risk", "medium")
    k_note = getattr(food, "potassium_note", "") or food.get("potassium_note", "")
    p_risk = getattr(food, "phosphorus_risk", "medium") or food.get("phosphorus_risk", "medium")
    p_note = getattr(food, "phosphorus_note", "") or food.get("phosphorus_note", "")
    na_note = getattr(food, "sodium_water_note", "") or food.get("sodium_water_note", "")
    hacks = getattr(food, "eating_hacks", []) or food.get("eating_hacks", [])
    summary = getattr(food, "friendly_summary", "") or food.get("friendly_summary", "")

    # 等級樣式
    level_color_map = {
        "green": ("#245A44", "#EDF5F0", "🟢 放心享用 · 掌握基本原則"),
        "yellow": ("#B85D19", "#FDF5ED", "🟡 留心份量 · 避開濃湯菜湯"),
        "red": ("#A32A2A", "#FDF0F0", "🔴 高雷警戒 · 請照降雷法吃"),
    }
    header_color, box_bg, level_text = level_color_map.get(level, level_color_map["yellow"])

    # 食材標籤
    ing_text = "、".join(ingredients[:5]) if ingredients else "一般家庭常備食材"

    # 降雷吃法
    hack_boxes = []
    for i, h in enumerate(hacks[:3], 1):
        hack_boxes.append(
            {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": f"第{i}招",
                        "size": "xs",
                        "color": "#245A44",
                        "weight": "bold",
                        "flex": 2,
                    },
                    {
                        "type": "text",
                        "text": str(h),
                        "size": "sm",
                        "color": "#2C302E",
                        "wrap": True,
                        "flex": 8,
                    },
                ],
                "margin": "sm",
            }
        )

    return {
        "type": "flex",
        "altText": f"🍽️ {dish_name} 透析飲食快篩結果",
        "contents": {
            "type": "bubble",
            "size": "giga",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": header_color,
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🍽️ 外食 AI 瞬間快篩",
                                "weight": "bold",
                                "size": "md",
                                "color": "#FFFFFF",
                                "flex": 8,
                            },
                            {
                                "type": "text",
                                "text": "透析飲食指引",
                                "size": "xs",
                                "color": "#F3ECE4",
                                "align": "end",
                                "flex": 4,
                            },
                        ],
                    },
                    {
                        "type": "text",
                        "text": dish_name,
                        "weight": "bold",
                        "size": "xl",
                        "color": "#FFFFFF",
                        "margin": "sm",
                    },
                    {
                        "type": "text",
                        "text": level_text,
                        "size": "xs",
                        "color": "#FFFFFF",
                        "margin": "xs",
                    },
                ],
                "paddingAll": "lg",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#FFFFFF",
                "contents": [
                    # 食材辨識
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "辨識主要食材：", "size": "xs", "color": "#5F6A64", "flex": 3},
                            {"type": "text", "text": ing_text, "size": "xs", "color": "#2C302E", "weight": "bold", "wrap": True, "flex": 7},
                        ],
                    },
                    {"type": "separator", "margin": "md", "color": "#E6DFD3"},
                    # 鉀、磷、鈉水分評估區
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🥬 鉀離子：", "size": "sm", "weight": "bold", "color": "#2C302E", "flex": 3},
                                    {"type": "text", "text": f"[{k_risk.upper()}] {k_note}", "size": "xs", "color": "#5F6A64", "wrap": True, "flex": 7},
                                ],
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "margin": "sm",
                                "contents": [
                                    {"type": "text", "text": "🥩 磷離子：", "size": "sm", "weight": "bold", "color": "#2C302E", "flex": 3},
                                    {"type": "text", "text": f"[{p_risk.upper()}] {p_note}", "size": "xs", "color": "#5F6A64", "wrap": True, "flex": 7},
                                ],
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "margin": "sm",
                                "contents": [
                                    {"type": "text", "text": "💧 水分鹽鈉：", "size": "sm", "weight": "bold", "color": "#2C302E", "flex": 3},
                                    {"type": "text", "text": na_note, "size": "xs", "color": "#5F6A64", "wrap": True, "flex": 7},
                                ],
                            },
                        ],
                    },
                    # 降雷救援吃法指南
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#EDF5F0",
                        "cornerRadius": "md",
                        "paddingAll": "md",
                        "margin": "lg",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🌿 洗腎長輩「降雷救援吃法」",
                                "weight": "bold",
                                "size": "sm",
                                "color": "#245A44",
                            },
                            {"type": "box", "layout": "vertical", "contents": hack_boxes, "margin": "sm"},
                        ],
                    },
                    # 溫暖總結
                    {
                        "type": "text",
                        "text": f"💬 {summary}",
                        "size": "xs",
                        "color": "#8E9892",
                        "wrap": True,
                        "margin": "md",
                    },
                ],
                "paddingAll": "lg",
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "spacing": "md",
                "backgroundColor": "#FBF9F5",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#245A44",
                        "height": "sm",
                        "action": {
                            "type": "message",
                            "label": "💧 記喝水 100cc",
                            "text": "喝水 100",
                        },
                        "flex": 1,
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {
                            "type": "message",
                            "label": "📸 再拍一道",
                            "text": "外食快篩",
                        },
                        "flex": 1,
                    },
                ],
                "paddingAll": "md",
            },
        },
    }


# ---------------------------------------------------------------------
# 3. 危急值主動預警推播 (Proactive Critical Alert) Flex 卡片
# ---------------------------------------------------------------------


def build_critical_alert_flex(alerts: list[Any], patient_nickname: str, family_id: str | None = None) -> dict[str, Any]:
    """生成重大危急值專屬緊急警戒 Flex 卡片。"""
    alert_rows = []
    for a in alerts:
        name = getattr(a, "name", "") or a.get("name", "")
        code = getattr(a, "code", "") or a.get("code", "")
        val = getattr(a, "value", "") or a.get("value", "")
        unit = getattr(a, "unit", "") or a.get("unit", "")
        reason = getattr(a, "reason", "") or a.get("reason", "")
        action = getattr(a, "action", "") or a.get("action", "")

        alert_rows.append(
            {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#FFF5F5",
                "cornerRadius": "md",
                "paddingAll": "md",
                "margin": "md",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"🚨 {name} ({code})",
                                "weight": "bold",
                                "size": "md",
                                "color": "#A32A2A",
                                "flex": 6,
                            },
                            {
                                "type": "text",
                                "text": f"{val} {unit}".strip(),
                                "weight": "bold",
                                "size": "md",
                                "color": "#A32A2A",
                                "align": "end",
                                "flex": 4,
                            },
                        ],
                    },
                    {
                        "type": "text",
                        "text": f"危急原因：{reason}",
                        "size": "xs",
                        "color": "#7F1D1D",
                        "wrap": True,
                        "margin": "xs",
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#FEE2E2",
                        "cornerRadius": "sm",
                        "paddingAll": "sm",
                        "margin": "sm",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"👉 即時處置：{action}",
                                "size": "xs",
                                "color": "#991B1B",
                                "wrap": True,
                                "weight": "bold",
                            }
                        ],
                    },
                ],
            }
        )

    dash_url = get_settings().get_dashboard_url(family_id)

    return {
        "type": "flex",
        "altText": f"🚨 【危急警戒】{patient_nickname} 的檢驗數值觸發緊急安全紅線！",
        "contents": {
            "type": "bubble",
            "size": "giga",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#A32A2A",
                "contents": [
                    {
                        "type": "text",
                        "text": "🚨 臨床重大危急值主動警報",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#FFFFFF",
                    },
                    {
                        "type": "text",
                        "text": f"受檢對象：{patient_nickname} · 需立即留心與處置",
                        "size": "xs",
                        "color": "#FEE2E2",
                        "margin": "xs",
                    },
                ],
                "paddingAll": "lg",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#FFFFFF",
                "contents": [
                    {
                        "type": "text",
                        "text": "⚠️ 系統依據國際透析標準 (KDOQI/KDIGO) 偵測到以下數值偏離安全帶，存在急性健康風險：",
                        "size": "sm",
                        "color": "#2C302E",
                        "wrap": True,
                    },
                    {"type": "box", "layout": "vertical", "contents": alert_rows},
                    {
                        "type": "text",
                        "text": "安全守則：請保持鎮定，如長輩出現胸悶、心悸、全身癱軟無力、頭暈或呼吸喘，請立即撥打 119 或至急診就醫！",
                        "size": "xs",
                        "color": "#A32A2A",
                        "wrap": True,
                        "margin": "lg",
                        "weight": "bold",
                    },
                ],
                "paddingAll": "lg",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#FBF9F5",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#A32A2A",
                        "action": {
                            "type": "uri",
                            "label": "📊 查看線上完整存摺數據",
                            "uri": dash_url,
                        },
                    }
                ],
                "paddingAll": "md",
            },
        },
    }

