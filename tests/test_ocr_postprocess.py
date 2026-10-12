"""OCR 後處理與日期校正測試。"""

from datetime import date

from app.services.ocr import OcrReport, OcrResult, normalize_date, postprocess


def test_normalize_roc_date():
    today = date(2026, 10, 12)
    # 民國 115 年 9 月 15 日 -> 西元 2026-09-15
    d = normalize_date("115/09/15", today)
    assert d == date(2026, 9, 15)

    # 點號分隔
    d2 = normalize_date("115.10.01", today)
    assert d2 == date(2026, 10, 1)

    # 西元
    d3 = normalize_date("2026-08-20", today)
    assert d3 == date(2026, 8, 20)


def test_postprocess_unit_correction():
    raw_report = OcrReport(
        test_date="2026-10-01",
        potassium=4.8,
        phosphorus=5.0,
        calcium=9.2,
        hemoglobin=105.0,  # 誤用 g/L 單位
        sodium=138.0,
        albumin=38.0,      # 誤用 g/L 單位
        bun=65.0,
        creatinine=11.2,
        kt_v=1.45,
        ipth=250.0,
        uncertain_fields=[],
    )

    result = OcrResult(is_lab_report=True, reports=[raw_report], note=None)
    processed = postprocess(result, today=date(2026, 10, 12))

    assert len(processed.reports) == 1
    r = processed.reports[0]
    assert r.hemoglobin == 10.5  # 換算為 10.5 g/dL
    assert r.albumin == 3.8     # 換算為 3.8 g/dL
