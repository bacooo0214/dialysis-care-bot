"""檢驗數據高質感可視化圖表渲染模組。

全面同步網頁版文青宣紙手札美學 (Literary & Warm Paper Aesthetic)：
- 暖宣紙底色 (#FBF9F5)、純白手札卡片 (#FFFFFF)、淺焙茶色邊框 (#E6DFD3)。
- 松煙墨黑字體 (#2C302E)、青苔灰輔助字 (#5F6A64)、竹青綠舒適圈底色帶 (#EDF5F0 / #245A44)。
- 內建思源黑體 (Noto Sans CJK TC Bold) 繁體中文字型，100% 杜絕雲端 Linux 豆腐塊。
- 去除疾病與冰冷感，轉化為生活元氣生活記帳本風格。
- 支援「未檢驗生活指南」、「首期基準趨勢圖」、「多期跨月歷史走勢折線圖」、「四大關鍵指標綜合走勢看板」與「單期活力總覽儀表板」。
"""

from __future__ import annotations

import io
import logging
import os
from datetime import date, timedelta
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.patches as patches
import matplotlib.pyplot as plt

from app.metrics import LEVEL_COLOR, METRICS, Level, MetricDef, get_metrics

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# 文青紙本書札配色體系 (Warm Paper & Literary Palette)
# ---------------------------------------------------------------------
COLOR_BG_PAPER = "#FBF9F5"     # 暖宣紙米白底色
COLOR_CARD_BG = "#FFFFFF"      # 純淨暖白卡片底
COLOR_BORDER = "#E6DFD3"       # 淺焙茶色細邊框
COLOR_GRID = "#EBE5DB"         # 淺焙茶色微網格線
COLOR_TEXT_INK = "#2C302E"     # 松煙墨黑
COLOR_TEXT_MUTED = "#5F6A64"   # 青苔灰
COLOR_TEXT_DIM = "#8E9892"     # 輕墨灰

COLOR_BAMBOO = "#245A44"       # 竹青綠（正常舒適）
COLOR_BAMBOO_BG = "#EDF5F0"    # 淺竹青舒適圈底色
COLOR_AMBER = "#B85D19"        # 沉著琥珀（稍加注意）
COLOR_AMBER_BG = "#FDF5ED"     # 淺琥珀底色
COLOR_CINNABAR = "#A32A2A"     # 赭石朱砂（偏高警戒）
COLOR_CINNABAR_BG = "#FDF0F0"  # 淺赭底色
COLOR_INDIGO = "#2D5873"       # 霽藍（主要走勢線）
COLOR_INDIGO_BG = "#EEF4F8"

# ---------------------------------------------------------------------
# 字型載入機制（優先使用專案內建 NotoSansTC-Bold.otf，保證繁中完美渲染）
# ---------------------------------------------------------------------

FONT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts", "NotoSansTC-Bold.otf")
)

FONT_PROP: fm.FontProperties

if os.path.exists(FONT_PATH):
    fm.fontManager.addfont(FONT_PATH)
    FONT_PROP = fm.FontProperties(fname=FONT_PATH)
    CHOSEN_FONT = FONT_PROP.get_name()
    plt.rcParams["font.family"] = CHOSEN_FONT
    plt.rcParams["font.sans-serif"] = [CHOSEN_FONT, "Noto Sans CJK TC", "Microsoft JhengHei", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
else:
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK TC", "Microsoft JhengHei", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    FONT_PROP = fm.FontProperties(family="sans-serif")
    CHOSEN_FONT = "sans-serif"


def _get_level_info(m: MetricDef, val: float | None) -> tuple[str, str, str]:
    """取得指標等級標籤與配色（文青雅致版）。"""
    if val is None:
        return "未檢驗", COLOR_TEXT_DIM, COLOR_CARD_BG
    level = m.classify(val)
    if level == Level.GREEN:
        return "安好舒適", COLOR_BAMBOO, COLOR_BAMBOO_BG
    elif level == Level.YELLOW:
        d = m.direction(val)
        lbl = "多關心(高)" if d == "high" else ("多關心(低)" if d == "low" else "多關心")
        return lbl, COLOR_AMBER, COLOR_AMBER_BG
    elif level == Level.RED:
        d = m.direction(val)
        lbl = "需留心(高)" if d == "high" else ("需留心(低)" if d == "low" else "需留心")
        return lbl, COLOR_CINNABAR, COLOR_CINNABAR_BG
    return "未檢驗", COLOR_TEXT_DIM, COLOR_CARD_BG


# ---------------------------------------------------------------------
# 1. 單一指標趨勢折線圖 / 基準圖 / 指南卡 (文青手札風格)
# ---------------------------------------------------------------------


def render_metric_trend(
    metric_key: str,
    reports: list[dict[str, Any]],
    patient_nickname: str = "長輩",
    overrides: dict[str, Any] | None = None,
) -> bytes:
    """繪製單一檢驗項目的趨勢折線圖（文青暖宣紙手札調性）。"""
    defs = get_metrics(overrides)
    m = defs.get(metric_key, METRICS.get(metric_key))
    if not m:
        raise ValueError(f"未知的檢驗項目: {metric_key}")

    dates_list: list[date] = []
    values_list: list[float] = []
    for r in reports:
        raw_val = r.get(metric_key)
        raw_d = r.get("test_date")
        if raw_val is not None and raw_d:
            try:
                d = date.fromisoformat(str(raw_d)[:10])
                v = float(raw_val)
                dates_list.append(d)
                values_list.append(v)
            except (ValueError, TypeError):
                continue

    # 情境 A：完全無數據 → 指標指南圖卡
    if not dates_list:
        return _render_empty_guide(m, patient_nickname)

    # 情境 B & C：有 1 筆或多筆數據 → 折線趨勢圖
    fig, ax = plt.subplots(figsize=(9.2, 5.4), dpi=160)
    fig.patch.set_facecolor(COLOR_BG_PAPER)
    ax.set_facecolor(COLOR_CARD_BG)

    y_min_data = min(values_list)
    y_max_data = max(values_list)
    span = max(y_max_data - y_min_data, 1.0)
    y_bottom = min(y_min_data - span * 0.35, (m.green_low or y_min_data) - 0.5)
    y_top = max(y_max_data + span * 0.45, (m.green_high or y_max_data) + 0.5)

    g_low = m.green_low if m.green_low is not None else y_bottom
    g_high = m.green_high if m.green_high is not None else y_top

    # 活力舒適圈底色帶 (柔和淺竹青半透明)
    ax.axhspan(
        g_low,
        g_high,
        color=COLOR_BAMBOO_BG,
        alpha=0.85,
        zorder=1,
        label=f"活力舒適圈 ({m.range_text()} {m.unit})",
    )
    if m.green_low is not None:
        ax.axhline(g_low, color=COLOR_BAMBOO, linestyle="--", linewidth=1.2, alpha=0.55, zorder=2)
    if m.green_high is not None:
        ax.axhline(g_high, color=COLOR_BAMBOO, linestyle="--", linewidth=1.2, alpha=0.55, zorder=2)

    # 折線（霽藍墨色折線）
    line_color = COLOR_INDIGO
    if len(dates_list) >= 2:
        ax.plot(dates_list, values_list, color=line_color, linestyle="-", linewidth=3.2, zorder=3, alpha=0.95)
        ax.fill_between(dates_list, values_list, y_bottom, color=line_color, alpha=0.08, zorder=2)

    # 數據點與立體標籤
    for d, v in zip(dates_list, values_list):
        status_lbl, c, bg_c = _get_level_info(m, v)
        ax.plot(d, v, marker="o", markersize=13, markerfacecolor=c, markeredgecolor="#FFFFFF", markeredgewidth=2.4, zorder=4)

        fmt_v = m.fmt(v)
        unit_str = f" {m.unit}" if m.unit else ""
        label_text = f"{fmt_v}{unit_str}\n[{status_lbl}]"
        ax.annotate(
            label_text,
            xy=(d, v),
            xytext=(0, 14),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=11.5,
            fontweight="bold",
            color=COLOR_TEXT_INK,
            bbox=dict(boxstyle="round,pad=0.35", facecolor=COLOR_CARD_BG, edgecolor=c, alpha=0.98, linewidth=1.4),
            zorder=5,
            fontproperties=FONT_PROP,
        )

    # 單筆數據時擴展時間軸
    if len(dates_list) == 1:
        d0 = dates_list[0]
        ax.set_xlim(d0 - timedelta(days=25), d0 + timedelta(days=25))
        ax.text(
            0.5, 0.08,
            "★ 首期元氣紀錄已入冊！隨後上傳新報告，將自動為您繪製平滑走勢圖",
            transform=ax.transAxes,
            ha="center", va="center",
            color=COLOR_TEXT_MUTED, fontsize=11,
            bbox=dict(boxstyle="round,pad=0.3", facecolor=COLOR_CARD_BG, edgecolor=COLOR_BORDER, alpha=0.9),
            fontproperties=FONT_PROP,
        )

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y/%m/%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(fontsize=11, fontweight="bold", color=COLOR_TEXT_MUTED)
    plt.yticks(fontsize=11, color=COLOR_TEXT_MUTED)

    unit_str = f" ({m.unit})" if m.unit else ""
    title_suffix = "跨月走勢折線圖" if len(dates_list) >= 2 else "首期活力基準圖"
    ax.set_title(
        f"生活元氣記帳本 ｜ 【{m.name} {m.code}】{title_suffix}",
        fontsize=17,
        fontweight="bold",
        pad=16,
        color=COLOR_TEXT_INK,
        fontproperties=FONT_PROP,
    )
    ax.set_ylabel(f"{m.name}{unit_str}", fontsize=12.5, fontweight="bold", color=COLOR_TEXT_MUTED, labelpad=8, fontproperties=FONT_PROP)

    ax.set_ylim(y_bottom, y_top)
    ax.grid(axis="y", linestyle=":", alpha=0.6, color=COLOR_GRID)
    ax.set_axisbelow(True)

    ax.legend(
        loc="upper right",
        frameon=True,
        facecolor=COLOR_CARD_BG,
        edgecolor=COLOR_BORDER,
        fontsize=11,
        prop=FONT_PROP,
        labelcolor=COLOR_TEXT_INK,
    )

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color(COLOR_BORDER)
        ax.spines[spine].set_linewidth(1.2)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _render_empty_guide(m: MetricDef, patient_nickname: str = "長輩") -> bytes:
    """無數據時的典雅生活指南卡片。"""
    fig = plt.figure(figsize=(8.8, 4.8), dpi=160)
    fig.patch.set_facecolor(COLOR_BG_PAPER)

    ax = fig.add_axes([0.05, 0.06, 0.90, 0.88])
    ax.set_facecolor(COLOR_CARD_BG)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color(COLOR_BORDER)
        spine.set_linewidth(1.4)

    ax.text(0.5, 0.88, "★ 生活元氣記帳本 · 指標指南", ha="center", va="center",
            color=COLOR_BAMBOO, fontsize=13, fontweight="bold", fontproperties=FONT_PROP)
    ax.text(0.5, 0.74, f"【{m.name} {m.code}】", ha="center", va="center",
            color=COLOR_TEXT_INK, fontsize=22, fontweight="bold", fontproperties=FONT_PROP)

    box = patches.FancyBboxPatch((0.15, 0.45), 0.70, 0.19,
                                 boxstyle="round,pad=0.02,rounding_size=0.03",
                                 facecolor=COLOR_BAMBOO_BG, edgecolor=COLOR_BORDER, linewidth=1.2)
    ax.add_patch(box)
    ax.text(0.5, 0.56, "本期生活成績單尚未包含此項目", ha="center", va="center",
            color=COLOR_AMBER, fontsize=15, fontweight="bold", fontproperties=FONT_PROP)
    ax.text(0.5, 0.48, f"日常活力舒適圈：{m.range_text()} {m.unit}".strip(), ha="center", va="center",
            color=COLOR_BAMBOO, fontsize=13, fontweight="bold", fontproperties=FONT_PROP)

    explain_map = {
        "kt_v": "透析效率 (Kt/V) 代表體內廢物與毒素清除的乾淨程度。\n院所通常每 1~3 個月定期評估一次，目標需 ≥ 1.2。",
        "ipth": "副甲狀腺素 (iPTH) 調節體內鈣與磷的代謝平衡。\n維持在舒適圈內能保護骨骼健康與血管彈性。",
        "bun": "透析前尿素氮 (BUN) 反映體內蛋白質代謝與營養狀況。\n與飲食優質蛋白質維持相輔相成。",
        "creatinine": "肌酸酐 (Cr) 反映肌肉代謝廢物與體能狀況。",
    }
    desc = explain_map.get(m.key, f"{m.name}是日常元氣管理的重點項目，維持在目標範圍可讓身體舒暢輕鬆。")
    ax.text(0.5, 0.28, desc, ha="center", va="center",
            color=COLOR_TEXT_MUTED, fontsize=12.5, fontproperties=FONT_PROP, linespacing=1.6)

    ax.text(0.5, 0.10, "★ 隨時上傳檢驗單，確認後將自動為全家人繪製專屬活力折線圖",
            ha="center", va="center", color=COLOR_TEXT_DIM, fontsize=11, fontproperties=FONT_PROP)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------
# 2. 綜合儀表板（單期 8 格生活總覽 / 多期四大核心活力走勢看板）
# ---------------------------------------------------------------------


def render_summary_dashboard(
    report_or_history: dict[str, Any] | list[dict[str, Any]],
    patient_nickname: str = "長輩",
    overrides: dict[str, Any] | None = None,
) -> bytes:
    """繪製綜合儀表板（文青暖宣紙手札調性）。"""
    if isinstance(report_or_history, list):
        if len(report_or_history) >= 2:
            return _render_multi_metrics_dashboard(report_or_history, patient_nickname, overrides)
        elif len(report_or_history) == 1:
            latest = report_or_history[0]
        else:
            return _render_empty_guide(METRICS["potassium"], patient_nickname)
    else:
        latest = report_or_history

    return _render_single_summary_dashboard(latest, patient_nickname, overrides)


def _render_single_summary_dashboard(
    latest_report: dict[str, Any],
    patient_nickname: str = "長輩",
    overrides: dict[str, Any] | None = None,
) -> bytes:
    """單期 8 格生活活力總覽儀表板。"""
    defs = get_metrics(overrides)
    test_date = latest_report.get("test_date", "最新紀錄")
    keys = ["potassium", "phosphorus", "hemoglobin", "albumin", "sodium", "calcium", "creatinine", "ipth"]

    fig = plt.figure(figsize=(10, 6.4), dpi=160)
    fig.patch.set_facecolor(COLOR_BG_PAPER)

    ax_main = fig.add_axes([0.04, 0.04, 0.92, 0.92])
    ax_main.set_facecolor(COLOR_BG_PAPER)
    ax_main.set_xticks([])
    ax_main.set_yticks([])
    for spine in ax_main.spines.values():
        spine.set_visible(False)

    ax_main.text(0.5, 0.96, f"★ 元氣充電所 ｜ 採檢紀錄：{test_date}",
                 ha="center", va="center", color=COLOR_BAMBOO, fontsize=13, fontweight="bold", fontproperties=FONT_PROP)
    ax_main.text(0.5, 0.90, "生活元氣記帳本 ｜ 核心活力指數總覽",
                 ha="center", va="center", color=COLOR_TEXT_INK, fontsize=21, fontweight="bold", fontproperties=FONT_PROP)

    cols = 2
    card_w = 0.44
    card_h = 0.17
    gap_x = 0.04
    gap_y = 0.03
    start_x = 0.04
    start_y = 0.81 - card_h

    for idx, key in enumerate(keys):
        m = defs.get(key, METRICS[key])
        r = idx // cols
        c = idx % cols
        cx = start_x + c * (card_w + gap_x)
        cy = start_y - r * (card_h + gap_y)

        val = None
        raw_val = latest_report.get(key)
        if raw_val is not None:
            try:
                val = float(raw_val)
            except (ValueError, TypeError):
                val = None

        status_label, main_color, bg_c = _get_level_info(m, val)

        # 純白手札卡片框
        card_box = patches.FancyBboxPatch((cx, cy), card_w, card_h,
                                          boxstyle="round,pad=0.015,rounding_size=0.025",
                                          facecolor=COLOR_CARD_BG, edgecolor=COLOR_BORDER, linewidth=1.2)
        ax_main.add_patch(card_box)

        # 左側狀態細色條
        strip = patches.FancyBboxPatch((cx, cy), 0.010, card_h,
                                       boxstyle="round,pad=0.005,rounding_size=0.01",
                                       facecolor=main_color, edgecolor=main_color)
        ax_main.add_patch(strip)

        # 指標名稱
        ax_main.text(cx + 0.025, cy + card_h - 0.035, f"{m.name} ({m.code})",
                     ha="left", va="center", color=COLOR_TEXT_INK, fontsize=12.5, fontweight="bold", fontproperties=FONT_PROP)

        # 狀態印章徽章
        status_badge = patches.FancyBboxPatch((cx + card_w - 0.13, cy + card_h - 0.045), 0.11, 0.03,
                                              boxstyle="round,pad=0.005,rounding_size=0.012",
                                              facecolor=bg_c, edgecolor=main_color, linewidth=1)
        ax_main.add_patch(status_badge)
        ax_main.text(cx + card_w - 0.075, cy + card_h - 0.03, status_label,
                     ha="center", va="center", color=main_color,
                     fontsize=9.5, fontweight="bold", fontproperties=FONT_PROP)

        # 數值文字
        fmt_val = m.fmt(val) if val is not None else "--"
        unit_str = f" {m.unit}" if m.unit else ""
        ax_main.text(cx + 0.025, cy + card_h - 0.09, fmt_val,
                     ha="left", va="center", color=main_color, fontsize=20, fontweight="bold", fontproperties=FONT_PROP)
        ax_main.text(cx + 0.155, cy + card_h - 0.088, unit_str,
                     ha="left", va="baseline", color=COLOR_TEXT_DIM, fontsize=10, fontproperties=FONT_PROP)

        # 目標區間文字
        ax_main.text(cx + card_w - 0.02, cy + card_h - 0.09, f"舒適圈: {m.range_text()}",
                     ha="right", va="center", color=COLOR_TEXT_MUTED, fontsize=10.5, fontproperties=FONT_PROP)

        # 底部微型量表條
        pbar_y = cy + 0.022
        pbar_w = card_w - 0.05
        pbar_h = 0.012
        pbg = patches.Rectangle((cx + 0.025, pbar_y), pbar_w, pbar_h, facecolor=COLOR_BG_PAPER, edgecolor=COLOR_BORDER, linewidth=0.8)
        ax_main.add_patch(pbg)

        g_low = m.green_low if m.green_low is not None else 0
        g_high = m.green_high if m.green_high is not None else (g_low + 1.0)
        span = max(g_high - g_low, 0.1)
        disp_min = max(0, g_low - span * 0.7)
        disp_max = g_high + span * 0.7
        disp_range = max(disp_max - disp_min, 0.1)

        gx = cx + 0.025 + ((g_low - disp_min) / disp_range) * pbar_w
        gw = ((g_high - g_low) / disp_range) * pbar_w
        gx = max(cx + 0.025, min(cx + 0.025 + pbar_w, gx))
        gw = max(0.005, min(cx + 0.025 + pbar_w - gx, gw))
        ax_main.add_patch(patches.Rectangle((gx, pbar_y), gw, pbar_h, facecolor=COLOR_BAMBOO_BG, edgecolor=COLOR_BAMBOO, linewidth=0.8))

        if val is not None:
            vx = cx + 0.025 + ((max(disp_min, min(disp_max, val)) - disp_min) / disp_range) * pbar_w
            ax_main.plot([vx], [pbar_y + pbar_h / 2], marker="o", markersize=6.5, color=main_color, markeredgecolor="#FFFFFF", markeredgewidth=1.2)

    ax_main.text(0.5, 0.015, "— 陪伴每一天神采奕奕，願全家日子過得舒心悠哉 —",
                 ha="center", va="center", color=COLOR_TEXT_DIM, fontsize=10.5, fontproperties=FONT_PROP)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _render_multi_metrics_dashboard(
    reports: list[dict[str, Any]],
    patient_nickname: str = "長輩",
    overrides: dict[str, Any] | None = None,
) -> bytes:
    """四大核心活力指數跨期走勢看板（對齊網頁版文青風格）。"""
    defs = get_metrics(overrides)
    core_keys = [
        ("potassium", COLOR_BAMBOO),
        ("phosphorus", COLOR_AMBER),
        ("hemoglobin", COLOR_CINNABAR),
        ("calcium", COLOR_INDIGO),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(11, 7.2), dpi=160)
    fig.patch.set_facecolor(COLOR_BG_PAPER)

    fig.suptitle("生活元氣記帳本 ｜ 四大核心活力指數跨期走勢",
                 fontsize=19, fontweight="bold", color=COLOR_TEXT_INK, y=0.97, fontproperties=FONT_PROP)

    flat_axes = axes.flatten()
    for idx, (k, line_col) in enumerate(core_keys):
        ax = flat_axes[idx]
        ax.set_facecolor(COLOR_CARD_BG)
        m = defs.get(k, METRICS[k])

        dates_l = []
        vals_l = []
        for r in reports:
            raw_v = r.get(k)
            raw_d = r.get("test_date")
            if raw_v is not None and raw_d:
                try:
                    dates_l.append(date.fromisoformat(str(raw_d)[:10]))
                    vals_l.append(float(raw_v))
                except (ValueError, TypeError):
                    pass

        if not dates_l:
            ax.text(0.5, 0.5, f"{m.name} 尚無足夠數據", ha="center", va="center", color=COLOR_TEXT_MUTED, fontproperties=FONT_PROP)
            ax.set_xticks([])
            ax.set_yticks([])
            continue

        y_min = min(vals_l)
        y_max = max(vals_l)
        span = max(y_max - y_min, 1.0)
        y_bot = min(y_min - span * 0.3, (m.green_low or y_min) - 0.3)
        y_top = max(y_max + span * 0.3, (m.green_high or y_max) + 0.3)

        g_lo = m.green_low if m.green_low is not None else y_bot
        g_hi = m.green_high if m.green_high is not None else y_top

        # 柔和舒適圈底色帶
        ax.axhspan(g_lo, g_hi, color=COLOR_BAMBOO_BG, alpha=0.85, zorder=1)
        if m.green_low is not None:
            ax.axhline(g_lo, color=COLOR_BAMBOO, linestyle="--", linewidth=1.0, alpha=0.55)
        if m.green_high is not None:
            ax.axhline(g_hi, color=COLOR_BAMBOO, linestyle="--", linewidth=1.0, alpha=0.55)

        # 折線
        ax.plot(dates_l, vals_l, color=line_col, linewidth=3.0, zorder=3)
        ax.fill_between(dates_l, vals_l, y_bot, color=line_col, alpha=0.08, zorder=2)

        for d, v in zip(dates_l, vals_l):
            _, c, _ = _get_level_info(m, v)
            ax.plot(d, v, marker="o", markersize=9.5, markerfacecolor=c, markeredgecolor="#FFFFFF", markeredgewidth=2.0, zorder=4)
            ax.text(d, v, f" {m.fmt(v)}", fontsize=11, fontweight="bold", color=COLOR_TEXT_INK, va="bottom", fontproperties=FONT_PROP)

        unit_str = f" ({m.unit})" if m.unit else ""
        ax.set_title(f"{m.name} {m.code}{unit_str} [舒適圈: {m.range_text()}]",
                     fontsize=12.5, fontweight="bold", color=COLOR_TEXT_INK, pad=8, fontproperties=FONT_PROP)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.set_ylim(y_bot, y_top)
        ax.grid(axis="y", linestyle=":", alpha=0.5, color=COLOR_GRID)

        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color(COLOR_BORDER)
            ax.spines[spine].set_linewidth(1.1)

        plt.setp(ax.get_xticklabels(), color=COLOR_TEXT_MUTED, fontsize=10)
        plt.setp(ax.get_yticklabels(), color=COLOR_TEXT_MUTED, fontsize=10)

    plt.tight_layout(rect=[0, 0.02, 1, 0.94])
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
