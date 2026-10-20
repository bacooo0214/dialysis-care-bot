"""檢驗項目定義與紅綠燈判斷。

目標值參考 KDIGO / 台灣腎臟醫學會透析品質指標的常見區間；
各院目標不同，可用 families.metric_overrides 覆寫，例如：
    {"potassium": {"green_high": 5.5}, "hemoglobin": {"green_low": 9.5}}
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any


class Level(StrEnum):
    """紅綠燈等級。"""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNKNOWN = "unknown"


LEVEL_ORDER = {Level.UNKNOWN: -1, Level.GREEN: 0, Level.YELLOW: 1, Level.RED: 2}
LEVEL_EMOJI = {Level.GREEN: "🟢", Level.YELLOW: "🟡", Level.RED: "🔴", Level.UNKNOWN: "⚪"}
# 刻意不用「危險」「異常」等恐嚇字眼
LEVEL_LABEL = {Level.GREEN: "很好", Level.YELLOW: "要注意", Level.RED: "要小心", Level.UNKNOWN: "沒資料"}
LEVEL_COLOR = {
    Level.GREEN: "#1E9E5A",
    Level.YELLOW: "#E8A400",
    Level.RED: "#D93A3A",
    Level.UNKNOWN: "#9AA0A6",
}


@dataclass(frozen=True)
class MetricDef:
    """單一檢驗項目。

    判斷邏輯：
        green_low <= v <= green_high          → 綠
        v < red_low 或 v > red_high            → 紅
        其他                                  → 黃
    None 代表該側沒有界線。
    """

    key: str
    name: str  # 長輩看的名稱
    code: str  # 檢驗單上的縮寫
    unit: str
    green_low: float | None
    green_high: float | None
    red_low: float | None
    red_high: float | None
    plausible_low: float  # 超出視為辨識錯誤
    plausible_high: float
    decimals: int = 1
    lightable: bool = True
    chartable: bool = True
    hint_high: str = ""
    hint_low: str = ""

    def classify(self, value: float | None) -> Level:
        """回傳紅綠燈等級。"""
        if value is None or not self.lightable:
            return Level.UNKNOWN
        v = float(value)
        if self.red_low is not None and v < self.red_low:
            return Level.RED
        if self.red_high is not None and v > self.red_high:
            return Level.RED
        lo_ok = self.green_low is None or v >= self.green_low
        hi_ok = self.green_high is None or v <= self.green_high
        return Level.GREEN if lo_ok and hi_ok else Level.YELLOW

    def direction(self, value: float | None) -> str | None:
        """偏高 high / 偏低 low / 正常 None。"""
        if value is None:
            return None
        v = float(value)
        if self.green_high is not None and v > self.green_high:
            return "high"
        if self.green_low is not None and v < self.green_low:
            return "low"
        return None

    def is_plausible(self, value: float | None) -> bool:
        """數值是否在生理可能範圍。"""
        return value is not None and self.plausible_low <= float(value) <= self.plausible_high

    def fmt(self, value: float | None) -> str:
        """格式化數值。"""
        if value is None:
            return "—"
        return f"{float(value):.{self.decimals}f}"

    def range_text(self) -> str:
        """安全範圍文字。"""
        lo, hi = self.green_low, self.green_high
        if lo is not None and hi is not None:
            return f"{lo:g}–{hi:g}"
        if lo is not None:
            return f"≥ {lo:g}"
        if hi is not None:
            return f"≤ {hi:g}"
        return "—"


METRICS: dict[str, MetricDef] = {
    m.key: m
    for m in [
        MetricDef(
            "potassium", "鉀", "K", "mEq/L", 3.5, 5.0, 3.0, 6.0, 1.5, 10.0, 1,
            hint_high="心跳可能會亂", hint_low="容易沒力氣",
        ),
        MetricDef(
            "phosphorus", "磷", "P", "mg/dL", 3.5, 5.5, 2.5, 7.0, 0.5, 20.0, 1,
            hint_high="皮膚癢、骨頭會變脆",
        ),
        MetricDef("calcium", "鈣", "Ca", "mg/dL", 8.4, 10.2, 7.5, 11.0, 4.0, 16.0, 1),
        MetricDef(
            "hemoglobin", "血紅素", "Hb", "g/dL", 10.0, 11.5, 8.0, 13.0, 3.0, 20.0, 1,
            hint_low="容易累、頭暈、喘",
        ),
        MetricDef("sodium", "鈉", "Na", "mEq/L", 135, 145, 130, 150, 100, 180, 0),
        MetricDef(
            "albumin", "白蛋白", "Alb", "g/dL", 3.5, None, 3.0, None, 1.0, 6.0, 1,
            hint_low="營養不夠、抵抗力差",
        ),
        MetricDef("kt_v", "透析效率", "Kt/V", "", 1.2, None, 1.0, None, 0.3, 3.5, 2),
        MetricDef("ipth", "副甲狀腺素", "iPTH", "pg/mL", 150, 600, 100, 800, 1, 5000, 0),
        MetricDef(
            "bun", "尿素氮", "BUN", "mg/dL", None, None, None, None, 5, 250, 0,
            lightable=False, chartable=False,
        ),
        MetricDef(
            "creatinine", "肌酸酐", "Cr", "mg/dL", None, None, None, None, 0.5, 25, 1,
            lightable=False, chartable=False,
        ),
    ]
}

# 長輩最在意、圖表選單優先順序
CORE_METRICS = ["potassium", "phosphorus", "hemoglobin", "albumin", "sodium", "calcium", "kt_v", "ipth"]

_OVERRIDABLE = {"green_low", "green_high", "red_low", "red_high"}


def get_metrics(overrides: dict[str, Any] | None = None) -> dict[str, MetricDef]:
    """套用家庭個別目標值後的定義。"""
    if not overrides:
        return METRICS
    out = dict(METRICS)
    for key, patch in overrides.items():
        if key in out and isinstance(patch, dict):
            clean = {k: (None if v is None else float(v)) for k, v in patch.items() if k in _OVERRIDABLE}
            out[key] = replace(out[key], **clean)
    return out


@dataclass
class MetricResult:
    """單一項目的判讀結果。"""

    metric: MetricDef
    value: float | None
    level: Level
    direction: str | None
    previous: float | None = None

    @property
    def trend(self) -> str:
        """與上次比較：↑ ↓ →。"""
        if self.value is None or self.previous is None:
            return ""
        diff = float(self.value) - float(self.previous)
        tol = 10 ** (-self.metric.decimals)
        if abs(diff) < tol:
            return "→"
        return "↑" if diff > 0 else "↓"


def evaluate_report(
    report: dict[str, Any],
    previous: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
) -> list[MetricResult]:
    """判讀整份報告（只回傳有亮燈資格的項目）。"""
    defs = get_metrics(overrides)
    results: list[MetricResult] = []
    for key in CORE_METRICS:
        m = defs[key]
        v = _num(report.get(key))
        prev = _num(previous.get(key)) if previous else None
        results.append(MetricResult(m, v, m.classify(v), m.direction(v), prev))
    return results


def worst_level(levels: list[Level]) -> Level:
    """取最嚴重燈號。"""
    return max(levels, key=lambda lv: LEVEL_ORDER[lv], default=Level.UNKNOWN)


# ---------------------------------------------------------------------
# 日常紀錄判讀
# ---------------------------------------------------------------------


def classify_weight_gain(weight: float | None, dry_weight: float | None) -> tuple[Level, float | None]:
    """透析間體重增加（相對乾體重 %）：≤3% 綠、≤5% 黃、>5% 紅。"""
    if weight is None or not dry_weight:
        return Level.UNKNOWN, None
    pct = (float(weight) - float(dry_weight)) / float(dry_weight) * 100
    if pct <= 3:
        return Level.GREEN, pct
    if pct <= 5:
        return Level.YELLOW, pct
    return Level.RED, pct


def classify_bp(systolic: int | None, diastolic: int | None) -> tuple[Level, str | None]:
    """透析病人血壓：收縮壓 90–139 綠；<90 或 ≥180 紅；舒張壓 ≥110 紅。"""
    if systolic is None:
        return Level.UNKNOWN, None
    s, d = int(systolic), int(diastolic or 0)
    if s < 90:
        return Level.RED, "low"
    if s >= 180 or d >= 110:
        return Level.RED, "high"
    if s >= 140 or d >= 90:
        return Level.YELLOW, "high"
    if s < 100:
        return Level.YELLOW, "low"
    return Level.GREEN, None


def classify_water(water_ml: int, limit_ml: int) -> Level:
    """喝水量：≤80% 綠、≤100% 黃、>100% 紅。"""
    if limit_ml <= 0:
        return Level.UNKNOWN
    ratio = water_ml / limit_ml
    if ratio <= 0.8:
        return Level.GREEN
    if ratio <= 1.0:
        return Level.YELLOW
    return Level.RED


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@dataclass
class CriticalAlert:
    """臨床重大危急值警報項目。"""

    metric_key: str
    name: str
    code: str
    value: float
    unit: str
    severity: str  # "danger" (極度致命危險) 或 "warning" (高度警戒)
    reason: str
    action: str


def detect_critical_alerts(report: dict[str, Any]) -> list[CriticalAlert]:
    """檢測透析臨床關鍵危急值 (Critical Values)。
    
    依據 KDOQI / KDIGO 指南：
    - 血鉀 (K) >= 5.5 (特別是 >= 6.0 致命性心律不整) 或 < 3.2
    - 血紅素 (Hb) < 8.0 (重度貧血、缺氧與心臟負荷急增)
    - 血鈣 (Ca) > 11.5 或 < 7.0 (急性電解質危象)
    - 血磷 (P) > 7.0 (血管急遽鈣化危險期)
    """
    alerts: list[CriticalAlert] = []

    # 1. 鉀離子 (Potassium)
    k_val = _num(report.get("potassium"))
    if k_val is not None:
        if k_val >= 6.0:
            alerts.append(
                CriticalAlert(
                    metric_key="potassium",
                    name="血鉀",
                    code="K",
                    value=k_val,
                    unit="mEq/L",
                    severity="danger",
                    reason="血鉀高達致命危險區間 (≥6.0 mEq/L)，極易誘發心室顫動甚至心搏驟停！",
                    action="請立即聯絡透析室值班醫師或前往急診處置！嚴格禁吃任何高鉀水果、菜湯、高湯或中草藥！",
                )
            )
        elif k_val >= 5.5:
            alerts.append(
                CriticalAlert(
                    metric_key="potassium",
                    name="血鉀",
                    code="K",
                    value=k_val,
                    unit="mEq/L",
                    severity="danger",
                    reason="血鉀偏高 (≥5.5 mEq/L)，已達臨床警報紅線，心肌傳導受阻風險激增！",
                    action="請盡速回報透析室護理師或醫師；今日嚴格禁食生菜沙拉、香蕉、番茄、奇異果與肉湯！",
                )
            )
        elif k_val < 3.2:
            alerts.append(
                CriticalAlert(
                    metric_key="potassium",
                    name="血鉀",
                    code="K",
                    value=k_val,
                    unit="mEq/L",
                    severity="danger",
                    reason="血鉀過低 (<3.2 mEq/L)，易引發嚴重肢體無力、呼吸麻痺或惡性心律不整！",
                    action="請盡快告知主治醫師，評估是否調整透析液鉀濃度或口服補鉀處方。",
                )
            )

    # 2. 血紅素 (Hemoglobin)
    hb_val = _num(report.get("hemoglobin"))
    if hb_val is not None and hb_val < 8.0:
        alerts.append(
            CriticalAlert(
                metric_key="hemoglobin",
                name="血紅素",
                code="Hb",
                value=hb_val,
                unit="g/dL",
                severity="danger",
                reason="血紅素低於 8.0 g/dL，屬重度貧血，心臟代償負荷急遽攀升，易引起心衰竭與缺氧喘促！",
                action="請提早於下次透析向醫師反應，確認是否需要安排加驗鐵質飽和度或調整造血針劑量。",
            )
        )

    # 3. 鈣離子 (Calcium)
    ca_val = _num(report.get("calcium"))
    if ca_val is not None:
        if ca_val > 11.5:
            alerts.append(
                CriticalAlert(
                    metric_key="calcium",
                    name="血鈣",
                    code="Ca",
                    value=ca_val,
                    unit="mg/dL",
                    severity="danger",
                    reason="血鈣嚴重超標 (>11.5 mg/dL)，易引起嗜睡、意識混亂、胃腸痙攣及心血管毒性！",
                    action="請立即告知主治醫師，通常需暫停含鈣降磷劑與活性維生素 D。",
                )
            )
        elif ca_val < 7.0:
            alerts.append(
                CriticalAlert(
                    metric_key="calcium",
                    name="血鈣",
                    code="Ca",
                    value=ca_val,
                    unit="mg/dL",
                    severity="danger",
                    reason="血鈣嚴重低下 (<7.0 mg/dL)，易引發手指發麻、抽搐痙攣與心肌收縮異常！",
                    action="請盡速向透析室反應，評估注射補充葡萄糖酸鈣或調整透析液鈣濃度。",
                )
            )

    # 4. 磷離子 (Phosphorus)
    p_val = _num(report.get("phosphorus"))
    if p_val is not None and p_val > 7.0:
        alerts.append(
            CriticalAlert(
                metric_key="phosphorus",
                name="血磷",
                code="P",
                value=p_val,
                unit="mg/dL",
                severity="warning",
                reason="血磷過高 (>7.0 mg/dL)，會劇烈加速全身動脈血管鈣化並誘發頑固皮膚劇癢！",
                action="務必餐餐隨第一口飯咬碎磷結合劑，嚴格禁止香腸肉丸等加工品與濃肉汁骨湯！",
            )
        )

    return alerts

