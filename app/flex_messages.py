"""LINE Flex Message 與訊息樣板建構器。

專為高齡友善介面設計：
- 高對比、大字體、清楚色塊
- 盡量使用按鈕與快速回覆取代打字
- 清楚的紅綠燈視覺提示
"""

from __future__ import annotations

from typing import Any

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
        trend_symbol = r.trend
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


def build_charts_menu_flex(patient_nickname: str = "長輩") -> dict[str, Any]:
    """圖表選單卡片。"""
    buttons = [
        ("綜合儀表板", "summary", "#4F46E5"),
        ("鉀離子 (K)", "potassium", "#059669"),
        ("磷 (P)", "phosphorus", "#D97706"),
        ("血紅素 (Hb)", "hemoglobin", "#DC2626"),
        ("白蛋白 (Alb)", "albumin", "#2563EB"),
        ("透析效率 (Kt/V)", "kt_v", "#7C3AED"),
    ]

    btn_rows: list[dict[str, Any]] = []
    for label, metric_key, color in buttons:
        btn_rows.append(
            {
                "type": "button",
                "style": "secondary",
                "height": "sm",
                "action": {
                    "type": "postback",
                    "label": f"📊 {label}",
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
                        "text": "點選想查看的項目：",
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


def build_daily_quick_reply() -> dict[str, Any]:
    """日常紀錄 Quick Reply 項目清單。"""
    return {
        "items": [
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
                    "label": "📅 今日摘要",
                    "text": "今日狀況",
                },
            },
        ]
    }


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
