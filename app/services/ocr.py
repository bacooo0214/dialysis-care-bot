"""檢驗單照片 → 結構化數值（Gemini Vision + JSON schema）。"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from google.genai import types
from pydantic import BaseModel, Field

from app.config import get_settings
from app.metrics import METRICS
from app.services.llm import gemini

log = logging.getLogger(__name__)


# 注意：Gemini response_schema 不支援 default 值，所有欄位都設為 required + nullable
class OcrReport(BaseModel):
    """單一檢驗日期的一組數值。"""

    test_date: str | None = Field(description="檢驗日期，轉成西元 YYYY-MM-DD；民國年要加 1911；看不到填 null")
    potassium: float | None = Field(description="鉀 K，mEq/L 或 mmol/L")
    phosphorus: float | None = Field(description="磷 P / IP / 無機磷，mg/dL")
    calcium: float | None = Field(description="鈣 Ca，mg/dL")
    hemoglobin: float | None = Field(description="血紅素 Hb / 血色素，換算成 g/dL")
    sodium: float | None = Field(description="鈉 Na，mEq/L")
    albumin: float | None = Field(description="白蛋白 Alb，換算成 g/dL")
    bun: float | None = Field(description="透析前尿素氮 BUN（pre），mg/dL")
    creatinine: float | None = Field(description="肌酸酐 Cr / Creatinine，mg/dL")
    kt_v: float | None = Field(description="Kt/V 透析效率（若有 spKt/V 用它）")
    ipth: float | None = Field(description="副甲狀腺素 iPTH / PTH，pg/mL")
    uncertain_fields: list[str] = Field(description="字跡模糊或不確定的欄位英文名稱")


class OcrResult(BaseModel):
    """辨識結果。"""

    is_lab_report: bool = Field(description="這張圖是不是血液/透析檢驗報告")
    reports: list[OcrReport] = Field(description="每個檢驗日期一筆；表格若有多個月份欄位就回傳多筆")
    note: str | None = Field(description="給使用者的簡短說明，例如照片太暗、被裁切")


PROMPT = """你是台灣血液透析室的檢驗報告辨識專家。請從照片擷取檢驗數值。

規則：
1. 台灣透析紀錄表常見格式：列是檢驗項目、欄是月份/日期，一張表可能有多個月份，每個日期回傳一筆。
2. 日期若為民國年（例如 115/09/15、115.9.15），請加 1911 轉成西元（2026-09-15）。只有月/日時照原樣填（例如 09/15），並把 test_date 列入 uncertain_fields。
3. 常見別名：K=鉀、P/IP/Phosphate=磷、Ca=鈣、Hb/HGB=血紅素、Na=鈉、Alb=白蛋白、
   BUN(pre)/透析前BUN=尿素氮（只取透析前）、Cr/CRE=肌酸酐、Kt/V/spKt/V、iPTH/i-PTH=副甲狀腺素。
4. Hb 若是 g/L（例如 105）要換算成 g/dL（10.5）；Albumin 若是 g/L（例如 38）換成 g/dL（3.8）。
5. 只填照片上清楚看得到的數字，看不到就填 null，絕對不要猜或用參考值代替。
6. 參考值欄位（Reference / 正常值）不是病人的數值，不要擷取。
7. 不要擷取姓名、身分證、病歷號、床號等任何個人資料。
8. 如果不是檢驗報告（例如風景、食物、自拍），is_lab_report=false、reports=[]。
"""


async def recognize(image: bytes, mime_type: str = "image/jpeg") -> OcrResult:
    """呼叫 Gemini 辨識並做後處理。"""
    s = get_settings()
    resp = await gemini().aio.models.generate_content(
        model=s.gemini_model,
        contents=[types.Part.from_bytes(data=image, mime_type=mime_type), PROMPT],
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=OcrResult,
        ),
    )
    result = OcrResult.model_validate_json(resp.text or "{}")
    return postprocess(result)


def postprocess(result: OcrResult, today: date | None = None) -> OcrResult:
    """日期正規化、單位校正、生理合理性檢查、同日合併。"""
    today = today or date.today()
    merged: dict[str, OcrReport] = {}
    for r in result.reports:
        uncertain = set(r.uncertain_fields)
        parsed = normalize_date(r.test_date, today)
        if parsed is None:
            parsed = today
            uncertain.add("test_date")
        data = r.model_dump()
        data["test_date"] = parsed.isoformat()

        # 單位校正（模型偶爾沒換算）
        if data["hemoglobin"] is not None and 30 <= data["hemoglobin"] <= 200:
            data["hemoglobin"] = round(data["hemoglobin"] / 10, 1)
        if data["albumin"] is not None and 10 <= data["albumin"] <= 60:
            data["albumin"] = round(data["albumin"] / 10, 1)

        for key, m in METRICS.items():
            v = data.get(key)
            if v is not None and not m.is_plausible(v):
                log.info("drop implausible %s=%s", key, v)
                data[key] = None
                uncertain.add(key)

        data["uncertain_fields"] = sorted(uncertain)
        if not any(data.get(k) is not None for k in METRICS):
            continue
        key = data["test_date"]
        if key in merged:  # 同日兩欄（例如重複拍到）→ 補空值
            prev = merged[key].model_dump()
            for k, v in data.items():
                if prev.get(k) is None and v is not None:
                    prev[k] = v
            data = prev
        merged[key] = OcrReport.model_validate(data)

    reports = sorted(merged.values(), key=lambda x: x.test_date or "")[-6:]  # 最多 6 期，Flex carousel 才不會太長
    return OcrResult(is_lab_report=result.is_lab_report and bool(reports), reports=reports, note=result.note)


_DATE_RE = re.compile(r"(\d{2,4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})")
_MD_RE = re.compile(r"^\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})")


def normalize_date(raw: str | None, today: date) -> date | None:
    """支援西元、民國年、只有月日（推回最近一次不在未來的日期）。"""
    if not raw:
        return None
    m = _DATE_RE.search(raw)
    try:
        if m:
            y, mo, d = (int(x) for x in m.groups())
            if y < 1911:
                y += 1911
            result = date(y, mo, d)
        else:
            m2 = _MD_RE.search(raw)
            if not m2:
                return None
            mo, d = int(m2.group(1)), int(m2.group(2))
            result = date(today.year, mo, d)
            if result > today:
                result = date(today.year - 1, mo, d)
    except ValueError:
        return None
    if result > today or result.year < 2000:
        return None
    return result


def report_to_row(r: OcrReport) -> dict[str, Any]:
    """OcrReport → medical_reports 欄位。"""
    data = r.model_dump()
    return {k: data[k] for k in [*METRICS.keys(), "test_date", "uncertain_fields"]}
