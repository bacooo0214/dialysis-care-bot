"""AI 白話照護建議：結合 care_rules 知識庫 + 紅綠燈結果。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from google.genai import types
from pydantic import BaseModel, Field

from app.config import get_settings
from app.metrics import LEVEL_LABEL, METRICS, Level, MetricResult
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


# ---------------------------------------------------------------------
# 自然語言對話與數據統整：AI 照護專員
# ---------------------------------------------------------------------

QUERY_SYSTEM = """你是「腎好伴」，一位溫暖、專業、有耐心的血液透析照護小幫手（雲端小乖孫），對象是正在洗腎的台灣長輩與其家屬。

重要原則：
1. 說話語氣：台灣在地口語白話、溫暖親切、像有同理心的醫療照護專員或貼心孫輩，不用死板機器人口氣。
2. 結合實際數據：如果提供了長輩的檢驗數據或日常紀錄，請【主動且精準地引用這些數值】來回答使用者的問題（例如指出鉀 5.1 稍高、血紅素 8.7 偏低等）。
3. 實用且具體：給出 2~3 點日常可立即實踐的生活、飲食技巧（如汆燙蔬菜去鉀、吃肉配降磷劑、口渴含冰塊），不要講空泛大道理。
4. 安全守則：嚴禁指示擅自停藥或改藥，藥物問題一律請示透析醫護團隊；不用恐嚇威脅字眼。
5. 簡潔適中：字數控制在 160 ~ 280 字以內，方便在 LINE 手機螢幕上快速閱讀。
"""


async def answer_patient_query(
    query: str,
    patient_nickname: str = "長輩",
    latest_report: dict[str, Any] | None = None,
    daily_record: dict[str, Any] | None = None,
    rules: list[dict[str, Any]] | None = None,
) -> str:
    """針對使用者在 LINE 的隨意提問，結合當前檢驗數據與衛教知識產生 AI 統整回覆。"""
    lines = [f"長輩稱呼：{patient_nickname}", f"使用者問題：{query}"]

    if latest_report:
        lines.append(f"\n【最新檢驗報告 ({latest_report.get('test_date')})】")
        for k in ["potassium", "phosphorus", "calcium", "hemoglobin", "sodium", "albumin", "creatinine", "kt_v", "ipth"]:
            val = latest_report.get(k)
            if val is not None:
                m = METRICS.get(k)
                if m:
                    lines.append(f"- {m.name} ({m.code}): {m.fmt(val)} {m.unit} (目標: {m.range_text()})")
    else:
        lines.append("\n【最新檢驗報告】：目前尚無已確認的報告紀錄。")

    if daily_record:
        lines.append(f"\n【今日自主管理紀錄】")
        if daily_record.get("weight_kg"):
            lines.append(f"- 今日體重: {daily_record.get('weight_kg')} kg")
        if daily_record.get("systolic") and daily_record.get("diastolic"):
            lines.append(f"- 今日血壓: {daily_record.get('systolic')}/{daily_record.get('diastolic')} mmHg")
        if daily_record.get("water_ml"):
            lines.append(f"- 今日喝水: {daily_record.get('water_ml')} ml")

    if rules:
        fam_rules = [r for r in rules if r.get("family_id")]
        if fam_rules:
            lines.append("\n【家屬照護經驗（優先採用）】")
            for r in fam_rules[:3]:
                lines.append(f"- {r.get('title')}: {r.get('content')}")

    prompt_content = "\n".join(lines)
    try:
        resp = await gemini().aio.models.generate_content(
            model=get_settings().gemini_model,
            contents=prompt_content,
            config=types.GenerateContentConfig(
                system_instruction=QUERY_SYSTEM,
                temperature=0.6,
            ),
        )
        return resp.text.strip() if resp.text else f"收到您的問題！{patient_nickname}的身體狀況很重要，有任何不適建議隨時告知透析室醫護團隊喔！"
    except Exception:
        log.exception("answer_patient_query failed")
        return f"{patient_nickname}的照護非常重要！關於「{query}」，建議您在下次透析時向護理師或醫師進一步諮詢喔！"


# ---------------------------------------------------------------------
# 門診專用「30 秒就醫小抄 / 醫師問診備忘錄」生成
# ---------------------------------------------------------------------


class ClinicMemoOut(BaseModel):
    """門診 30 秒就醫小抄結構。"""

    summary_headline: str = Field(description="簡要標題，例如：近三期核心指標走勢與門診問診備忘")
    overview_text: str = Field(description="30 秒看診重點陳述，讓醫師快速掌握長輩近況與變化")
    key_highlights: list[str] = Field(
        description="2~4 項數值關鍵亮點對比，例如：['血紅素 (Hb)：8.7 → 10.1 → 11.6 g/dL（大幅改善）', '血鉀 (K)：5.1 mEq/L（維持安全區）', '副甲狀腺素 (iPTH)：614.8 pg/mL（仍偏高）']"
    )
    doctor_questions: list[str] = Field(
        description="建議在診間主動向醫師詢問的 2~3 個精準問題，切合當前指標狀態"
    )
    daily_reminders: list[str] = Field(
        description="透析與日常照護注意事項（乾體重、水分控制、用藥時機）"
    )


CLINIC_MEMO_SYSTEM = """你是台灣權威腎臟內科與血液透析資深照護專家。
請根據提供的長輩檢驗歷史報告（通常為近 2~3 期）與日常紀錄，為長輩或陪診家屬整理一份【門診專用 30 秒就醫小抄】。

目標：
1. 醫師門診時間緊湊，長輩往往不知道該看什麼、問什麼。
2. 小抄必須讓陪診家屬能在 30 秒內向醫師清晰說明近期變化，並主動提出「最關鍵、最具臨床意義的 2~3 個提問」。
3. 數值亮點：清楚標註跨期數值消長（例如 Hb 8.7 → 10.1 → 11.6、K 5.1、iPTH 614.8 等）。
4. 專業問診設計：
   - 若貧血達標（Hb >= 11），詢問是否需要調減紅血球生成素 (EPO) 劑量。
   - 若血鉀高（K >= 5.3），詢問利尿劑或透析液設定。
   - 若副甲狀腺素高（iPTH > 300~600），詢問是否評估擬鈣劑 (Cinacalcet/Etelcalcetide) 或活性維生素 D。
   - 若透析間體重增加多，詢問乾體重設定是否需微調。
5. 語氣專業、清晰、結構分明，無廢話。
"""


async def generate_clinic_memo(
    patient_nickname: str,
    recent_reports: list[dict[str, Any]],
    daily_record: dict[str, Any] | None = None,
    rules: list[dict[str, Any]] | None = None,
) -> ClinicMemoOut:
    """產生門診 30 秒就醫小抄。"""
    if not recent_reports:
        return ClinicMemoOut(
            summary_headline="門診備忘小抄",
            overview_text=f"目前尚無{patient_nickname}的檢驗資料，請先上傳檢驗單建立紀錄喔！",
            key_highlights=["暫無檢驗歷史數據"],
            doctor_questions=["1. 長輩目前透析狀況是否穩定？", "2. 下次檢驗抽血安排在何時？"],
            daily_reminders=["日常維持秤重習慣與水分控制。"],
        )

    # 組合 Prompt 內容
    lines = [f"長輩姓名/稱呼：{patient_nickname}", "\n【近幾次檢驗報告歷程（由新至舊）】"]
    for i, rep in enumerate(recent_reports[:3], 1):
        dt = rep.get("test_date") or f"第 {i} 期"
        sub_lines = [f"● 報告日期：{dt}"]
        for k in ["hemoglobin", "potassium", "phosphorus", "calcium", "albumin", "ipth", "kt_v", "creatinine", "bun"]:
            v = rep.get(k)
            if v is not None:
                m = METRICS.get(k)
                unit = m.unit if m else ""
                name = m.name if m else k
                code = m.code if m else k
                sub_lines.append(f"  - {name} ({code}): {v} {unit}")
        lines.append("\n".join(sub_lines))

    if daily_record:
        lines.append("\n【近期生活自主管理狀態】")
        if daily_record.get("weight_kg"):
            lines.append(f"- 今日體重: {daily_record.get('weight_kg')} kg")
        if daily_record.get("systolic") and daily_record.get("diastolic"):
            lines.append(f"- 今日血壓: {daily_record.get('systolic')}/{daily_record.get('diastolic')} mmHg")
        if daily_record.get("water_ml"):
            lines.append(f"- 喝水量: {daily_record.get('water_ml')} ml")

    prompt_content = "\n\n".join(lines)

    try:
        resp = await gemini().aio.models.generate_content(
            model=get_settings().gemini_model,
            contents=prompt_content,
            config=types.GenerateContentConfig(
                system_instruction=CLINIC_MEMO_SYSTEM,
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=ClinicMemoOut,
            ),
        )
        return ClinicMemoOut.model_validate_json(resp.text or "{}")
    except Exception as e:
        log.exception("門診小抄生成失敗，啟動備用邏輯: %s", e)
        # 本地規則組裝 fallback
        latest = recent_reports[0]
        prev = recent_reports[1] if len(recent_reports) > 1 else None

        hb_cur = latest.get("hemoglobin")
        hb_prev = prev.get("hemoglobin") if prev else None
        k_cur = latest.get("potassium")
        ipth_cur = latest.get("ipth")

        highlights = []
        if hb_cur is not None:
            hb_text = f"血紅素 (Hb)：{hb_cur} g/dL"
            if hb_prev is not None:
                hb_text = f"血紅素 (Hb)：{hb_prev} → {hb_cur} g/dL（近期穩健進步）"
            highlights.append(hb_text)
        if k_cur is not None:
            highlights.append(f"血鉀 (K)：{k_cur} mEq/L（目標 3.5~5.3）")
        if ipth_cur is not None:
            highlights.append(f"副甲狀腺素 (iPTH)：{ipth_cur} pg/mL（數值偏高，需注意骨骼血管）")

        questions = [
            f"1. {patient_nickname}近期血紅素維持在 {hb_cur or '標準'}，造血刺激素 (EPO) 劑量是否需微調或維持？",
            "2. 副甲狀腺素數值偏高，是否需要評估擬鈣劑或調整活性維生素 D 用法？",
            "3. 目前透析後乾體重評估是否恰當？日常水分控制建議？",
        ]

        return ClinicMemoOut(
            summary_headline=f"{patient_nickname} 門診 30 秒問診備忘小抄",
            overview_text=f"{patient_nickname}近期透析狀況整體平穩，造血表現良好，建議把握門診時間確認造血針劑量與副甲狀腺素控制策略。",
            key_highlights=highlights or ["數據已記錄於系統中"],
            doctor_questions=questions,
            daily_reminders=[
                "就診前請先測量當日體重與血壓紀錄。",
                "攜帶目前所有正在服用的藥物清單（尤其是磷結合劑與降壓藥）。",
                "提醒醫師注意近期的飲食胃口與精神狀態變化。",
            ],
        )

