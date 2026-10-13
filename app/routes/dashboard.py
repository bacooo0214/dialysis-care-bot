"""後台數據統整與互動式視覺化健康中心 Web 路由。

文學文青質感 (Literary & Warm Paper Aesthetic) + 長輩護眼大字版 (Senior-Friendly UI/UX)。
支援主分頁導航（總覽手札 vs 歷次檢驗詳實歷程）、月份篩選與折疊卡片，解決頁面過長問題。
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.db import db
from app.metrics import METRICS

router = APIRouter(tags=["dashboard"])


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>長輩照護手札 ｜ 腎好伴 檢驗數據與走勢中心</title>
  <meta name="description" content="溫潤素雅的人文健康手札，提供血液透析檢驗數據可視化、互動走勢圖與 AI 智能照護統整。">
  <!-- 字型：思源宋體（標題典雅）與思源黑體（易讀清朗） -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700;900&family=Noto+Serif+TC:wght@500;600;700;900&display=swap" rel="stylesheet">
  <!-- Chart.js 與 LINE LIFF SDK -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script charset="utf-8" src="https://static.line-scdn.net/liff/edge/2/sdk.js"></script>
  <style>
    /* ========================================================
       文青紙本書札色彩體系 (Literary & Warm Paper Palette)
       ======================================================== */
    :root {
      --bg-paper: #FBF9F5;          /* 暖宣紙底色，溫潤不刺眼 */
      --bg-subtle: #F3ECE4;         /* 淺焙茶米色 */
      --card-bg: #FFFFFF;           /* 純淨暖白手札卡片 */
      --card-border: #E6DFD3;       /* 淺焙茶色纖細邊框 */
      --text-ink: #2C302E;          /* 松煙墨黑，柔和高對比 */
      --text-muted: #5F6A64;        /* 青苔灰，說明文字 */
      --text-dim: #8E9892;          /* 輕墨灰，次要刻度 */
      
      /* 文人雅致狀態色彩 */
      --c-bamboo: #245A44;          /* 竹青/松柏綠（正常安好） */
      --c-bamboo-bg: #EDF5F0;       /* 柔和淺竹青底色 */
      --c-amber: #B85D19;           /* 沉著琥珀（稍加注意） */
      --c-amber-bg: #FDF5ED;        /* 柔和淺琥珀底色 */
      --c-cinnabar: #A32A2A;        /* 朱砂/赭紅（偏高警戒） */
      --c-cinnabar-bg: #FDF0F0;     /* 柔和淺赭底色 */
      --c-indigo: #2D5873;          /* 靛藍/霽藍（走勢折線） */
      --c-indigo-bg: #EEF4F8;
      
      /* 陰影與圓角 */
      --shadow-paper: 0 4px 18px -2px rgba(50, 40, 30, 0.05), 0 1px 3px rgba(0, 0, 0, 0.02);
      --radius-card: 16px;
      --radius-sm: 8px;

      /* 標準排版尺寸 */
      --font-scale: 1rem;
      --val-font-size: 1.85rem;
      --title-font-size: 1.65rem;
      --line-height-body: 1.68;
    }

    /* ========================================================
       長輩護眼大字版 (Senior-Friendly Accessibility Mode)
       ======================================================== */
    body.senior-mode {
      --font-scale: 1.18rem;
      --val-font-size: 2.35rem;
      --title-font-size: 2.05rem;
      --line-height-body: 1.85;
      letter-spacing: 0.02em;
    }
    body.senior-mode .main-tab-btn {
      padding: 12px 24px;
      font-size: 1.15rem;
    }
    body.senior-mode .metric-pill {
      padding: 16px 14px;
    }
    body.senior-mode .tab-btn {
      padding: 10px 18px;
      font-size: 1rem;
    }
    body.senior-mode .btn {
      padding: 12px 20px;
      font-size: 1.05rem;
    }
    body.senior-mode .folder-header {
      padding: 20px 22px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg-paper);
      background-image: 
        radial-gradient(at 0% 0%, rgba(36, 90, 68, 0.03) 0px, transparent 60%),
        radial-gradient(at 100% 100%, rgba(184, 93, 25, 0.03) 0px, transparent 60%);
      color: var(--text-ink);
      font-family: 'Noto Sans TC', -apple-system, sans-serif;
      min-height: 100vh;
      line-height: var(--line-height-body);
      font-size: var(--font-scale);
      padding: 20px 16px 90px;
      transition: font-size 0.25s, line-height 0.25s;
    }

    .container { max-width: 960px; margin: 0 auto; }

    /* ========================================================
       頂部：人文典雅 Header 與功能列
       ======================================================== */
    header {
      margin-bottom: 20px;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      flex-wrap: wrap;
      gap: 14px;
      padding-bottom: 16px;
      border-bottom: 1px dashed var(--card-border);
    }

    .header-sub {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--c-bamboo);
      font-size: 0.88rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      margin-bottom: 6px;
    }

    h1 {
      font-family: 'Noto Serif TC', serif;
      font-size: var(--title-font-size);
      font-weight: 700;
      color: var(--text-ink);
      letter-spacing: -0.01em;
    }

    .subtitle {
      color: var(--text-muted);
      font-size: 0.94rem;
      margin-top: 4px;
    }

    .header-actions {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }

    /* 長輩模式切換開關 */
    .mode-switch-btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      border-radius: 9999px;
      background: #FFFFFF;
      border: 1.5px solid var(--c-bamboo);
      color: var(--c-bamboo);
      font-weight: 700;
      font-size: 0.88rem;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
      transition: all 0.2s ease;
    }
    .mode-switch-btn:hover {
      background: var(--c-bamboo-bg);
    }
    body.senior-mode .mode-switch-btn {
      background: var(--c-bamboo);
      color: #FFFFFF;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 14px;
      border-radius: 8px;
      font-size: 0.86rem;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.2s;
      cursor: pointer;
      border: 1px solid var(--card-border);
      background: #FFFFFF;
      color: var(--text-ink);
    }
    .btn:hover { background: var(--bg-subtle); }

    /* ========================================================
       頂級主標籤頁導航 (Main Tabs Navigation)
       ======================================================== */
    .main-nav-bar {
      display: flex;
      gap: 10px;
      background: var(--bg-subtle);
      padding: 6px;
      border-radius: 12px;
      margin-bottom: 24px;
      border: 1px solid var(--card-border);
    }
    .main-tab-btn {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 10px 18px;
      border-radius: 8px;
      font-size: 1rem;
      font-weight: 700;
      color: var(--text-muted);
      background: transparent;
      border: none;
      cursor: pointer;
      transition: all 0.22s ease;
      font-family: 'Noto Sans TC', sans-serif;
    }
    .main-tab-btn:hover {
      color: var(--text-ink);
    }
    .main-tab-btn.active {
      background: #FFFFFF;
      color: var(--c-bamboo);
      box-shadow: 0 2px 8px rgba(44, 48, 46, 0.06);
    }
    .tab-badge {
      display: inline-block;
      font-size: 0.78rem;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--c-bamboo-bg);
      color: var(--c-bamboo);
      border: 1px solid rgba(36, 90, 68, 0.2);
    }
    .main-tab-btn.active .tab-badge {
      background: var(--c-bamboo);
      color: #FFFFFF;
    }

    /* 視圖切換容器 */
    .view-panel {
      display: none;
    }
    .view-panel.active {
      display: block;
      animation: fadeIn 0.25s ease-out;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* ========================================================
       1. AI 智能長輩月候箋（溫暖如家書）
       ======================================================== */
    .letter-card {
      background: #FFFFFF;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-card);
      padding: 24px 26px;
      margin-bottom: 24px;
      box-shadow: var(--shadow-paper);
      position: relative;
    }
    .letter-card::before {
      content: "";
      position: absolute;
      top: 0; left: 24px; right: 24px; height: 3px;
      background: linear-gradient(90deg, var(--c-bamboo) 0%, #4E876A 50%, var(--c-amber) 100%);
      border-radius: 3px 3px 0 0;
    }
    .letter-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      flex-wrap: wrap;
      gap: 8px;
    }
    .letter-seal {
      font-family: 'Noto Serif TC', serif;
      font-weight: 700;
      font-size: 0.92rem;
      color: var(--c-bamboo);
      background: var(--c-bamboo-bg);
      border: 1px solid rgba(36, 90, 68, 0.25);
      padding: 4px 12px;
      border-radius: 6px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .letter-date {
      font-size: 0.88rem;
      color: var(--text-dim);
    }
    .letter-content {
      font-size: 1.02rem;
      color: var(--text-ink);
      line-height: var(--line-height-body);
    }
    .letter-content strong {
      color: var(--c-bamboo);
    }
    .letter-tags {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 18px;
      padding-top: 16px;
      border-top: 1px dashed var(--card-border);
    }
    .tag-chip {
      font-size: 0.86rem;
      font-weight: 600;
      padding: 5px 12px;
      border-radius: 6px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .tag-bamboo { background: var(--c-bamboo-bg); color: var(--c-bamboo); border: 1px solid rgba(36, 90, 68, 0.2); }
    .tag-amber { background: var(--c-amber-bg); color: var(--c-amber); border: 1px solid rgba(184, 93, 25, 0.2); }
    .tag-cinnabar { background: var(--c-cinnabar-bg); color: var(--c-cinnabar); border: 1px solid rgba(163, 42, 42, 0.2); }

    /* ========================================================
       最新一期核心快覽卡片
       ======================================================== */
    .quick-shelf-box {
      background: #FFFFFF;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-card);
      padding: 20px 22px;
      margin-bottom: 24px;
      box-shadow: var(--shadow-paper);
    }
    .quick-shelf-title {
      font-family: 'Noto Serif TC', serif;
      font-size: 1.12rem;
      font-weight: 700;
      margin-bottom: 14px;
      color: var(--text-ink);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    /* ========================================================
       2. 互動式跨月走勢折線圖（文人山水藍調）
       ======================================================== */
    .chart-box {
      background: #FFFFFF;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-card);
      padding: 24px 22px;
      margin-bottom: 28px;
      box-shadow: var(--shadow-paper);
    }
    .chart-top-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 14px;
      margin-bottom: 20px;
    }
    .chart-heading h2 {
      font-family: 'Noto Serif TC', serif;
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--text-ink);
    }
    .chart-heading p {
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-top: 2px;
    }

    /* 書籤風籤頁切換 */
    .chart-tabs {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 4px;
      max-width: 100%;
    }
    .tab-btn {
      padding: 7px 14px;
      border-radius: 8px;
      font-size: 0.86rem;
      font-weight: 600;
      background: var(--bg-subtle);
      color: var(--text-muted);
      border: 1px solid transparent;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s ease;
    }
    .tab-btn:hover {
      background: #ECE6DE;
      color: var(--text-ink);
    }
    .tab-btn.active {
      background: var(--c-indigo);
      color: #FFFFFF;
      border-color: var(--c-indigo);
      font-weight: 700;
      box-shadow: 0 2px 6px rgba(45, 88, 115, 0.2);
    }
    .chart-area-wrap {
      position: relative;
      height: 330px;
      width: 100%;
    }
    body.senior-mode .chart-area-wrap {
      height: 400px;
    }

    /* ========================================================
       3. 獨立分頁：歷次檢驗成績詳實歷程 (Tab 2)
       ======================================================== */
    .history-controls {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 20px;
      background: #FFFFFF;
      padding: 14px 18px;
      border-radius: 12px;
      border: 1px solid var(--card-border);
      box-shadow: var(--shadow-paper);
    }
    .history-filter-pills {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }
    .history-pill {
      padding: 6px 14px;
      border-radius: 999px;
      font-size: 0.86rem;
      font-weight: 600;
      cursor: pointer;
      background: var(--bg-subtle);
      color: var(--text-muted);
      border: 1px solid transparent;
      transition: all 0.2s ease;
    }
    .history-pill:hover {
      background: #ECE4DA;
      color: var(--text-ink);
    }
    .history-pill.active {
      background: var(--c-bamboo);
      color: #FFFFFF;
      border-color: var(--c-bamboo);
    }

    /* 歷史月檢手帖折疊卡片 (Folder Accordion) */
    .folder-card {
      background: #FFFFFF;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-card);
      margin-bottom: 16px;
      box-shadow: var(--shadow-paper);
      overflow: hidden;
      transition: all 0.2s ease;
    }
    .folder-card:hover {
      border-color: #D4CBBC;
    }
    .folder-header {
      padding: 16px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
      background: #FFFFFF;
      user-select: none;
      transition: background-color 0.15s;
    }
    .folder-header:hover {
      background: #FAF8F5;
    }
    .folder-title-wrap {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .folder-date {
      font-family: 'Noto Serif TC', serif;
      font-size: 1.15rem;
      font-weight: 700;
      color: var(--text-ink);
    }
    .folder-summary-tags {
      display: flex;
      gap: 6px;
      font-size: 0.8rem;
    }
    .folder-toggle-icon {
      font-size: 0.95rem;
      color: var(--text-dim);
      transition: transform 0.2s ease;
    }
    .folder-card.open .folder-toggle-icon {
      transform: rotate(180deg);
    }
    .folder-body {
      display: none;
      padding: 0 20px 20px 20px;
      border-top: 1px dashed var(--card-border);
      background: #FAF8F5;
    }
    .folder-card.open .folder-body {
      display: block;
      padding-top: 18px;
    }

    /* 橫向歷史指標速查總表 (Matrix Table) */
    .matrix-box {
      background: #FFFFFF;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-card);
      padding: 20px;
      margin-bottom: 24px;
      box-shadow: var(--shadow-paper);
      overflow-x: auto;
    }
    .matrix-title {
      font-family: 'Noto Serif TC', serif;
      font-size: 1.15rem;
      font-weight: 700;
      margin-bottom: 12px;
      color: var(--text-ink);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .matrix-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
      text-align: center;
      min-width: 600px;
    }
    .matrix-table th, .matrix-table td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--card-border);
    }
    .matrix-table th {
      background: var(--bg-subtle);
      color: var(--text-ink);
      font-weight: 700;
      font-family: 'Noto Serif TC', serif;
    }
    .matrix-table th:first-child, .matrix-table td:first-child {
      text-align: left;
      font-weight: 600;
    }
    .matrix-table tr:hover {
      background: #FDFBF8;
    }

    /* 雅緻指標格子 */
    .metrics-shelf {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
      gap: 12px;
    }
    body.senior-mode .metrics-shelf {
      grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
      gap: 16px;
    }

    .metric-pill {
      background: #FFFFFF;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-sm);
      padding: 12px 14px;
      transition: transform 0.15s;
    }
    .metric-pill:hover {
      transform: translateY(-1px);
    }

    .pill-header {
      font-size: 0.82rem;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-weight: 600;
    }
    .pill-row {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      margin-top: 6px;
    }
    .pill-num {
      font-size: var(--val-font-size);
      font-weight: 800;
      font-feature-settings: "tnum";
    }
    .pill-unit {
      font-size: 0.76rem;
      color: var(--text-dim);
      margin-left: 4px;
    }
    .pill-target {
      font-size: 0.78rem;
      color: var(--text-dim);
      margin-top: 4px;
    }

    .v-bamboo { color: var(--c-bamboo); }
    .v-amber { color: var(--c-amber); }
    .v-cinnabar { color: var(--c-cinnabar); }
    .v-none { color: var(--text-dim); }

    .stamp-badge {
      font-size: 0.82rem;
      font-weight: 700;
      padding: 3px 9px;
      border-radius: 6px;
      border: 1px solid currentColor;
    }
    .stamp-good { color: var(--c-bamboo); background: var(--c-bamboo-bg); }
    .stamp-draft { color: var(--c-amber); background: var(--c-amber-bg); }

    /* 空狀態 */
    .empty-card {
      text-align: center;
      padding: 50px 20px;
      color: var(--text-muted);
      background: #FFFFFF;
      border-radius: var(--radius-card);
      border: 1px dashed var(--card-border);
      box-shadow: var(--shadow-paper);
    }
    .empty-card h3 {
      font-family: 'Noto Serif TC', serif;
      color: var(--text-ink);
      margin-bottom: 8px;
    }

    /* 底部返回 LINE 提示 */
    .liff-footer {
      text-align: center;
      margin-top: 40px;
      color: var(--text-dim);
      font-size: 0.86rem;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <div class="header-sub">🌿 腎好伴 · 家庭照護健康箋</div>
        <h1 id="pageTitle">長輩健康與檢驗走勢</h1>
        <p class="subtitle" id="pageSubtitle">為長輩與家人量身訂製的溫潤健康存摺</p>
      </div>
      <div class="header-actions">
        <!-- 核心功能：一鍵切換長輩護眼大字版 -->
        <button class="mode-switch-btn" id="modeSwitchBtn" onclick="toggleSeniorMode()">
          👓 長輩大字版
        </button>
        <button onclick="location.reload()" class="btn">🔄 重新整理</button>
        <button id="liffCloseBtn" onclick="closeInApp()" class="btn" style="display: none;">✕ 關閉</button>
      </div>
    </header>

    <!-- 頂級主標籤導航欄 (主視圖切換) -->
    <nav class="main-nav-bar" role="tablist">
      <button class="main-tab-btn active" id="tabNavOverview" onclick="switchMainTab('overview')" role="tab">
        🍂 照護手札與走勢
      </button>
      <button class="main-tab-btn" id="tabNavHistory" onclick="switchMainTab('history')" role="tab">
        📋 歷次檢驗詳實歷程 <span class="tab-badge" id="reportCountBadge">0</span>
      </button>
    </nav>

    <!-- ==========================================
         視圖 1：【照護手札與走勢】 (Overview Tab)
         ========================================== -->
    <main id="viewOverview" class="view-panel active">
      <!-- 1. AI 智能長輩月候箋 -->
      <div class="letter-card" id="aiLetterCard">
        <div class="letter-header">
          <span class="letter-seal">📜 照護手札 · 智能月箋</span>
          <span class="letter-date" id="letterDate">最新紀錄：等待建立</span>
        </div>
        <div class="letter-content" id="letterContent">
          正在準備長輩的健康月箋...
        </div>
        <div class="letter-tags" id="letterTags">
          <!-- 標籤區 -->
        </div>
      </div>

      <!-- 2. 最新一期核心數值快覽 -->
      <div class="quick-shelf-box" id="latestQuickBox" style="display: none;">
        <div class="quick-shelf-title">
          <span>🌿 最近一期檢驗核心快報</span>
          <span id="quickReportDate" style="font-size: 0.88rem; color: var(--text-muted); font-family: 'Noto Sans TC';"></span>
        </div>
        <div class="metrics-shelf" id="quickShelfGrid">
          <!-- 動態載入最新一期指標 -->
        </div>
      </div>

      <!-- 3. 互動式跨月走勢折線圖 -->
      <div class="chart-box">
        <div class="chart-top-bar">
          <div class="chart-heading">
            <h2>📈 歷史跨月指標走勢</h2>
            <p>綠色柔和區間代表醫師建議的「安全目標範圍」</p>
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
        <div class="chart-area-wrap">
          <canvas id="trendChart"></canvas>
        </div>
      </div>
    </main>

    <!-- ==========================================
         視圖 2：【歷次檢驗詳實歷程】 (History Tab)
         ========================================== -->
    <main id="viewHistory" class="view-panel">
      <!-- 篩選列與期數書籤 -->
      <div class="history-controls" id="historyControls" style="display: none;">
        <div class="history-filter-pills" id="historyFilterPills">
          <!-- 動態生成月份書籤按鈕 -->
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn" onclick="toggleAllFolders(true)">展開全部</button>
          <button class="btn" onclick="toggleAllFolders(false)">收合全部</button>
        </div>
      </div>

      <!-- 跨月對比橫向速查表 -->
      <div class="matrix-box" id="historyMatrixBox" style="display: none;">
        <div class="matrix-title">
          <span>📊 跨月核心數值橫向速查</span>
          <span style="font-size: 0.82rem; color: var(--text-muted); font-weight: normal;">向右滑動可查閱更多月份</span>
        </div>
        <table class="matrix-table" id="matrixTable">
          <!-- 動態生成跨月對照表格 -->
        </table>
      </div>

      <!-- 手風琴式月份折疊卡片清單（杜絕頁面過長） -->
      <div id="reportsListContainer">
        <!-- 動態載入報告 -->
      </div>
    </main>

    <div class="liff-footer">
      <p>— 陪伴長輩平穩透析，願一家人日日安好 —</p>
    </div>
  </div>

  <script>
    const reports = window.__REPORTS_DATA__ || [];
    const families = window.__FAMILIES_DATA__ || [];
    const currentFamily = window.__CURRENT_FAMILY__ || (families[0] || null);

    // 指標定義與醫學目標
    const metricDefs = {
      potassium: { name: '鉀 (K)', unit: 'mEq/L', low: 3.5, high: 5.0, color: '#245A44' },
      phosphorus: { name: '磷 (P)', unit: 'mg/dL', low: 3.5, high: 5.5, color: '#B85D19' },
      hemoglobin: { name: '血紅素 (Hb)', unit: 'g/dL', low: 10.0, high: 11.5, color: '#A32A2A' },
      calcium: { name: '鈣 (Ca)', unit: 'mg/dL', low: 8.4, high: 10.2, color: '#2D5873' },
      albumin: { name: '白蛋白 (Alb)', unit: 'g/dL', low: 3.5, high: 99, color: '#6A5ACD' },
      sodium: { name: '鈉 (Na)', unit: 'mEq/L', low: 135, high: 145, color: '#319795' },
      creatinine: { name: '肌酸酐 (Cr)', unit: 'mg/dL', low: 0, high: 99, color: '#64748B' },
      kt_v: { name: '透析效率 (Kt/V)', unit: '', low: 1.2, high: 99, color: '#245A44' },
      ipth: { name: '副甲狀腺素 (iPTH)', unit: 'pg/mL', low: 150, high: 600, color: '#D97706' }
    };

    let chartInstance = null;
    let currentTab = 'all';
    let selectedMonthFilter = 'all';

    // 1. 主視圖標籤頁切換
    function switchMainTab(tabName) {
      document.querySelectorAll('.main-tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));

      if (tabName === 'overview') {
        document.getElementById('tabNavOverview').classList.add('active');
        document.getElementById('viewOverview').classList.add('active');
        if (chartInstance) {
          chartInstance.resize();
        }
      } else {
        document.getElementById('tabNavHistory').classList.add('active');
        document.getElementById('viewHistory').classList.add('active');
      }
    }

    // 2. 長輩大字模式切換
    function initSeniorMode() {
      const saved = localStorage.getItem('dialysis_font_mode');
      if (saved === 'senior') {
        document.body.classList.add('senior-mode');
        document.getElementById('modeSwitchBtn').innerText = '🌿 文青雅緻版';
      }
    }

    function toggleSeniorMode() {
      const isSenior = document.body.classList.toggle('senior-mode');
      const btn = document.getElementById('modeSwitchBtn');
      if (isSenior) {
        btn.innerText = '🌿 文青雅緻版';
        localStorage.setItem('dialysis_font_mode', 'senior');
      } else {
        btn.innerText = '👓 長輩大字版';
        localStorage.setItem('dialysis_font_mode', 'standard');
      }
      if (chartInstance) {
        initChart(currentTab);
      }
    }

    // 3. LINE In-App 瀏覽器 / LIFF 支援
    function initLiff() {
      if (typeof liff !== 'undefined') {
        const liffId = window.__LIFF_ID__;
        if (liffId) {
          liff.init({ liffId: liffId }).then(() => {
            if (liff.isInClient()) {
              document.getElementById('liffCloseBtn').style.display = 'inline-flex';
            }
          }).catch(console.error);
        } else if (liff.isInClient && liff.isInClient()) {
          document.getElementById('liffCloseBtn').style.display = 'inline-flex';
        }
      }
    }

    function closeInApp() {
      if (typeof liff !== 'undefined' && liff.closeWindow) {
        liff.closeWindow();
      } else {
        window.close();
      }
    }

    // 4. AI 智能統整長輩月箋
    function renderAISummary() {
      const confirmed = reports.filter(r => r.status === 'confirmed');
      const nickname = currentFamily ? (currentFamily.display_name || '長輩') : '長輩';

      if (confirmed.length === 0) {
        document.getElementById('letterDate').innerText = '狀態：資料庫已重置清空';
        document.getElementById('letterContent').innerHTML = `
          ${nickname}您好，目前的歷史檢驗數據已全數乾淨清空。<br>
          請由您提供各月份的完整檢驗資料，我們將為長輩進行專業的透析指標深度分析與建立健康存摺！
        `;
        document.getElementById('letterTags').innerHTML = `
          <span class="tag-chip tag-bamboo">🌿 等待新資料建檔中</span>
          <span class="tag-chip tag-amber">✍ 支援各月份檢驗報告輸入</span>
        `;
        return;
      }

      const latest = confirmed[0];
      document.getElementById('letterDate').innerText = `最新採檢日期：${latest.test_date}`;

      const good = [];
      const warn = [];

      for (const [k, def] of Object.entries(metricDefs)) {
        const val = latest[k];
        if (val !== null && val !== undefined) {
          if (val < def.low) {
            warn.push({ name: def.name, val, reason: `稍低於目標 (${val} < ${def.low})` });
          } else if (val > def.high) {
            warn.push({ name: def.name, val, reason: `稍高於目標 (${val} > ${def.high})` });
          } else {
            good.push({ name: def.name, val });
          }
        }
      }

      let text = `親愛的<strong>${nickname}</strong>與家人，在 <strong>${latest.test_date}</strong> 的檢查中：`;
      if (good.length > 0) {
        text += `<br>🌿 其中 <strong>${good.map(g => g.name).join('、')}</strong> 維持在十分理想的安全區間，感謝長輩與家人長期的細心照顧，請為自己的努力喝采！`;
      }
      if (warn.length > 0) {
        text += `<br><br>💡 目前有微調空間的項目為：<strong>${warn.map(w => `${w.name} (${w.reason})`).join('、')}</strong>。<br>日常飲食溫馨小叮嚀：蔬菜切碎用大量滾水汆燙 3-5 分鐘以溫和去鉀、用餐按醫囑搭配降磷劑。慢慢調養即可，我們一直陪伴在身邊。`;
      } else {
        text += `<br>🎉 所有核心數值皆全數符合標準目標，狀態非常平穩安心，繼續保持現在的生活步調喔！`;
      }

      document.getElementById('letterContent').innerHTML = text;

      const tagContainer = document.getElementById('letterTags');
      let tagsHtml = '';
      good.forEach(g => {
        tagsHtml += `<span class="tag-chip tag-bamboo">✓ ${g.name} ${g.val} 安好</span>`;
      });
      warn.forEach(w => {
        tagsHtml += `<span class="tag-chip tag-amber">⚠ ${w.name} ${w.val} 留心</span>`;
      });
      tagContainer.innerHTML = tagsHtml;
    }

    // 5. 最新一期核心指標快報 (Overview Tab)
    function renderLatestQuickBox() {
      const confirmed = reports.filter(r => r.status === 'confirmed');
      const box = document.getElementById('latestQuickBox');
      const grid = document.getElementById('quickShelfGrid');

      if (confirmed.length === 0) {
        box.style.display = 'none';
        return;
      }

      const latest = confirmed[0];
      box.style.display = 'block';
      document.getElementById('quickReportDate').innerText = `採檢日期：${latest.test_date}`;

      let pillsHtml = '';
      const mainKeys = ['potassium', 'phosphorus', 'hemoglobin', 'calcium', 'albumin', 'kt_v'];
      mainKeys.forEach(k => {
        const def = metricDefs[k];
        const val = latest[k];
        let valClass = 'v-bamboo';
        if (val === null || val === undefined) {
          valClass = 'v-none';
        } else if (val < def.low) {
          valClass = 'v-amber';
        } else if (val > def.high) {
          valClass = 'v-cinnabar';
        }

        pillsHtml += `
          <div class="metric-pill">
            <div class="pill-header">
              <span>${def.name}</span>
              <span class="pill-unit">${def.unit}</span>
            </div>
            <div class="pill-row">
              <span class="pill-num ${valClass}">${val !== null && val !== undefined ? val : '--'}</span>
            </div>
            <div class="pill-target">
              目標: ${def.low === 0 ? '< ' + def.high : def.low + ' ~ ' + def.high}
            </div>
          </div>
        `;
      });

      grid.innerHTML = pillsHtml;
    }

    // 6. Chart.js 文人走勢圖
    function switchMetric(key) {
      currentTab = key;
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      event.target.classList.add('active');
      initChart(key);
    }

    function initChart(key) {
      const confirmed = reports.filter(r => r.status === 'confirmed').slice().reverse();
      const ctx = document.getElementById('trendChart').getContext('2d');
      const isSenior = document.body.classList.contains('senior-mode');

      if (chartInstance) {
        chartInstance.destroy();
      }

      if (confirmed.length === 0) {
        chartInstance = new Chart(ctx, {
          type: 'line',
          data: {
            labels: ['尚無資料'],
            datasets: [{
              label: '等待新檢驗數據入冊',
              data: [0],
              borderColor: '#8E9892',
              borderDash: [5, 5],
              pointRadius: 0
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                labels: { font: { family: 'Noto Sans TC', size: isSenior ? 14 : 12 } }
              }
            },
            scales: {
              y: { beginAtZero: true, max: 10 }
            }
          }
        });
        return;
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
            backgroundColor: def.color + '15',
            tension: 0.3,
            fill: false,
            borderWidth: isSenior ? 4 : 3,
            pointRadius: isSenior ? 8 : 6,
            pointHoverRadius: isSenior ? 11 : 9,
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
          backgroundColor: def.color + '1A',
          tension: 0.3,
          fill: true,
          borderWidth: isSenior ? 4.5 : 3.5,
          pointRadius: isSenior ? 9 : 7,
          pointHoverRadius: isSenior ? 12 : 10,
          pointBackgroundColor: def.color,
          pointBorderColor: '#FFFFFF',
          pointBorderWidth: 2.5
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
              labels: {
                color: '#2C302E',
                font: { family: 'Noto Sans TC', size: isSenior ? 14 : 12, weight: 600 },
                boxWidth: 14,
                padding: 16
              }
            },
            tooltip: {
              backgroundColor: '#FFFFFF',
              titleColor: '#245A44',
              bodyColor: '#2C302E',
              borderColor: '#E8E2D7',
              borderWidth: 1.5,
              padding: 12,
              bodyFont: { size: isSenior ? 15 : 13, family: 'Noto Sans TC' },
              titleFont: { size: isSenior ? 14 : 12, weight: 700, family: 'Noto Sans TC' },
              boxPadding: 6,
              usePointStyle: true
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(232, 226, 215, 0.6)' },
              ticks: { color: '#646E68', font: { family: 'Noto Sans TC', size: isSenior ? 13 : 11, weight: 600 } }
            },
            y: {
              grid: { color: 'rgba(232, 226, 215, 0.6)' },
              ticks: { color: '#646E68', font: { family: 'Noto Sans TC', size: isSenior ? 13 : 11 } }
            }
          }
        }
      });
    }

    // 7. 歷次檢驗詳實歷程獨立分頁 (History Tab)
    function toggleFolder(cardId) {
      const card = document.getElementById(cardId);
      if (card) {
        card.classList.toggle('open');
      }
    }

    function toggleAllFolders(shouldOpen) {
      document.querySelectorAll('.folder-card').forEach(c => {
        if (shouldOpen) {
          c.classList.add('open');
        } else {
          c.classList.remove('open');
        }
      });
    }

    function filterByMonth(dateStr) {
      selectedMonthFilter = dateStr;
      document.querySelectorAll('.history-pill').forEach(btn => btn.classList.remove('active'));
      event.target.classList.add('active');
      renderReportsList();
    }

    function renderHistoryControls() {
      const confirmed = reports;
      const controls = document.getElementById('historyControls');
      const pillsContainer = document.getElementById('historyFilterPills');

      if (confirmed.length === 0) {
        controls.style.display = 'none';
        return;
      }

      controls.style.display = 'flex';
      let pillsHtml = `<button class="history-pill ${selectedMonthFilter === 'all' ? 'active' : ''}" onclick="filterByMonth('all')">全部期數 (${confirmed.length})</button>`;
      
      confirmed.forEach((r, idx) => {
        const isLatest = idx === 0 ? ' (最新)' : '';
        const activeClass = selectedMonthFilter === r.test_date ? 'active' : '';
        pillsHtml += `<button class="history-pill ${activeClass}" onclick="filterByMonth('${r.test_date}')">${r.test_date}${isLatest}</button>`;
      });

      pillsContainer.innerHTML = pillsHtml;
    }

    function renderMatrixTable() {
      const box = document.getElementById('historyMatrixBox');
      const table = document.getElementById('matrixTable');
      const confirmed = reports.filter(r => r.status === 'confirmed');

      if (confirmed.length <= 1) {
        box.style.display = 'none';
        return;
      }

      box.style.display = 'block';
      let dates = confirmed.map(r => r.test_date);

      let thead = `<thead><tr><th>檢驗項目</th><th>建議安全區間</th>`;
      dates.forEach(d => {
        thead += `<th>${d}</th>`;
      });
      thead += `</tr></thead>`;

      let tbody = `<tbody>`;
      for (const [key, def] of Object.entries(metricDefs)) {
        tbody += `<tr><td>${def.name}</td><td>${def.low === 0 ? '< ' + def.high : def.low + ' ~ ' + def.high} ${def.unit}</td>`;
        confirmed.forEach(r => {
          const val = r[key];
          let valClass = 'v-bamboo';
          if (val === null || val === undefined) {
            valClass = 'v-none';
          } else if (val < def.low) {
            valClass = 'v-amber';
          } else if (val > def.high) {
            valClass = 'v-cinnabar';
          }
          tbody += `<td class="${valClass}" style="font-weight: 700;">${val !== null && val !== undefined ? val : '--'}</td>`;
        });
        tbody += `</tr>`;
      }
      tbody += `</tbody>`;

      table.innerHTML = thead + tbody;
    }

    function renderReportsList() {
      const container = document.getElementById('reportsListContainer');
      document.getElementById('reportCountBadge').innerText = reports.length;

      if (reports.length === 0) {
        container.innerHTML = `
          <div class="empty-card">
            <h3>目前尚無檢驗手札存摺</h3>
            <p style="margin-top: 8px;">歷史數據已全部重置清空。請由您提供各月份檢驗報告，我們將立即為長輩建立各期資料！</p>
          </div>
        `;
        return;
      }

      const filtered = selectedMonthFilter === 'all' 
        ? reports 
        : reports.filter(r => r.test_date === selectedMonthFilter);

      let html = '';
      filtered.forEach((r, idx) => {
        const folderId = `folder_${r.id || idx}`;
        const isFirst = (idx === 0 && selectedMonthFilter === 'all');

        let metricsHtml = '';
        let goodCount = 0;
        let warnCount = 0;

        for (const [key, def] of Object.entries(metricDefs)) {
          const val = r[key];
          let valClass = 'v-bamboo';
          if (val === null || val === undefined) {
            valClass = 'v-none';
          } else if (val < def.low) {
            valClass = 'v-amber';
            warnCount++;
          } else if (val > def.high) {
            valClass = 'v-cinnabar';
            warnCount++;
          } else {
            goodCount++;
          }

          metricsHtml += `
            <div class="metric-pill">
              <div class="pill-header">
                <span>${def.name}</span>
                <span class="pill-unit">${def.unit}</span>
              </div>
              <div class="pill-row">
                <span class="pill-num ${valClass}">${val !== null && val !== undefined ? val : '--'}</span>
              </div>
              <div class="pill-target">
                目標: ${def.low === 0 ? '< ' + def.high : def.low + ' ~ ' + def.high}
              </div>
            </div>
          `;
        }

        html += `
          <div class="folder-card ${isFirst ? 'open' : ''}" id="${folderId}">
            <div class="folder-header" onclick="toggleFolder('${folderId}')">
              <div class="folder-title-wrap">
                <span class="folder-date">📅 採檢日期：${r.test_date}</span>
                <span class="stamp-badge ${r.status === 'confirmed' ? 'stamp-good' : 'stamp-draft'}">
                  ${r.status === 'confirmed' ? '✓ 已入冊' : '⏳ 草稿'}
                </span>
                <div class="folder-summary-tags">
                  <span class="tag-chip tag-bamboo" style="padding: 2px 8px; font-size: 0.76rem;">${goodCount} 項標準</span>
                  ${warnCount > 0 ? `<span class="tag-chip tag-amber" style="padding: 2px 8px; font-size: 0.76rem;">${warnCount} 項留心</span>` : ''}
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 0.82rem; color: var(--text-dim);">點擊展開/收合</span>
                <span class="folder-toggle-icon">▼</span>
              </div>
            </div>
            <div class="folder-body">
              <div class="metrics-shelf">
                ${metricsHtml}
              </div>
            </div>
          </div>
        `;
      });

      container.innerHTML = html;
    }

    function init() {
      if (currentFamily && currentFamily.display_name) {
        document.getElementById('pageTitle').innerText = `${currentFamily.display_name} 健康月候手札`;
      }
      initSeniorMode();
      initLiff();
      renderAISummary();
      renderLatestQuickBox();
      renderHistoryControls();
      renderMatrixTable();
      renderReportsList();
      initChart('all');
    }

    init();
  </script>
</body>
</html>
"""


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(family_id: str | None = Query(None)) -> HTMLResponse:
    """長輩照護手札 ｜ 腎好伴 檢驗數據與走勢中心。"""
    c = await db()
    settings = get_settings()

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
    safe_liff_id = json.dumps(settings.liff_id or "", default=str)

    html = (
        DASHBOARD_HTML.replace("window.__REPORTS_DATA__ || []", safe_reports)
        .replace("window.__FAMILIES_DATA__ || []", safe_families)
        .replace("window.__CURRENT_FAMILY__ || null", safe_current_family)
        .replace("window.__LIFF_ID__", safe_liff_id)
    )

    return HTMLResponse(content=html)
