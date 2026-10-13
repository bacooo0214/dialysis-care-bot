"""後台數據統整與互動式視覺化健康中心 Web 路由。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.db import db
from app.metrics import METRICS

router = APIRouter(tags=["dashboard"])


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>檢驗數據與趨勢中心 ｜ 腎好伴 AI 照護</title>
  <meta name="description" content="血液透析檢驗報告互動式趨勢走勢圖與 AI 智能數據統整中心。">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+TC:wght@400;500;700;900&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {
      --bg-primary: #0A0F1D;
      --bg-card: rgba(18, 24, 38, 0.75);
      --bg-card-hover: rgba(26, 34, 53, 0.9);
      --border-color: rgba(255, 255, 255, 0.08);
      --border-highlight: rgba(16, 185, 129, 0.3);
      --primary: #10B981;
      --primary-light: #34D399;
      --primary-glow: rgba(16, 185, 129, 0.15);
      --text-main: #F8FAFC;
      --text-muted: #94A3B8;
      --text-dim: #64748B;
      --danger: #EF4444;
      --warning: #F59E0B;
      --success: #10B981;
      --blue: #38BDF8;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg-primary);
      background-image: 
        radial-gradient(at 0% 0%, rgba(16, 185, 129, 0.1) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(56, 189, 248, 0.08) 0px, transparent 50%);
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', 'Noto Sans TC', -apple-system, sans-serif;
      min-height: 100vh;
      line-height: 1.6;
      padding: 24px 16px 80px;
    }

    .container { max-width: 1080px; margin: 0 auto; }

    /* 頂部 Header */
    header {
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      flex-wrap: wrap;
      gap: 16px;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 20px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      border-radius: 9999px;
      font-size: 0.8rem;
      font-weight: 600;
      background: var(--primary-glow);
      color: var(--primary-light);
      border: 1px solid var(--border-highlight);
      margin-bottom: 8px;
    }

    h1 { font-size: 1.85rem; font-weight: 800; letter-spacing: -0.02em; }
    .subtitle { color: var(--text-muted); font-size: 0.92rem; }

    .header-actions { display: flex; gap: 8px; align-items: center; }

    .btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.2s;
      cursor: pointer;
      border: none;
    }
    .btn-primary { background: var(--primary); color: #022C22; }
    .btn-primary:hover { background: var(--primary-light); }
    .btn-secondary {
      background: rgba(255, 255, 255, 0.06);
      color: var(--text-main);
      border: 1px solid var(--border-color);
    }
    .btn-secondary:hover { background: rgba(255, 255, 255, 0.12); }

    /* AI 智能統整診斷卡片 */
    .ai-summary-card {
      background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%);
      border: 1px solid rgba(56, 189, 248, 0.25);
      border-radius: 16px;
      padding: 22px 24px;
      margin-bottom: 28px;
      position: relative;
      overflow: hidden;
      box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    }
    .ai-summary-card::before {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0; height: 3px;
      background: linear-gradient(90deg, #10B981, #38BDF8, #818CF8);
    }
    .ai-title-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
    }
    .ai-tag {
      font-size: 0.8rem;
      font-weight: 700;
      padding: 3px 10px;
      border-radius: 6px;
      background: rgba(56, 189, 248, 0.15);
      color: #38BDF8;
      border: 1px solid rgba(56, 189, 248, 0.3);
    }
    .ai-content { font-size: 0.98rem; line-height: 1.7; color: #E2E8F0; }
    .ai-highlights {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
    }
    .hl-chip {
      font-size: 0.82rem;
      padding: 4px 10px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .hl-good { background: rgba(16, 185, 129, 0.15); color: #34D399; }
    .hl-warn { background: rgba(245, 158, 11, 0.15); color: #FBBF24; }
    .hl-danger { background: rgba(239, 68, 68, 0.15); color: #F87171; }

    /* 互動式折線圖區塊 */
    .chart-section {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 22px;
      margin-bottom: 30px;
      backdrop-filter: blur(12px);
    }
    .chart-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 18px;
    }
    .chart-tabs {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 4px;
      max-width: 100%;
    }
    .tab-btn {
      padding: 6px 14px;
      border-radius: 8px;
      font-size: 0.82rem;
      font-weight: 600;
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-muted);
      border: 1px solid var(--border-color);
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s;
    }
    .tab-btn.active {
      background: var(--blue);
      color: #042F2E;
      border-color: var(--blue);
      font-weight: 700;
    }
    .chart-canvas-wrapper {
      position: relative;
      height: 340px;
      width: 100%;
    }

    /* 歷次檢驗報告歷程 */
    .history-title {
      font-size: 1.3rem;
      font-weight: 700;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .report-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 20px;
      margin-bottom: 16px;
      transition: border-color 0.2s;
    }
    .report-card:hover { border-color: rgba(255, 255, 255, 0.2); }

    .report-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border-color);
    }
    .report-date { font-size: 1.15rem; font-weight: 700; color: #fff; }

    .status-tag {
      padding: 3px 10px;
      border-radius: 6px;
      font-size: 0.78rem;
      font-weight: 600;
    }
    .status-confirmed { background: rgba(16, 185, 129, 0.2); color: #34D399; }
    .status-draft { background: rgba(245, 158, 11, 0.2); color: #FBBF24; }

    /* 指標九宮格 */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
      gap: 10px;
    }
    .metric-pill {
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 8px;
      padding: 10px 12px;
    }
    .metric-name {
      font-size: 0.78rem;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
    }
    .metric-value-row {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      margin-top: 4px;
    }
    .metric-num { font-size: 1.25rem; font-weight: 700; }
    .val-normal { color: #10B981; }
    .val-warn { color: #F59E0B; }
    .val-danger { color: #EF4444; }
    .val-none { color: var(--text-dim); }

    .empty-state {
      text-align: center;
      padding: 60px 20px;
      color: var(--text-muted);
      background: var(--bg-card);
      border-radius: 12px;
      border: 1px dashed var(--border-color);
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <div class="badge">📊 血液透析檢驗視覺化中心</div>
        <h1 id="pageTitle">檢驗數據與趨勢總覽</h1>
        <p class="subtitle" id="pageSubtitle">長輩專屬線上健康儀表板 ｜ 隨時掌握數值動態</p>
      </div>
      <div class="header-actions">
        <a href="/changelog" class="btn btn-secondary">📜 版本紀錄</a>
        <button onclick="location.reload()" class="btn btn-primary">🔄 重新整理</button>
      </div>
    </header>

    <!-- 1. AI 智能統整診斷卡片 -->
    <div class="ai-summary-card" id="aiSummaryCard">
      <div class="ai-title-row">
        <span class="ai-tag">✨ AI 深度健康摘要與叮嚀</span>
        <span id="aiReportDate" style="font-size: 0.85rem; color: var(--text-muted);">最新報告：載入中...</span>
      </div>
      <div class="ai-content" id="aiSummaryText">
        正在統整長輩近期數值...
      </div>
      <div class="ai-highlights" id="aiHighlights">
        <!-- 動態標籤 -->
      </div>
    </div>

    <!-- 2. 互動式折線趨勢圖 -->
    <div class="chart-section">
      <div class="chart-header">
        <div>
          <h2 style="font-size: 1.15rem; font-weight: 700;">📈 歷史跨月趨勢走勢圖</h2>
          <p style="font-size: 0.82rem; color: var(--text-muted); margin-top: 2px;">
            綠色橫向色帶代表醫師建議的「安全目標區間」
          </p>
        </div>
        <div class="chart-tabs">
          <button class="tab-btn active" onclick="switchMetric('all')">四大指標</button>
          <button class="tab-btn" onclick="switchMetric('potassium')">血鉀 (K)</button>
          <button class="tab-btn" onclick="switchMetric('phosphorus')">血磷 (P)</button>
          <button class="tab-btn" onclick="switchMetric('hemoglobin')">血紅素 (Hb)</button>
          <button class="tab-btn" onclick="switchMetric('calcium')">鈣 (Ca)</button>
          <button class="tab-btn" onclick="switchMetric('albumin')">白蛋白 (Alb)</button>
        </div>
      </div>
      <div class="chart-canvas-wrapper">
        <canvas id="trendChart"></canvas>
      </div>
    </div>

    <!-- 3. 歷次檢驗報告清單 -->
    <h3 class="history-title">📋 歷次檢驗成績詳細歷程</h3>
    <div id="reportsListContainer">
      <!-- 動態載入 -->
    </div>
  </div>

  <script>
    const reports = window.__REPORTS_DATA__ || [];
    const families = window.__FAMILIES_DATA__ || [];
    const currentFamily = window.__CURRENT_FAMILY__ || (families[0] || null);

    const metricDefs = {
      potassium: { name: '鉀 (K)', unit: 'mEq/L', low: 3.5, high: 5.0, color: '#38BDF8' },
      phosphorus: { name: '磷 (P)', unit: 'mg/dL', low: 3.5, high: 5.5, color: '#FBBF24' },
      hemoglobin: { name: '血紅素 (Hb)', unit: 'g/dL', low: 10.0, high: 11.5, color: '#F87171' },
      calcium: { name: '鈣 (Ca)', unit: 'mg/dL', low: 8.4, high: 10.2, color: '#34D399' },
      albumin: { name: '白蛋白 (Alb)', unit: 'g/dL', low: 3.5, high: 99, color: '#A78BFA' },
      sodium: { name: '鈉 (Na)', unit: 'mEq/L', low: 135, high: 145, color: '#38BDF8' },
      creatinine: { name: '肌酸酐 (Cr)', unit: 'mg/dL', low: 0, high: 99, color: '#94A3B8' },
      kt_v: { name: '透析效率 (Kt/V)', unit: '', low: 1.2, high: 99, color: '#10B981' },
      ipth: { name: '副甲狀腺素 (iPTH)', unit: 'pg/mL', low: 150, high: 600, color: '#F472B6' }
    };

    let chartInstance = null;
    let currentTab = 'all';

    function init() {
      if (currentFamily && currentFamily.display_name) {
        document.getElementById('pageTitle').innerText = `${currentFamily.display_name} 檢驗中心`;
      }

      renderAISummary();
      renderReportsList();
      initChart('all');
    }

    // 1. AI 智能統整診斷
    function renderAISummary() {
      const confirmed = reports.filter(r => r.status === 'confirmed');
      if (confirmed.length === 0) {
        document.getElementById('aiSummaryText').innerText = "目前尚無已確認的報告紀錄。只要在 LINE 傳送檢驗單照片並點確認，AI 將自動為您深度統整分析！";
        return;
      }

      const latest = confirmed[0];
      document.getElementById('aiReportDate').innerText = `最新檢驗：${latest.test_date}`;

      const good = [];
      const warn = [];

      for (const [k, def] of Object.entries(metricDefs)) {
        const val = latest[k];
        if (val !== null && val !== undefined) {
          if (val < def.low) {
            warn.push({ name: def.name, val, reason: `偏低 (${val} < ${def.low})` });
          } else if (val > def.high) {
            warn.push({ name: def.name, val, reason: `偏高 (${val} > ${def.high})` });
          } else {
            good.push({ name: def.name, val });
          }
        }
      }

      let summaryHtml = `長輩在 <strong>${latest.test_date}</strong> 的檢驗中，整體狀態穩定！`;
      if (good.length > 0) {
        summaryHtml += ` 其中 <strong>${good.map(g => g.name).join('、')}</strong> 控制得相當理想，維持良好透析與生活節奏。`;
      }
      if (warn.length > 0) {
        summaryHtml += ` 目前需要微調的項目為：<strong>${warn.map(w => `${w.name} (${w.reason})`).join('、')}</strong>。建議在日常料理時注意青菜汆燙去鉀、遵醫囑按時搭配降磷劑與造血輔助喔！`;
      } else {
        summaryHtml += ` 所有核心檢驗指標皆在標準範圍內，非常優秀，請繼續保持！`;
      }

      document.getElementById('aiSummaryText').innerHTML = summaryHtml;

      const hlContainer = document.getElementById('aiHighlights');
      let hlHtml = '';
      good.forEach(g => {
        hlHtml += `<span class="hl-chip hl-good">🟢 ${g.name} ${g.val} 正常</span>`;
      });
      warn.forEach(w => {
        hlHtml += `<span class="hl-chip hl-warn">⚠️ ${w.name} ${w.val} ${w.reason}</span>`;
      });
      hlContainer.innerHTML = hlHtml;
    }

    // 2. 互動式 Chart.js
    function switchMetric(key) {
      currentTab = key;
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      event.target.classList.add('active');
      initChart(key);
    }

    function initChart(key) {
      const confirmed = reports.filter(r => r.status === 'confirmed').slice().reverse(); // 舊到新
      const ctx = document.getElementById('trendChart').getContext('2d');

      if (chartInstance) {
        chartInstance.destroy();
      }

      const labels = confirmed.map(r => r.test_date || '未知');

      let datasets = [];

      if (key === 'all') {
        const keysToShow = ['potassium', 'phosphorus', 'hemoglobin', 'calcium'];
        keysToShow.forEach(k => {
          const def = metricDefs[k];
          datasets.push({
            label: `${def.name} (${def.unit})`,
            data: confirmed.map(r => r[k]),
            borderColor: def.color,
            backgroundColor: def.color + '22',
            tension: 0.35,
            fill: false,
            borderWidth: 3,
            pointRadius: 6,
            pointHoverRadius: 9,
            pointBackgroundColor: def.color,
            pointBorderColor: '#FFFFFF',
            pointBorderWidth: 2
          });
        });
      } else {
        const def = metricDefs[key];
        datasets.push({
          label: `${def.name} (${def.unit})`,
          data: confirmed.map(r => r[key]),
          borderColor: def.color,
          backgroundColor: def.color + '22',
          tension: 0.35,
          fill: true,
          borderWidth: 3.5,
          pointRadius: 7,
          pointHoverRadius: 10,
          pointBackgroundColor: def.color,
          pointBorderColor: '#FFFFFF',
          pointBorderWidth: 2
        });
      }

      chartInstance = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: {
              labels: { color: '#E2E8F0', font: { family: 'Noto Sans TC', size: 12, weight: 600 } }
            },
            tooltip: {
              backgroundColor: '#0F172A',
              titleColor: '#38BDF8',
              bodyColor: '#F8FAFC',
              borderColor: '#334155',
              borderWidth: 1,
              padding: 12,
              boxPadding: 6,
              usePointStyle: true
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { color: '#94A3B8', font: { family: 'Noto Sans TC', size: 11, weight: 600 } }
            },
            y: {
              grid: { color: 'rgba(255, 255, 255, 0.06)' },
              ticks: { color: '#94A3B8', font: { family: 'Noto Sans TC', size: 11 } }
            }
          }
        }
      });
    }

    // 3. 歷次報告清單
    function renderReportsList() {
      const container = document.getElementById('reportsListContainer');
      if (reports.length === 0) {
        container.innerHTML = `<div class="empty-state"><h3>目前尚無檢驗紀錄</h3><p style="margin-top: 8px;">在 LINE 官方帳號上傳報告照片並確認後，資料將自動分類顯示於此。</p></div>`;
        return;
      }

      let html = '';
      reports.forEach(r => {
        let metricsHtml = '';
        for (const [key, def] of Object.entries(metricDefs)) {
          const val = r[key];
          let valClass = 'val-normal';
          if (val === null || val === undefined) {
            valClass = 'val-none';
          } else if (val < def.low) {
            valClass = 'val-warn';
          } else if (val > def.high) {
            valClass = 'val-danger';
          }

          metricsHtml += `
            <div class="metric-pill">
              <div class="metric-name">
                <span>${def.name}</span>
                <span style="font-size: 0.7rem; color: var(--text-dim);">${def.unit}</span>
              </div>
              <div class="metric-value-row">
                <span class="metric-num ${valClass}">${val !== null && val !== undefined ? val : '--'}</span>
                <span style="font-size: 0.7rem; color: var(--text-dim);">${def.low === 0 ? '<' + def.high : def.low + '-' + def.high}</span>
              </div>
            </div>
          `;
        }

        html += `
          <div class="report-card">
            <div class="report-meta">
              <div>
                <span class="report-date">📋 檢驗日期：${r.test_date}</span>
                <span style="font-size: 0.85rem; color: var(--text-muted); margin-left: 10px;">
                  對象：${currentFamily ? currentFamily.display_name : '長輩'}
                </span>
              </div>
              <div>
                <span class="status-tag ${r.status === 'confirmed' ? 'status-confirmed' : 'status-draft'}">
                  ${r.status === 'confirmed' ? '✅ 已確認生效' : '⏳ 待確認草稿'}
                </span>
                <span style="font-size: 0.75rem; color: var(--text-dim); margin-left: 8px;">來源：${r.source || 'LINE OCR'}</span>
              </div>
            </div>
            <div class="metrics-grid">
              ${metricsHtml}
            </div>
          </div>
        `;
      });

      container.innerHTML = html;
    }

    init();
  </script>
</body>
</html>
"""


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(family_id: str | None = Query(None)) -> HTMLResponse:
    """後台數據統整與互動式趨勢走勢圖 Web 中心。"""
    c = await db()

    # 取得所有家庭
    families_res = await c.table("families").select("id, display_name, line_group_id").execute()
    families = families_res.data or []

    # 決定當前家庭
    target_family = None
    if family_id:
        target_family = next((f for f in families if f["id"] == family_id), None)
    if not target_family and families:
        target_family = families[0]

    # 取得該家庭的報告（最新日期排在最前）
    query = c.table("medical_reports").select("*").order("test_date", desc=True)
    if target_family:
        query = query.eq("family_id", target_family["id"])
    reports_res = await query.execute()
    reports = reports_res.data or []

    # 注入 JSON 資料至 HTML
    safe_reports = json.dumps(reports, default=str)
    safe_families = json.dumps(families, default=str)
    safe_current_family = json.dumps(target_family, default=str)

    html = (
        DASHBOARD_HTML.replace("window.__REPORTS_DATA__ || []", safe_reports)
        .replace("window.__FAMILIES_DATA__ || []", safe_families)
        .replace("window.__CURRENT_FAMILY__ || null", safe_current_family)
    )

    return HTMLResponse(content=html)
