"""Google Sheets 備份與同步服務。

提供雙向與備份功能：
1. 將確認後的檢驗報告寫入「檢驗報告」工作表
2. 將每日體重、血壓、喝水記錄寫入「每日紀錄」工作表
3. 若 Google Service Account 未配置或未設定 sheet_id，則自動跳過，不中斷主流程
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from app.config import get_settings
from app.metrics import CORE_METRICS, METRICS

log = logging.getLogger(__name__)

REPORT_HEADERS = [
    "檢驗日期",
    "鉀 (K)",
    "磷 (P)",
    "鈣 (Ca)",
    "血紅素 (Hb)",
    "鈉 (Na)",
    "白蛋白 (Alb)",
    "透析前BUN",
    "肌酸酐 (Cr)",
    "Kt/V",
    "副甲狀腺 (iPTH)",
    "資料來源",
    "確認時間",
]

DAILY_HEADERS = [
    "日期",
    "體重 (kg)",
    "收縮壓 (mmHg)",
    "舒張壓 (mmHg)",
    "脈搏 (bpm)",
    "喝水量 (ml)",
    "備註",
]


def _get_gspread_client() -> Any | None:
    """初始化 gspread client。"""
    s = get_settings()
    if not s.google_service_account_json:
        return None

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        info_raw = s.google_service_account_json.strip()
        if info_raw.startswith("{"):
            info = json.loads(info_raw)
            creds = Credentials.from_service_account_info(info, scopes=scopes)
        else:
            creds = Credentials.from_service_account_file(info_raw, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        log.warning("無法初始化 Google Sheets client: %s", e)
        return None


async def sync_report_to_sheet(sheet_id: str | None, report: dict[str, Any]) -> bool:
    """將已確認的報告同步至 Google Sheets。"""
    if not sheet_id:
        return False
    gc = _get_gspread_client()
    if not gc:
        return False

    try:
        sh = gc.open_by_key(sheet_id)
        # 尋找或建立「檢驗報告」工作表
        try:
            ws = sh.worksheet("檢驗報告")
        except Exception:
            ws = sh.add_worksheet(title="檢驗報告", rows=100, cols=len(REPORT_HEADERS))
            ws.append_row(REPORT_HEADERS)

        # 檢查是否已存在同日期記錄
        test_date = str(report.get("test_date", ""))
        existing_records = ws.get_all_values()
        date_col_idx = 0

        row_data = [
            test_date,
            report.get("potassium") or "",
            report.get("phosphorus") or "",
            report.get("calcium") or "",
            report.get("hemoglobin") or "",
            report.get("sodium") or "",
            report.get("albumin") or "",
            report.get("bun") or "",
            report.get("creatinine") or "",
            report.get("kt_v") or "",
            report.get("ipth") or "",
            report.get("source") or "ocr",
            report.get("confirmed_at") or "",
        ]

        found_row_idx = None
        for i, row in enumerate(existing_records[1:], start=2):
            if row and row[date_col_idx] == test_date:
                found_row_idx = i
                break

        if found_row_idx:
            ws.update(f"A{found_row_idx}:M{found_row_idx}", [row_data])
            log.info("更新 Google Sheets 檢驗報告第 %d 列", found_row_idx)
        else:
            ws.append_row(row_data)
            log.info("Google Sheets 新增檢驗報告一列")
        return True
    except Exception as e:
        log.error("同步報告至 Google Sheets 失敗: %s", e)
        return False


async def sync_daily_to_sheet(sheet_id: str | None, daily: dict[str, Any]) -> bool:
    """將日常紀錄同步至 Google Sheets。"""
    if not sheet_id:
        return False
    gc = _get_gspread_client()
    if not gc:
        return False

    try:
        sh = gc.open_by_key(sheet_id)
        try:
            ws = sh.worksheet("每日紀錄")
        except Exception:
            ws = sh.add_worksheet(title="每日紀錄", rows=200, cols=len(DAILY_HEADERS))
            ws.append_row(DAILY_HEADERS)

        rec_date = str(daily.get("record_date", ""))
        existing = ws.get_all_values()

        row_data = [
            rec_date,
            daily.get("weight_kg") or "",
            daily.get("systolic") or "",
            daily.get("diastolic") or "",
            daily.get("pulse") or "",
            daily.get("water_ml") or 0,
            daily.get("note") or "",
        ]

        found_idx = None
        for i, r in enumerate(existing[1:], start=2):
            if r and r[0] == rec_date:
                found_idx = i
                break

        if found_idx:
            ws.update(f"A{found_idx}:G{found_idx}", [row_data])
        else:
            ws.append_row(row_data)
        return True
    except Exception as e:
        log.error("同步每日紀錄至 Google Sheets 失敗: %s", e)
        return False
