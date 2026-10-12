"""檢驗數據高質感可視化圖表渲染模組。

專為血液透析病患與家屬手機體驗精心打造：
- 內建思源黑體 (Noto Sans CJK TC Bold) 繁體中文字型，100% 杜絕 Linux / 雲端環境豆腐塊亂碼。
- 科技深藍深邃醫療質感配色 (Slate & Emerald & Sky Blue)。
- 支援「未檢驗指南卡片」、「首期檢驗基準趨勢圖」、「多期跨月歷史走勢折線圖」、「四大關鍵指標綜合走勢看板」以及「單期紅綠燈儀表板」。
- 絕無任何 Emoji 掉字風險，採用精緻幾何標籤與高對比色塊。
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
    # Fallback
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK TC", "Microsoft JhengHei", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    FONT_PROP = fm.FontProperties(family="sans-serif")
    CHOSEN_FONT = "sans-serif"


def _get_level_info(m: MetricDef, val: float | None) -> tuple[str, str, str]:
    """取得指標等級標籤與配色。"""
    if val is None:
        return "未檢驗", "#64748B", "#1E293B"
    level = m.classify(val)
    if level == Level.GREEN:
        return "正常理想", "#10B981", "#064E3B"
    elif level == Level.YELLOW:
        d = m.direction(val)
        lbl = "注意偏高" if d == "high" else ("注意偏低" if d == "low" else "注意")
        return lbl, "#F59E0B", "#78350F"
    elif level == Level.RED:
        d = m.direction(val)
        lbl = "警戒過高" if d == "high" else ("警戒過低" if d == "low" else "警戒")
        return lbl, "#EF4444", "#7F1D1D"
    return "未檢驗", "#64748B", "#1E293B"


# ---------------------------------------------------------------------
# 1. 單一指標趨勢折線圖 / 基準圖 / 指南卡
# ---------------------------------------------------------------------


def render_metric_trend(
    metric_key: str,
    reports: list[dict[str, Any]],
    patient_nickname: str = "長輩",
    overrides: dict[str, Any] | None = None,
) -> bytes:
    """繪製單一檢驗項目的趨勢折線圖。

    - 0 筆數據時：繪製指標說明與衛教指南卡片
    - 1 筆數據時：繪製首期檢驗基準趨勢圖（帶安全區間與數值標記）
    - 2 筆以上時：繪製跨月歷史走勢折線圖（帶漸層填充與節點標註）
    """
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

    # 情境 A：完全無數據 → 指標衛教指南圖卡
    if not dates_list:
        return _render_empty_guide(m, patient_nickname)

    # 情境 B & C：有 1 筆或多筆數據 → 折線趨勢圖
    fig, ax = plt.subplots(figsize=(9.2, 5.4), dpi=160)
    fig.patch.set_facecolor("#0F172A") # 深邃科技深藍
    ax.set_facecolor("#1E293B")

    y_min_data = min(values_list)
    y_max_data = max(values_list)
    span = max(y_max_data - y_min_data, 1.0)
    y_bottom = min(y_min_data - span * 0.35, (m.green_low or y_min_data) - 0.5)
    y_top = max(y_max_data + span * 0.45, (m.green_high or y_max_data) + 0.5)

    g_low = m.green_low if m.green_low is not None else y_bottom
    g_high = m.green_high if m.green_high is not None else y_top

    # 安全目標區間底色帶 (柔和綠色漸層半透明)
    ax.axhspan(
        g_low,
        g_high,
        color="#10B981",
        alpha=0.15,
        zorder=1,
        label=f"安全目標 ({m.range_text()} {m.unit})",
    )
    if m.green_low is not None:
        ax.axhline(g_low, color="#10B981", linestyle="--", linewidth=1.2, alpha=0.7, zorder=2)
    if m.green_high is not None:
        ax.axhline(g_high, color="#10B981", linestyle="--", linewidth=1.2, alpha=0.7, zorder=2)

    # 折線（多筆時連線並半透明填色）
    if len(dates_list) >= 2:
        ax.plot(dates_list, values_list, color="#38BDF8", linestyle="-", linewidth=3.5, zorder=3, alpha=0.95)
        ax.fill_between(dates_list, values_list, y_bottom, color="#38BDF8", alpha=0.08, zorder=2)

    # 數據點與標籤
    for d, v in zip(dates_list, values_list):
        status_lbl, c, _ = _get_level_info(m, v)
        ax.plot(d, v, marker="o", markersize=14, markerfacecolor=c, markeredgecolor="#FFFFFF", markeredgewidth=2.4, zorder=4)

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
            fontsize=12,
            fontweight="bold",
            color="#F8FAFC",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#0F172A", edgecolor=c, alpha=0.95, linewidth=1.5),
            zorder=5,
            fontproperties=FONT_PROP,
        )

    # 單筆數據時擴展時間軸
    if len(dates_list) == 1:
        d0 = dates_list[0]
        ax.set_xlim(d0 - timedelta(days=25), d0 + timedelta(days=25))
        ax.text(
            0.5, 0.08,
            "★ 首期檢驗紀錄已建檔！下個月上傳新報告後，將自動連線繪製跨月走勢折線圖",
            transform=ax.transAxes,
            ha="center", va="center",
            color="#94A3B8", fontsize=11,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#0F172A", edgecolor="#334155", alpha=0.8),
            fontproperties=FONT_PROP,
        )

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y/%m/%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(fontsize=11.5, fontweight="bold", color="#94A3B8")
    plt.yticks(fontsize=11.5, color="#94A3B8")

    unit_str = f" ({m.unit})" if m.unit else ""
    title_suffix = "歷史走勢折線圖" if len(dates_list) >= 2 else "檢驗趨勢基準圖"
    ax.set_title(
        f"{patient_nickname} 的【{m.name} {m.code}】{title_suffix}",
        fontsize=18,
        fontweight="bold",
        pad=16,
        color="#F8FAFC",
        fontproperties=FONT_PROP,
    )
    ax.set_ylabel(f"{m.name}{unit_str}", fontsize=13, fontweight="bold", color="#94A3B8", labelpad=8, fontproperties=FONT_PROP)

    ax.set_ylim(y_bottom, y_top)
    ax.grid(axis="y", linestyle=":", alpha=0.25, color="#64748B")
    ax.set_axisbelow(True)

    ax.legend(
        loc="upper right",
        frameon=True,
        facecolor="#0F172A",
        edgecolor="#334155",
        fontsize=11,
        prop=FONT_PROP,
        labelcolor="#E2E8F0",
    )

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#334155")
        ax.spines[spine].set_linewidth(1.2)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _render_empty_guide(m: MetricDef, patient_nickname: str = "長輩") -> bytes:
    """無數據時的精緻指標指南卡片。"""
    fig = plt.figure(figsize=(8.8, 4.8), dpi=160)
    fig.patch.set_facecolor("#0F172A")

    ax = fig.add_axes([0.05, 0.06, 0.90, 0.88])
    ax.set_facecolor("#1E293B")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#334155")
        spine.set_linewidth(1.5)

    ax.text(0.5, 0.88, f"{patient_nickname} 的檢驗項目說明", ha="center", va="center",
            color="#94A3B8", fontsize=13, fontproperties=FONT_PROP)
    ax.text(0.5, 0.74, f"【{m.name} {m.code}】", ha="center", va="center",
            color="#F8FAFC", fontsize=22, fontweight="bold", fontproperties=FONT_PROP)

    box = patches.FancyBboxPatch((0.15, 0.45), 0.70, 0.19,
                                 boxstyle="round,pad=0.02,rounding_size=0.03",
                                 facecolor="#334155", edgecolor="#475569", linewidth=1.2)
    ax.add_patch(box)
    ax.text(0.5, 0.56, "本期檢驗單尚未包含此項目", ha="center", va="center",
            color="#FBBF24", fontsize=15, fontweight="bold", fontproperties=FONT_PROP)
    ax.text(0.5, 0.48, f"標準安全目標：{m.range_text()} {m.unit}".strip(), ha="center", va="center",
            color="#38BDF8", fontsize=13, fontproperties=FONT_PROP)

    explain_map = {
        "kt_v": "透析效率 (Kt/V) 代表每次洗腎清除體內尿素毒素的充分度。\n院所通常每 1~3 個月定期抽血一次，目標需 ≥ 1.2。",
        "ipth": "副甲狀腺素 (iPTH) 調節體內鈣與磷的代謝平衡。\n過高可能導致骨骼病變與血管鈣化，需定期配合醫囑追蹤。",
        "bun": "透析前尿素氮 (BUN) 反映體內蛋白質代謝廢物的累積程度。\n需搭配每次透析充分度綜合評估。",
        "creatinine": "肌酸酐 (Cr) 反映肌肉代謝廢物與殘餘腎功能狀況。",
    }
    desc = explain_map.get(m.key, f"{m.name}是洗腎照護的重點指標，維持在目標範圍可避免嚴重併發症。")
    ax.text(0.5, 0.28, desc, ha="center", va="center",
            color="#CBD5E1", fontsize=12.5, fontproperties=FONT_PROP, linespacing=1.6)

    ax.text(0.5, 0.10, "★ 下次檢驗單若列出此項目，確認上傳後將自動為您繪製歷史走勢折線圖",
            ha="center", va="center", color="#64748B", fontsize=11, fontproperties=FONT_PROP)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ---------------------------------------------------------------------
# 2. 綜合儀表板（單期 8 格紅綠燈總覽 / 多期四大關鍵指標走勢看板）
# ---------------------------------------------------------------------


def render_summary_dashboard(
    report_or_history: dict[str, Any] | list[dict[str, Any]],
    patient_nickname: str = "長輩",
    overrides: dict[str, Any] | None = None,
) -> bytes:
    """繪製綜合儀表板。

    - 若為多期歷史且筆數 >= 2：繪製四大關鍵透析指標歷史走勢看板
    - 若為單期報告或筆數 == 1：繪製高規格 8 格紅綠燈健康指標總覽儀表板
    """
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
    """單期 8 格紅綠燈健康總覽儀表板（含水平安全量表指示條）。"""
    defs = get_metrics(overrides)
    test_date = latest_report.get("test_date", "最新檢驗")
    keys = ["potassium", "phosphorus", "hemoglobin", "albumin", "sodium", "calcium", "creatinine", "ipth"]

    fig = plt.figure(figsize=(10, 6.4), dpi=160)
    fig.patch.set_facecolor("#0F172A")

    ax_main = fig.add_axes([0.04, 0.04, 0.92, 0.92])
    ax_main.set_facecolor("#0F172A")
    ax_main.set_xticks([])
    ax_main.set_yticks([])
    for spine in ax_main.spines.values():
        spine.set_visible(False)

    ax_main.text(0.5, 0.96, f"{patient_nickname} 的健康檢驗總覽 ｜ 檢驗日期：{test_date}",
                 ha="center", va="center", color="#94A3B8", fontsize=13, fontproperties=FONT_PROP)
    ax_main.text(0.5, 0.90, "核心透析指標紅綠燈儀表板",
                 ha="center", va="center", color="#F8FAFC", fontsize=22, fontweight="bold", fontproperties=FONT_PROP)

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

        status_label, main_color, _ = _get_level_info(m, val)

        # 卡片框
        card_box = patches.FancyBboxPatch((cx, cy), card_w, card_h,
                                          boxstyle="round,pad=0.015,rounding_size=0.02",
                                          facecolor="#1E293B", edgecolor="#334155", linewidth=1.2)
        ax_main.add_patch(card_box)

        # 左側標誌色條
        strip = patches.FancyBboxPatch((cx, cy), 0.012, card_h,
                                       boxstyle="round,pad=0.005,rounding_size=0.01",
                                       facecolor=main_color, edgecolor=main_color)
        ax_main.add_patch(strip)

        # 名稱
        ax_main.text(cx + 0.03, cy + card_h - 0.035, f"{m.name} ({m.code})",
                     ha="left", va="center", color="#E2E8F0", fontsize=13, fontweight="bold", fontproperties=FONT_PROP)

        # 狀態標籤
        status_badge = patches.FancyBboxPatch((cx + card_w - 0.12, cy + card_h - 0.045), 0.10, 0.03,
                                              boxstyle="round,pad=0.005,rounding_size=0.01",
                                              facecolor=main_color, edgecolor=main_color)
        ax_main.add_patch(status_badge)
        ax_main.text(cx + card_w - 0.07, cy + card_h - 0.03, status_label,
                     ha="center", va="center", color="#FFFFFF" if main_color != "#F59E0B" else "#1E293B",
                     fontsize=9.5, fontweight="bold", fontproperties=FONT_PROP)

        # 數值文字
        fmt_val = m.fmt(val) if val is not None else "--"
        unit_str = f" {m.unit}" if m.unit else ""
        ax_main.text(cx + 0.03, cy + card_h - 0.09, fmt_val,
                     ha="left", va="center", color=main_color, fontsize=20, fontweight="bold", fontproperties=FONT_PROP)
        ax_main.text(cx + 0.16, cy + card_h - 0.088, unit_str,
                     ha="left", va="baseline", color="#94A3B8", fontsize=10, fontproperties=FONT_PROP)

        # 目標文字
        ax_main.text(cx + card_w - 0.02, cy + card_h - 0.09, f"目標: {m.range_text()}",
                     ha="right", va="center", color="#64748B", fontsize=10.5, fontproperties=FONT_PROP)

        # 底部微型量表條
        pbar_y = cy + 0.022
        pbar_w = card_w - 0.05
        pbar_h = 0.012
        pbg = patches.Rectangle((cx + 0.025, pbar_y), pbar_w, pbar_h, facecolor="#334155")
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
        ax_main.add_patch(patches.Rectangle((gx, pbar_y), gw, pbar_h, facecolor="#10B981", alpha=0.9))

        if val is not None:
            vx = cx + 0.025 + ((max(disp_min, min(disp_max, val)) - disp_min) / disp_range) * pbar_w
            ax_main.plot([vx], [pbar_y + pbar_h / 2], marker="o", markersize=6, color=main_color, markeredgecolor="#FFFFFF", markeredgewidth=1)

    ax_main.text(0.5, 0.015, "★ 首次檢驗紀錄已建檔！下個月上傳新報告後，將自動連線繪製跨月走勢折線圖",
                 ha="center", va="center", color="#64748B", fontsize=11, fontproperties=FONT_PROP)

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
    """四大關鍵透析指標歷史走勢看板。"""
    defs = get_metrics(overrides)
    core_keys = ["potassium", "phosphorus", "hemoglobin", "calcium"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.2), dpi=160)
    fig.patch.set_facecolor("#0F172A")

    fig.suptitle(f"{patient_nickname} 的四大關鍵透析指標歷史走勢看板",
                 fontsize=20, fontweight="bold", color="#F8FAFC", y=0.97, fontproperties=FONT_PROP)

    flat_axes = axes.flatten()
    for idx, k in enumerate(core_keys):
        ax = flat_axes[idx]
        ax.set_facecolor("#1E293B")
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
            ax.text(0.5, 0.5, f"{m.name} 尚無足夠數據", ha="center", va="center", color="#64748B", fontproperties=FONT_PROP)
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

        ax.axhspan(g_lo, g_hi, color="#10B981", alpha=0.15, zorder=1)
        if m.green_low is not None:
            ax.axhline(g_lo, color="#10B981", linestyle="--", linewidth=1.0, alpha=0.7)
        if m.green_high is not None:
            ax.axhline(g_hi, color="#10B981", linestyle="--", linewidth=1.0, alpha=0.7)

        ax.plot(dates_l, vals_l, color="#38BDF8", linewidth=2.8, zorder=3)
        ax.fill_between(dates_l, vals_l, y_bot, color="#38BDF8", alpha=0.08, zorder=2)

        for d, v in zip(dates_l, vals_l):
            _, c, _ = _get_level_info(m, v)
            ax.plot(d, v, marker="o", markersize=9, markerfacecolor=c, markeredgecolor="#FFFFFF", markeredgewidth=1.8, zorder=4)
            ax.text(d, v, f" {m.fmt(v)}", fontsize=11, fontweight="bold", color="#F8FAFC", va="bottom", fontproperties=FONT_PROP)

        unit_str = f" ({m.unit})" if m.unit else ""
        ax.set_title(f"{m.name} {m.code}{unit_str} [目標: {m.range_text()}]",
                     fontsize=13, fontweight="bold", color="#E2E8F0", pad=8, fontproperties=FONT_PROP)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.set_ylim(y_bot, y_top)
        ax.grid(axis="y", linestyle=":", alpha=0.2, color="#64748B")
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color("#334155")
        plt.setp(ax.get_xticklabels(), color="#94A3B8", fontsize=10)
        plt.setp(ax.get_yticklabels(), color="#94A3B8", fontsize=10)

    plt.tight_layout(rect=[0, 0.02, 1, 0.94])
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
