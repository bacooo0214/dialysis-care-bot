from app.services import charts

def test_charts_empty_guide():
    b = charts.render_metric_trend("kt_v", [], "長輩")
    assert isinstance(b, bytes)
    assert len(b) > 1000

def test_charts_single_trend():
    reports = [{"test_date": "2026-10-12", "potassium": 5.1}]
    b = charts.render_metric_trend("potassium", reports, "長輩")
    assert isinstance(b, bytes)
    assert len(b) > 1000

def test_charts_multi_trend():
    reports = [
        {"test_date": "2026-09-12", "potassium": 4.8},
        {"test_date": "2026-10-12", "potassium": 5.1},
    ]
    b = charts.render_metric_trend("potassium", reports, "長輩")
    assert isinstance(b, bytes)
    assert len(b) > 1000

def test_charts_summary_single():
    reports = [{"test_date": "2026-10-12", "potassium": 5.1, "phosphorus": 5.1}]
    b = charts.render_summary_dashboard(reports, "長輩")
    assert isinstance(b, bytes)
    assert len(b) > 1000

def test_charts_summary_multi():
    reports = [
        {"test_date": "2026-09-12", "potassium": 4.8, "phosphorus": 4.9},
        {"test_date": "2026-10-12", "potassium": 5.1, "phosphorus": 5.1},
    ]
    b = charts.render_summary_dashboard(reports, "長輩")
    assert isinstance(b, bytes)
    assert len(b) > 1000
