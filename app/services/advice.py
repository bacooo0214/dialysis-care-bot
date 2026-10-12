"""AI 白話照護建議：結合 care_rules 知識庫 + 紅綠燈結果。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from google.genai import types
from pydantic import BaseModel, Field

from app.config import get_settings
from app.metrics import LEVEL_LABEL, Level, MetricResult
from app.services.llm import gemini

log = logging.getLogger(__name__)


@dataclass
class Finding:
    """一個需要建議的發現（檢驗或日常）。"""

    metric: str  # care_rules.metric
    name: str
    level: Level
    direction: str | None
    value_text: str
    trend: str = ""


class AdviceOut(BaseModel):
    """模型輸出。"""

    text: str = Field(description="LINE 顯示用的建議，可用少量 emoji，150~260 字")
    speech: str = Field(description="給語音播報的版本：同內容但不含 emoji、符號、英文縮寫與數字單位縮寫，口語化")


SYSTEM = """你是「腎好伴」，一位溫暖、有耐心的透析照護小幫手，說話對象是 70~85 歲、正在洗腎的台灣長輩和他的家人。

說話方式：
- 用台灣口語白話文，像孫子/孫女跟阿公阿嬤講話，一句不超過 20 個字。
- 先肯定、再提醒，最後鼓勵。不用「危險」「嚴重」「死亡」「洗腎失敗」等嚇人字眼。
- 最多 3 個重點，每個重點都是「今天就能做的具體動作」（吃什麼、怎麼煮、怎麼喝水），不要講大道理。
- 優先採用「家屬的經驗」，其次才是一般衛教。
- 不能叫長輩自己改藥、停藥或調整劑量；藥物問題一律說「下次透析時問醫師/護理師」。
- 如果有「要小心」(紅燈)的項目，必須保留知識庫裡的就醫警訊（什麼症狀要馬上就醫），但語氣要溫和。
- 不要列出檢驗數字的參考範圍，不要用英文縮寫（K、P 要說鉀、磷）。
"""


def build_findings(results: list[MetricResult]) -> list[Finding]:
    """從檢驗結果挑出黃/紅燈項目。"""
    out: list[Finding] = []
    for r in results:
        if r.level in (Level.YELLOW, Level.RED):
            out.append(
                Finding(
                    metric=r.metric.key,
                    name=r.metric.name,
                    level=r.level,
                    direction=r.direction,
                    value_text=f"{r.metric.fmt(r.value)} {r.metric.unit}".strip(),
                    trend=r.trend,
                )
            )
    return out


def match_rules(rules: list[dict[str, Any]], findings: list[Finding], limit: int = 12) -> list[dict[str, Any]]:
    """依 metric / direction / level 篩選知識庫規則。紅燈規則與家屬規則一定保留。"""
    picked: list[dict[str, Any]] = []
    for f in findings:
        for rule in rules:
            if rule.get("metric") not in (f.metric, None):
                continue
            if rule["direction"] not in ("any", f.direction):
                continue
            if rule["min_level"] == "red" and f.level != Level.RED:
                continue
            if rule not in picked:
                picked.append(rule)
    must = [r for r in picked if r["min_level"] == "red" or r.get("family_id")]
    rest = [r for r in picked if r not in must]
    return (must + rest)[:limit]


def _prompt(nickname: str, findings: list[Finding], rules: list[dict[str, Any]], context: str) -> str:
    lines = [f"長輩稱呼：{nickname}", "", "這次需要注意的項目："]
    for f in findings:
        dir_text = {"high": "偏高", "low": "偏低"}.get(f.direction or "", "")
        trend = {"↑": "，比上次高", "↓": "，比上次低", "→": "，跟上次差不多"}.get(f.trend, "")
        lines.append(f"- {f.name}：{f.value_text}，{dir_text}，燈號「{LEVEL_LABEL[f.level]}」{trend}")
    if context:
        lines += ["", f"其他狀況：{context}"]
    fam = [r for r in rules if r.get("family_id")]
    gen = [r for r in rules if not r.get("family_id")]
    if fam:
        lines += ["", "【家屬的經驗（優先採用）】"] + [f"- {r['title']}：{r['content']}" for r in fam]
    if gen:
        lines += ["", "【一般衛教知識】"] + [f"- {r['title']}：{r['content']}" for r in gen]
    lines += ["", f"請用「{nickname}」稱呼長輩，寫一段建議。"]
    return "\n".join(lines)


async def generate_advice(
    nickname: str, findings: list[Finding], rules: list[dict[str, Any]], context: str = ""
) -> AdviceOut:
    """產生建議；Gemini 失敗時用知識庫組出保底內容，絕不讓使用者收到空訊息。"""
    if not findings:
        text = f"{nickname}這次的數字都很好 🎉 繼續保持現在的吃法和喝水習慣，全家都以您為榮！"
        return AdviceOut(text=text, speech=strip_for_speech(text))
    matched = match_rules(rules, findings)
    try:
        resp = await gemini().aio.models.generate_content(
            model=get_settings().gemini_model,
            contents=_prompt(nickname, findings, matched, context),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                temperature=0.6,
                response_mime_type="application/json",
                response_schema=AdviceOut,
            ),
        )
        out = AdviceOut.model_validate_json(resp.text or "{}")
        out.speech = strip_for_speech(out.speech or out.text)
        return out
    except Exception:  # noqa: BLE001
        log.exception("advice generation failed, fallback to rules")
        return fallback_advice(nickname, findings, matched)


def fallback_advice(nickname: str, findings: list[Finding], rules: list[dict[str, Any]]) -> AdviceOut:
    """不靠 AI 的保底建議。"""
    names = "、".join(f.name for f in findings)
    tips = [r["content"] for r in rules if r.get("metric")][:3]
    text = f"{nickname}，這次{names}要多注意一下喔 💪\n\n" + "\n".join(f"✅ {t}" for t in tips)
    text += "\n\n慢慢調整就好，我們一起加油！"
    return AdviceOut(text=text, speech=strip_for_speech(text))


_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF\uFE0F\u200d\u2B50\u2B55\u2705\u274C]"
)


def strip_for_speech(text: str) -> str:
    """移除 emoji/符號，讓 TTS 唸起來自然。"""
    t = _EMOJI_RE.sub("", text)
    t = t.replace("mEq/L", "").replace("mg/dL", "").replace("g/dL", "").replace("pg/mL", "")
    t = re.sub(r"[#*_~`>•●▶️\-–—]+", " ", t)
    t = re.sub(r"\s*\n+\s*", "。", t)
    t = re.sub(r"。{2,}", "。", t)
    return re.sub(r"\s{2,}", " ", t).strip(" 。") + "。"


# ---------------------------------------------------------------------
# 家屬新增經驗：AI 自動分類 metric / direction
# ---------------------------------------------------------------------


class RuleClassification(BaseModel):
    """家屬經驗分類結果。"""

    metric: str | None = Field(
        description="potassium/phosphorus/calcium/hemoglobin/sodium/albumin/kt_v/ipth/weight_gain/water/bp 其一，無法判斷填 null"
    )
    direction: str = Field(description="high / low / any")
    title: str = Field(description="10 字內標題")


async def classify_rule(content: str) -> RuleClassification:
    """把家屬輸入的一句經驗分類成 care_rules 欄位。"""
    try:
        resp = await gemini().aio.models.generate_content(
            model=get_settings().gemini_model,
            contents=f"把這段洗腎照護經驗分類：\n{content}",
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=RuleClassification,
            ),
        )
        out = RuleClassification.model_validate_json(resp.text or "{}")
        if out.direction not in ("high", "low", "any"):
            out.direction = "any"
        return out
    except Exception:  # noqa: BLE001
        log.exception("rule classification failed")
        return RuleClassification(metric=None, direction="any", title=content[:10])
