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
