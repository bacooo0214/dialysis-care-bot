"""版本更新歷程 Web 路由與前端頁面。"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["changelog"])

CHANGELOG_HTML = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>版本更新紀錄 ｜ 雲端小乖孫 AI 腎臟照護小幫手</title>
  <meta name="description" content="血液透析檢驗報告可視化與 AI 照護 LINE Bot（雲端小乖孫）的最新版本更新紀錄與歷程。">
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
      --tag-feat: rgba(16, 185, 129, 0.15);
      --tag-feat-text: #34D399;
      --tag-fix: rgba(245, 158, 11, 0.15);
      --tag-fix-text: #FBBF24;
      --tag-infra: rgba(59, 130, 246, 0.15);
      --tag-infra-text: #60A5FA;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg-primary);
      background-image: 
        radial-gradient(at 0% 0%, rgba(16, 185, 129, 0.08) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(59, 130, 246, 0.06) 0px, transparent 50%);
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', 'Noto Sans TC', -apple-system, sans-serif;
      min-height: 100vh;
      line-height: 1.6;
      padding: 40px 20px 80px;
    }

    .container {
      max-width: 860px;
      margin: 0 auto;
    }

    /* Header */
    .header {
      text-align: center;
      margin-bottom: 50px;
      padding-bottom: 30px;
      border-bottom: 1px solid var(--border-color);
    }

    .badge-bot {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 16px;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.25);
      border-radius: 999px;
      color: var(--primary-light);
      font-size: 0.875rem;
      font-weight: 600;
      margin-bottom: 16px;
    }

    .badge-bot span.dot {
      width: 8px;
      height: 8px;
      background: var(--primary);
      border-radius: 50%;
      box-shadow: 0 0 10px var(--primary);
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.5; transform: scale(0.85); }
    }

    h1 {
      font-size: 2.5rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 12px;
      background: linear-gradient(135deg, #FFFFFF 0%, #D1D5DB 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .subtitle {
      color: var(--text-muted);
      font-size: 1.1rem;
      max-width: 600px;
      margin: 0 auto;
    }

    /* Timeline */
    .timeline {
      position: relative;
      padding-left: 32px;
    }

    .timeline::before {
      content: '';
      position: absolute;
      left: 7px;
      top: 14px;
      bottom: 20px;
      width: 2px;
      background: linear-gradient(to bottom, var(--primary) 0%, rgba(255,255,255,0.05) 100%);
    }

    .release-card {
      position: relative;
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 28px 32px;
      margin-bottom: 32px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .release-card:hover {
      background: var(--bg-card-hover);
      border-color: var(--border-highlight);
      transform: translateY(-2px);
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.3);
    }

    .release-card.latest {
      border-color: rgba(16, 185, 129, 0.4);
      box-shadow: 0 0 25px rgba(16, 185, 129, 0.08);
    }

    .timeline-node {
      position: absolute;
      left: -32px;
      top: 32px;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: #0A0F1D;
      border: 3px solid var(--primary);
      box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.2);
    }

    .release-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 20px;
    }

    .release-title {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .version-tag {
      font-size: 1.35rem;
      font-weight: 700;
      color: #FFFFFF;
    }

    .badge-latest {
      background: var(--primary);
      color: #042F2E;
      font-size: 0.75rem;
      font-weight: 700;
      padding: 2px 10px;
      border-radius: 999px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .release-date {
      color: var(--text-dim);
      font-size: 0.9rem;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .section-title {
      font-size: 0.875rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin: 18px 0 10px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .section-title.feat { color: var(--tag-feat-text); }
    .section-title.fix { color: var(--tag-fix-text); }
    .section-title.infra { color: var(--tag-infra-text); }

    .change-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .change-item {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      color: var(--text-main);
      font-size: 0.95rem;
    }

    .change-item::before {
      content: '•';
      color: var(--text-dim);
      font-size: 1.2rem;
      line-height: 1;
      margin-top: 2px;
    }

    .change-item strong {
      color: #FFFFFF;
      font-weight: 600;
    }

    /* Footer */
    .footer {
      text-align: center;
      margin-top: 60px;
      color: var(--text-dim);
      font-size: 0.875rem;
    }

    .footer a {
      color: var(--primary-light);
      text-decoration: none;
      transition: color 0.2s;
    }

    .footer a:hover {
      text-decoration: underline;
    }

    @media (max-width: 640px) {
      body { padding: 24px 14px 60px; }
      h1 { font-size: 1.85rem; }
      .release-card { padding: 20px 22px; }
      .timeline { padding-left: 24px; }
      .timeline-node { left: -24px; }
    }
  </style>
</head>
<body>

  <div class="container">
    <header class="header">
      <div class="badge-bot">
        <span class="dot"></span>
        雲端小乖孫 ｜ 血液透析 AI 照護小幫手
      </div>
      <h1>系統版本更新紀錄</h1>
      <p class="subtitle">追蹤每一次醫療檢驗數據可視化、AI 照護建議與長輩友善互動的演進細節</p>
    </header>

    <div class="timeline">

      <!-- v1.2.0 -->
      <article class="release-card latest">
        <div class="timeline-node"></div>
        <div class="release-header">
          <div class="release-title">
            <span class="version-tag">v1.2.0</span>
            <span class="badge-latest">LATEST</span>
          </div>
          <div class="release-date">
            📅 2026 年 10 月 13 日
          </div>
        </div>

        <div class="section-title feat">✨ 新增功能 (Features)</div>
        <ul class="change-list">
          <li class="change-item">
            <div><strong>浮動實體快捷鍵 (Quick Reply)</strong>：每次訊息底部自帶 7 大實體按鈕（📸 上傳報告、📈 趨勢折線圖、⚖️ 記體重、❤️ 記血壓、💧 喝水 100/200cc、📋 今日總覽），一指點擊即可直達。</div>
          </li>
          <li class="change-item">
            <div><strong>辨識進度與預估時間提示</strong>：核對前提示「3~5 秒內生成成績單」，確認後立即觸發 LINE 官方輸入中動畫，徹底消除等待疑慮。</div>
          </li>
          <li class="change-item">
            <div><strong>版本歷史頁面上線</strong>：提供公開網頁版 <code>/changelog</code> 時間軸與 LINE 內建更新卡片。</div>
          </li>
        </ul>

        <div class="section-title fix">🐛 錯誤修復 (Bug Fixes)</div>
        <ul class="change-list">
          <li class="change-item">
            <div><strong>修復 Flex Message 400 退件</strong>：解決首次上傳報告無前期趨勢時為空字串引發 LINE API 拒收問題，補上防禦預設值。</div>
          </li>
          <li class="change-item">
            <div><strong>全域圖文選單鎖定</strong>：重新註冊並設為所有使用者的預設 Rich Menu。</div>
          </li>
        </ul>
      </article>

      <!-- v1.1.0 -->
      <article class="release-card">
        <div class="timeline-node"></div>
        <div class="release-header">
          <div class="release-title">
            <span class="version-tag">v1.1.0</span>
          </div>
          <div class="release-date">
            📅 2026 年 10 月 13 日
          </div>
        </div>

        <div class="section-title infra">☁️ 雲端正式架構 (Infra & Cloud)</div>
        <ul class="change-list">
          <li class="change-item">
            <div><strong>正式託管至 Render.com</strong>：全天候 Linux 雲端常駐容器，徹底擺脫本機 Tunnel 連線不穩定問題。</div>
          </li>
          <li class="change-item">
            <div><strong>24/7 永不休眠雙保險</strong>：整合 UptimeRobot 每 5 分鐘健康 Ping 與 GitHub Actions Keepalive 定時喚醒。</div>
          </li>
          <li class="change-item">
            <div><strong>LINE 官方 Webhook 啟用</strong>：完成全域網址註冊與連通性認證。</div>
          </li>
        </ul>

        <div class="section-title feat">⚡ 調整與優化 (Enhancements)</div>
        <ul class="change-list">
          <li class="change-item">
            <div><strong>取消語音播報功能</strong>：移除檢驗成績單上的「🔊 聽語音建議播報」按鈕與 gTTS 後端生成，專注於圖文分析。</div>
          </li>
          <li class="change-item">
            <div><strong>家庭群組協同模式全開</strong>：支援加入 LINE 群組、多家庭資料隔離與異常數值主動 <code>@</code> 標記家屬警報。</div>
          </li>
        </ul>
      </article>

      <!-- v1.0.0 -->
      <article class="release-card">
        <div class="timeline-node"></div>
        <div class="release-header">
          <div class="release-title">
            <span class="version-tag">v1.0.0</span>
          </div>
          <div class="release-date">
            📅 2026 年 10 月 12 日
          </div>
        </div>

        <div class="section-title feat">🎉 核心功能正式發布 (Initial Release)</div>
        <ul class="change-list">
          <li class="change-item">
            <div><strong>Gemini 多模態視覺 OCR</strong>：手機拍照即時辨識血液透析檢驗單，自動校正民國年與醫療單位。</div>
          </li>
          <li class="change-item">
            <div><strong>長輩專用紅綠燈成績單</strong>：依臨床指引將數值標定為綠燈（安全）、黃燈（注意）、紅燈（警示）。</div>
          </li>
          <li class="change-item">
            <div><strong>大字體安全區間趨勢圖</strong>：自動繪製長輩友善高清折線走勢圖。</div>
          </li>
          <li class="change-item">
            <div><strong>AI 白話照護飲食建議</strong>：提供溫暖易懂的生活照護小技巧（蔬菜汆燙瀝乾、磷結合劑用法）。</div>
          </li>
          <li class="change-item">
            <div><strong>每日原子自主管理</strong>：支援體重增幅比對、血壓落點分析與喝水打卡。</div>
          </li>
        </ul>
      </article>

    </div>

    <footer class="footer">
      <p>雲端小乖孫 AI 腎臟照護小幫手 ｜ 由 Google Gemini 2.5 Flash 與 Supabase 驅動</p>
      <p style="margin-top: 6px;">健康無價，愛心同行 💚</p>
    </footer>
  </div>

</body>
</html>
"""


@router.get("/changelog", response_class=HTMLResponse)
async def get_changelog() -> HTMLResponse:
    """提供版本更新歷程視覺化網頁。"""
    return HTMLResponse(content=CHANGELOG_HTML, status_code=200)


@router.get("/", response_class=HTMLResponse)
async def get_root() -> HTMLResponse:
    """根目錄首頁導向至版本更新歷程。"""
    return HTMLResponse(content=CHANGELOG_HTML, status_code=200)
