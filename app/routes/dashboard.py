"""後台數據統整與檢驗分類儀表板 Web 路由。"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.db import db
from app.metrics import METRICS

router = APIRouter(tags=["dashboard"])


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>檢驗數據中心 ｜ 腎好伴 AI 照護後台</title>
  <meta name="description" content="血液透析檢驗報告後台資料統整與日期分類檢視。">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+TC:wght@400;500;700;900&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-primary: #0A0F1D;
      --bg-card: rgba(18, 24, 38, 0.7);
      --bg-card-hover: rgba(26, 34, 53, 0.85);
      --border-color: rgba(255, 255, 255, 0.08);
      --border-highlight: rgba(16, 185, 129, 0.3);
      --primary: #10B981;
      --primary-light: #34D399;
      --primary-glow: rgba(16, 185, 129, 0.15);
      --text-main: #F3F4F6;
      --text-muted: #9CA3AF;
      --text-dim: #6B7280;
      --danger: #EF4444;
      --warning: #F59E0B;
      --success: #10B981;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg-primary);
      background-image: 
        radial-gradient(at 0% 0%, rgba(16, 185, 129, 0.08) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(59, 130, 246, 0.06) 0px, transparent 50%);
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', 'Noto Sans TC', -apple-system, sans-serif;
      min-height: 100vh;
      line-height: 1.6;
      padding: 30px 20px 80px;
    }

    .container { max-width: 1100px; margin: 0 auto; }

    header {
      margin-bottom: 30px;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      flex-wrap: wrap;
      gap: 16px;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 24px;
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
      margin-bottom: 10px;
    }

    h1 { font-size: 2rem; font-weight: 800; letter-spacing: -0.02em; }
    .subtitle { color: var(--text-muted); font-size: 0.95rem; }

    .header-actions {
      display: flex;
      gap: 10px;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 0.88rem;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.2s;
      cursor: pointer;
    }
    .btn-primary {
      background: var(--primary);
      color: #052E16;
    }
    .btn-primary:hover { background: var(--primary-light); }
    .btn-secondary {
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-main);
      border: 1px solid var(--border-color);
    }
    .btn-secondary:hover { background: rgba(255, 255, 255, 0.1); }

    /* 統計概況卡片 */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 30px;
    }

    .stat-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 20px;
      backdrop-filter: blur(12px);
    }
    .stat-label { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 6px; }
    .stat-val { font-size: 1.8rem; font-weight: 800; color: #fff; }
    .stat-desc { font-size: 0.8rem; color: var(--text-dim); margin-top: 4px; }

    /* 分類區塊 */
    .month-section {
      margin-bottom: 32px;
    }

    .month-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
      padding-left: 4px;
    }

    .month-title {
      font-size: 1.25rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .report-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 20px 24px;
      margin-bottom: 16px;
      transition: transform 0.2s, border-color 0.2s;
      backdrop-filter: blur(12px);
    }
    .report-card:hover {
      border-color: rgba(255, 255, 255, 0.2);
    }

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

    .report-date {
      font-size: 1.1rem;
      font-weight: 700;
      color: #fff;
    }

    .status-tag {
      padding: 3px 10px;
      border-radius: 6px;
      font-size: 0.78rem;
      font-weight: 600;
    }
    .status-confirmed { background: rgba(16, 185, 129, 0.2); color: #34D399; }
    .status-draft { background: rgba(245, 158, 11, 0.2); color: #FBBF24; }

    /* 檢驗數值九宮格 */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
      gap: 12px;
    }

    .metric-pill {
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 8px;
      padding: 10px 14px;
    }
    .metric-name {
      font-size: 0.8rem;
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
    .metric-num {
      font-size: 1.25rem;
      font-weight: 700;
      font-feature-settings: "tnum";
    }
    .metric-unit {
      font-size: 0.75rem;
      color: var(--text-dim);
    }
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
        <div class="badge">📊 透析檢驗資料庫</div>
        <h1>檢驗數據中心</h1>
        <p class="subtitle">自動依檢驗日期統整、分類與異常指標分析</p>
      </div>
      <div class="header-actions">
        <a href="/changelog" class="btn btn-secondary">📜 版本更新</a>
        <button onclick="location.reload()" class="btn btn-primary">🔄 重新整理</button>
      </div>
    </header>

    <!-- 概況卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">累積已確認報告</div>
        <div class="stat-val" id="totalConfirmed">0</div>
        <div class="stat-desc">經 LINE 確認儲存的正式紀錄</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">最新檢驗日期</div>
        <div class="stat-val" id="latestDate" style="font-size: 1.4rem;">--</div>
        <div class="stat-desc">最近一次透析月檢</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">關聯家庭數</div>
        <div class="stat-val" id="totalFamilies">0</div>
        <div class="stat-desc">綁定的家庭照護個案</div>
      </div>
    </div>

    <!-- 依月份分組列表 -->
    <div id="timelineContainer">
      <!-- 動態載入 -->
    </div>
  </div>

  <script>
    const reports = window.__REPORTS_DATA__ || [];
    const families = window.__FAMILIES_DATA__ || [];

    function render() {
      const confirmed = reports.filter(r => r.status === 'confirmed');
      document.getElementById('totalConfirmed').innerText = confirmed.length;
      document.getElementById('totalFamilies').innerText = families.length;
      if (confirmed.length > 0) {
        document.getElementById('latestDate').innerText = confirmed[0].test_date;
      }

      const container = document.getElementById('timelineContainer');
      if (reports.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <h3>目前尚無檢驗紀錄</h3>
            <p style="margin-top: 8px;">在 LINE 官方帳號上傳報告照片並點選確認後，資料將自動分類顯示於此。</p>
          </div>
        `;
        return;
      }

      // 依 年-月 分組
      const groups = {};
      reports.forEach(r => {
        const monthKey = (r.test_date || '未知日期').substring(0, 7); // YYYY-MM
        if (!groups[monthKey]) groups[monthKey] = [];
        groups[monthKey].push(r);
      });

      let html = '';
      const metricDefs = {
        potassium: { name: '鉀 (K)', unit: 'mEq/L', low: 3.5, high: 5.5 },
        phosphorus: { name: '磷 (P)', unit: 'mg/dL', low: 3.5, high: 5.5 },
        calcium: { name: '鈣 (Ca)', unit: 'mg/dL', low: 8.4, high: 10.2 },
        hemoglobin: { name: '血紅素 (Hb)', unit: 'g/dL', low: 10.0, high: 11.5 },
        sodium: { name: '鈉 (Na)', unit: 'mEq/L', low: 135, high: 145 },
        albumin: { name: '白蛋白 (Alb)', unit: 'g/dL', low: 4.0, high: 99 },
        bun: { name: '尿素氮 (BUN)', unit: 'mg/dL', low: 0, high: 100 },
        creatinine: { name: '肌酸酐 (Cr)', unit: 'mg/dL', low: 0, high: 99 },
        kt_v: { name: '透析效率 (Kt/V)', unit: '', low: 1.2, high: 99 },
        ipth: { name: '副甲狀腺素 (iPTH)', unit: 'pg/mL', low: 150, high: 300 }
      };

      Object.keys(groups).sort().reverse().forEach(month => {
        const list = groups[month];
        html += `
          <div class="month-section">
            <div class="month-header">
              <div class="month-title">📅 ${month} (${list.length} 筆報告)</div>
            </div>
        `;

        list.forEach(r => {
          const fam = families.find(f => f.id === r.family_id);
          const famName = fam ? (fam.display_name || '照護家庭') : '個人家庭';

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
                  <span class="metric-unit">${def.unit}</span>
                </div>
                <div class="metric-value-row">
                  <span class="metric-num ${valClass}">${val !== null && val !== undefined ? val : '--'}</span>
                  <span style="font-size: 0.72rem; color: var(--text-dim);">${def.low === 0 ? '<' + def.high : def.low + '-' + def.high}</span>
                </div>
              </div>
            `;
          }

          html += `
            <div class="report-card">
              <div class="report-meta">
                <div>
                  <span class="report-date">📋 檢驗日期：${r.test_date}</span>
                  <span style="font-size: 0.85rem; color: var(--text-muted); margin-left: 10px;">對象：${famName}</span>
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

        html += '</div>';
      });

      container.innerHTML = html;
    }

    render();
  </script>
</body>
</html>
"""


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard() -> HTMLResponse:
    """後台數據統整與日期分類檢視頁面。"""
    c = await db()
    
    # 取得報告（最新日期排在最前）
    reports_res = await (
        c.table("medical_reports")
        .select("*")
        .order("test_date", desc=True)
        .execute()
    )
    reports = reports_res.data or []

    # 取得家庭資訊
    families_res = await c.table("families").select("id, display_name, line_group_id").execute()
    families = families_res.data or []

    # 注入 JSON 資料至 HTML
    safe_reports = json.dumps(reports, default=str)
    safe_families = json.dumps(families, default=str)

    html = DASHBOARD_HTML.replace(
        "window.__REPORTS_DATA__ || []",
        safe_reports
    ).replace(
        "window.__FAMILIES_DATA__ || []",
        safe_families
    )

    return HTMLResponse(content=html)


@router.get("/api/reports")
async def get_reports_api() -> dict[str, Any]:
    """取得資料庫所有報告統整（JSON 格式）。"""
    c = await db()
    reports = (await c.table("medical_reports").select("*").order("test_date", desc=True).execute()).data
    families = (await c.table("families").select("*").execute()).data
    return {
        "total": len(reports),
        "reports": reports,
        "families": families,
    }
