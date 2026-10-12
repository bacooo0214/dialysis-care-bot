"""檢驗數據可視化圖表渲染。

專為高齡視力與手機螢幕設計：
- 2x 高解析度繪圖 (DPI=160)，文字特大 (16~22pt)，高對比配色
- 綠色底帶表示「安全目標範圍」
- 數據點依紅黃綠燈著色，並在點旁標註數值與單位
- 自動偵測系統可用的中文字型（Windows / Linux / Docker）
"""

from __future__ import annotations

import io
import logging
from datetime import date
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

from app.metrics import LEVEL_COLOR, METRICS, MetricDef, get_metrics

log = logging.getLogger(__name__)

# 中文字型偏好清單
FONT_CANDIDATES = [
    "Noto Sans CJK TC",
    "Noto Sans TC",
    "Microsoft JhengHei",
    "PingFang TC",
    "Source Han Sans TC",
    "WenQuanYi Zen Hei",
    "DFKai-SB",
    "Arial Unicode MS",
]


def _setup_chinese_font() -> str:
    """自動偵測並設定可用中文字型。"""
    available = {f.name for f in fm.fontManager.ttflist}
    for font in FONT_CANDIDATES:
        if font in available:
            plt.rcParams["font.family"] = font
            plt.rcParams["font.sans-serif"] = [font, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            return font

    # 若都沒有，使用預設無襯線字型
    plt.rcParams["font.sans-serif"] = ["sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    return "sans-serif"


CHOSEN_FONT = _setup_chinese_font()


def render_metric_trend(
    metric_key: str,
    reports: list[dict[str, Any]],
    patient_nickname: str = "長輩",
    overrides: dict[str, Any] | None = None,
) -> bytes:
    """繪製單一檢驗指標的歷史趨勢折線圖。

    reports: 舊到新排序的確認報告列表
    回傳: PNG 圖片的 bytes
    """
    defs = get_metrics(overrides)
    m = defs.get(metric_key, METRICS.get(metric_key))
    if not m:
        raise ValueError(f"未知的檢驗項目: {metric_key}")

    # 提取有效數據點
    dates: list[date] = []
    values: list[float] = []
    for r in reports:
        raw_val = r.get(metric_key)
        raw_date = r.get("test_date")
        if raw_val is not None and raw_date:
            try:
                d = date.fromisoformat(str(raw_date)[:10])
                v = float(raw_val)
                dates.append(d)
                values.append(v)
            except (ValueError, TypeError):
                continue

    if not dates:
        return _render_empty_chart(f"{patient_nickname} 的 {m.name} 尚無足夠數據")

    fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=160)
    fig.patch.set_facecolor("#FAFAFC")
    ax.set_facecolor("#FFFFFF")

    # 1. 繪製安全目標範圍底色帶（柔和淺綠色）
    y_min_data = min(values)
    y_max_data = max(values)
    y_span = max(y_max_data - y_min_data, 1.0)
    y_bottom = min(y_min_data - y_span * 0.25, (m.green_low or y_min_data) - 0.5)
    y_top = max(y_max_data + y_span * 0.35, (m.green_high or y_max_data) + 0.5)

    g_low = m.green_low if m.green_low is not None else y_bottom
    g_high = m.green_high if m.green_high is not None else y_top

    ax.axhspan(
        g_low,
        g_high,
        color="#E6F4EA",
        alpha=0.7,
        zorder=1,
        label=f"安全目標 ({m.range_text()} {m.unit})",
    )

    # 繪製基準線
    if m.green_low is not None:
        ax.axhline(m.green_low, color="#34A853", linestyle="--", linewidth=1.5, alpha=0.8, zorder=2)
    if m.green_high is not None:
        ax.axhline(m.green_high, color="#34A853", linestyle="--", linewidth=1.5, alpha=0.8, zorder=2)

    # 2. 趨勢折線
    ax.plot(
        dates,
        values,
        color="#2D3748",
        linestyle="-",
        linewidth=3.5,
        zorder=3,
        alpha=0.9,
    )

    # 3. 數據點與標註（依紅黃綠著色）
    for d, v in zip(dates, values):
        level = m.classify(v)
        color = LEVEL_COLOR[level]
        # 外圈白色強化對比
        ax.plot(d, v, marker="o", markersize=14, markerfacecolor=color, markeredgecolor="#FFFFFF", markeredgewidth=2.5, zorder=4)

        # 數值文字放大
        fmt_val = m.fmt(v)
        ax.annotate(
            fmt_val,
            xy=(d, v),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=15,
            fontweight="bold",
            color="#1A202C",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#FFFFFF", edgecolor=color, alpha=0.9, linewidth=1.5),
            zorder=5,
        )

    # 標題與標籤（長輩友善大字體）
    unit_str = f" ({m.unit})" if m.unit else ""
    ax.set_title(
        f"{patient_nickname} 的【{m.name} {m.code}】趨勢圖",
        fontsize=20,
        fontweight="bold",
        pad=18,
        color="#1A202C",
    )
    ax.set_ylabel(f"{m.name}{unit_str}", fontsize=15, fontweight="bold", color="#4A5568", labelpad=10)

    # X 軸日期格式
    if len(dates) == 1:
        # 單一數據點時擴展 X 軸範圍
        ax.set_xlim(dates[0] - mdates.relativedelta(days=15), dates[0] + mdates.relativedelta(days=15))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(fontsize=14, fontweight="bold", color="#4A5568")
    plt.yticks(fontsize=14, color="#4A5568")

    # Y 軸安全範圍邊界
    ax.set_ylim(y_bottom, y_top)

    # 網格線
    ax.grid(axis="y", linestyle=":", alpha=0.5, color="#A0AEC0")
    ax.set_axisbelow(True)

    # 圖例（置頂右側）
    ax.legend(
        loc="upper right",
        frameon=True,
        facecolor="#FFFFFF",
        edgecolor="#CBD5E0",
        fontsize=13,
    )

    # 移除多餘邊框
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#CBD5E0")
        ax.spines[spine].set_linewidth(1.2)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def render_summary_dashboard(
    latest_report: dict[str, Any],
    patient_nickname: str = "長輩",
    overrides: dict[str, Any] | None = None,
) -> bytes:
    """繪製最新報告的長輩專用「紅綠燈綜合儀表板」圖卡。

    以色塊 + 大字清晰呈現各項指標狀態，適合長輩一目了然。
    """
    from app.metrics import CORE_METRICS, Level

    defs = get_metrics(overrides)
    items: list[tuple[MetricDef, float | None, Level]] = []
    for k in CORE_METRICS:
        m = defs[k]
        val = None
        if latest_report.get(k) is not None:
            try:
                val = float(latest_report[k])
            except (ValueError, TypeError):
                val = None
        items.append((m, val, m.classify(val)))

    # 2 行 x 4 列的卡片佈局
    fig, axes = plt.subplots(2, 4, figsize=(10, 5.6), dpi=160)
    fig.patch.set_facecolor("#F7FAFC")

    test_date = latest_report.get("test_date", "")
    fig.suptitle(
        f"{patient_nickname} 的檢驗紅綠燈總覽 ({test_date})",
        fontsize=22,
        fontweight="bold",
        color="#1A202C",
        y=0.98,
    )

    flat_axes = axes.flatten()
    for idx, (m, val, lv) in enumerate(items):
        ax = flat_axes[idx]
        ax.set_facecolor("#FFFFFF")
        ax.set_xticks([])
        ax.set_yticks([])

        color = LEVEL_COLOR[lv]
        status_text = {
            Level.GREEN: "🟢 很好",
            Level.YELLOW: "🟡 注意",
            Level.RED: "🔴 警戒",
            Level.UNKNOWN: "⚪ 未測",
        }[lv]

        # 卡片邊框加粗對應顏色
        for spine in ax.spines.values():
            spine.set_color(color)
            spine.set_linewidth(3.5 if lv in (Level.YELLOW, Level.RED) else 1.5)

        # 項目名稱
        ax.text(
            0.5, 0.78,
            f"{m.name} ({m.code})",
            ha="center", va="center",
            fontsize=15, fontweight="bold",
            color="#2D3748",
            transform=ax.transAxes,
        )

        # 數值文字（超大）
        val_str = m.fmt(val) if val is not None else "—"
        ax.text(
            0.5, 0.48,
            val_str,
            ha="center", va="center",
            fontsize=24, fontweight="bold",
            color=color,
            transform=ax.transAxes,
        )

        # 目標與狀態
        target_str = f"目標: {m.range_text()} {m.unit}".strip()
        ax.text(
            0.5, 0.22,
            f"{status_text}\n{target_str}",
            ha="center", va="center",
            fontsize=11, color="#718096",
            transform=ax.transAxes,
        )

    plt.tight_layout(rect=[0, 0.03, 1, 0.93])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _render_empty_chart(msg: str) -> bytes:
    """無數據時的提示圖片。"""
    fig, ax = plt.subplots(figsize=(7, 3.5), dpi=140)
    fig.patch.set_facecolor("#F7FAFC")
    ax.set_facecolor("#FFFFFF")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#E2E8F0")

    ax.text(
        0.5, 0.5, msg,
        ha="center", va="center",
        fontsize=16, fontweight="bold",
        color="#718096",
        transform=ax.transAxes,
    )
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
