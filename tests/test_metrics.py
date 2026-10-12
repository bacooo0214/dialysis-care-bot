"""紅綠燈邏輯單元測試。"""

from app.metrics import (
    Level,
    classify_bp,
    classify_water,
    classify_weight_gain,
    evaluate_report,
    get_metrics,
)


def test_potassium_classification():
    defs = get_metrics()
    k = defs["potassium"]
    assert k.classify(4.5) == Level.GREEN
    assert k.classify(5.4) == Level.YELLOW
    assert k.classify(6.2) == Level.RED
    assert k.classify(2.8) == Level.RED
    assert k.direction(5.2) == "high"
    assert k.direction(3.2) == "low"
    assert k.direction(4.5) is None


def test_weight_gain_classification():
    # 乾體重 50kg
    # 增 1kg = 2% (綠)
    lv, pct = classify_weight_gain(51.0, 50.0)
    assert lv == Level.GREEN
    assert round(pct, 1) == 2.0

    # 增 2kg = 4% (黃)
    lv, pct = classify_weight_gain(52.0, 50.0)
    assert lv == Level.YELLOW
    assert round(pct, 1) == 4.0

    # 增 3kg = 6% (紅)
    lv, pct = classify_weight_gain(53.0, 50.0)
    assert lv == Level.RED
    assert round(pct, 1) == 6.0


def test_bp_classification():
    assert classify_bp(120, 75)[0] == Level.GREEN
    assert classify_bp(150, 85)[0] == Level.YELLOW
    assert classify_bp(185, 95)[0] == Level.RED
    assert classify_bp(85, 55)[0] == Level.RED


def test_water_classification():
    assert classify_water(700, 1000) == Level.GREEN
    assert classify_water(950, 1000) == Level.YELLOW
    assert classify_water(1200, 1000) == Level.RED


def test_evaluate_report_trend():
    curr = {"potassium": 5.2, "phosphorus": 4.5}
    prev = {"potassium": 4.8, "phosphorus": 5.0}
    results = evaluate_report(curr, prev)
    k_res = next(r for r in results if r.metric.key == "potassium")
    p_res = next(r for r in results if r.metric.key == "phosphorus")

    assert k_res.trend == "↑"
    assert p_res.trend == "↓"
