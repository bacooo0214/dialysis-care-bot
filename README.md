# 洗腎病患檢驗報告可視化與 AI 照護 LINE Bot (腎好伴 🌱)

整合於 LINE 家族群組的血液透析 AI 醫療輔助機器人。透過 AI 視覺模型自動擷取每月透析檢驗紀錄數據，轉化為長輩友善的視覺化圖表與紅綠燈成績單，並結合家庭專屬衛教知識庫提供溫暖白話的生活飲食建議與語音播報。

---

## 🌟 核心特色

1. **AI 視覺 OCR 辨識**：支援手機拍照直接上傳血液透析檢驗單，自動相容民國年、多月份表格，後處理校正單位與數值合理性。
2. **長輩專用紅綠燈成績單**：以綠燈（很好）、黃燈（要注意）、紅燈（要小心）取代冰冷複雜數字，無恐嚇性字眼。
3. **大字體安全範圍折線圖**：Matplotlib 繪製 2x 高解析度趨勢圖，綠色安全目標底帶、紅綠燈彩色數值點，視力老化友善。
4. **AI 溫暖白話建議與語音播報**：結合家屬自訂經驗庫（優先採用）與標準腎臟衛教；支援 gTTS 語音播放。
5. **異常指標主動 @ 標記家屬**：在家族群組中，當數值出現紅燈危險警示時，主動推播並使用 `TextMessageV2` @ 標記家屬。
6. **每日自主管理**：一鍵記錄乾體重增幅比對、血壓、喝水量（原子累加防競爭）。
7. **雙向備份與資料庫安全**：Supabase PostgreSQL 全表開啟 RLS，私有 Storage 桶長效 Signed URL，可選 Google Sheets 同步。

---

## 🛠️ 技術架構

- **後端框架**：Python 3.11 + FastAPI (非同步 Webhook 處理，秒級回應用戶)
- **資料庫與儲存**：Supabase (PostgreSQL + RLS + Storage)
- **通訊介面**：LINE Messaging API (Flex Messages, TextMessageV2 Mentions, 2500x1686 Rich Menu)
- **AI 辨識與建議**：Google Gemini 2.5 Flash (Vision OCR + Structured JSON Advice)
- **語音合成**：gTTS + mutagen (計算毫秒音訊長度供 LINE Audio Message)
- **圖表引擎**：Matplotlib (支援中文字型動態載入與安全區間底帶)
- **部署環境**：Google Cloud Run (容器化) + Cloud Scheduler (排程提醒)

---

## 📁 專案結構

```
.
├── app/
│   ├── config.py              # Pydantic Settings 環境設定
│   ├── db.py                  # Supabase 資料庫封裝 (原子喝水 RPC、去重、草稿合併)
│   ├── metrics.py             # 檢驗指標定義、安全區間與紅綠燈演算法
│   ├── line_api.py            # LINE Messaging API REST Client (Retry-Key, TextV2)
│   ├── flex_messages.py       # 長輩友善 Flex 卡片與選單樣板
│   ├── bot_handlers.py        # 核心事件分派器與狀態機 (FSM)
│   ├── main.py                # FastAPI 應用程式入口
│   ├── routes/
│   │   ├── webhook.py         # LINE Webhook (/callback)
│   │   └── cron.py            # 排程提醒端點 (/cron/daily-reminders)
│   └── services/
│       ├── ocr.py             # Gemini Vision OCR 辨識與民國年校正
│       ├── advice.py          # AI 白話建議生成與家屬經驗自動分類
│       ├── charts.py          # 長輩專用趨勢折線圖與綜合儀表板
│       ├── tts.py             # gTTS 語音生成與長度計算
│       ├── sheets.py          # Google Sheets 雙向同步備份
│       ├── storage.py         # Supabase Storage 檔案上傳與簽署 URL
│       └── llm.py             # Gemini Client 單例
├── scripts/
│   ├── generate_rich_menu_image.py  # 動態生成 2500x1686 圖文選單圖片
│   └── setup_rich_menu.py           # 向 LINE 註冊並設定預設 Rich Menu
├── supabase/
│   └── migrations/
│       ├── 20261012000001_init_schema.sql      # 核心資料表結構、RLS 政策與 RPC
│       └── 20261012000002_seed_care_rules.sql  # 預設衛教知識庫種子資料
├── tests/                     # 核心邏輯單元測試
├── Dockerfile                 # Cloud Run 容器配置 (預裝 Noto CJK 繁體中文與 ffmpeg)
├── requirements.txt
└── .env.example
```

---

## 🚀 快速開始

### 1. 建立虛擬環境與安裝依賴

```bash
python3 -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

python3 -m pip install -r requirements.txt
```

### 2. 配置環境變數

複製 `.env.example` 為 `.env` 並填入憑證：

```bash
cp .env.example .env
```

必填項目說明：
- `LINE_CHANNEL_SECRET` 與 `LINE_CHANNEL_ACCESS_TOKEN`：從 [LINE Developers Console](https://developers.line.biz/) 取得。
- `GEMINI_API_KEY`：從 [Google AI Studio](https://aistudio.google.com/) 取得。
- `SUPABASE_SERVICE_ROLE_KEY`：從 Supabase 專案 Dashboard (`Project Settings -> API`) 複製 `service_role` key。
- `SUPABASE_URL`：已預設配置為專屬專案 `https://qutlevdyjfgwkgowlxdd.supabase.co`。

### 3. 本地啟動開發伺服器

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

使用 ngrok 穿透進行 LINE Webhook 測試：
```bash
ngrok http 8000
```
在 LINE Developers Console 將 Webhook URL 設定為：`https://<你的-ngrok-網址>/callback` 並開啟 `Use webhook`。

### 4. 註冊長輩專用 Rich Menu 圖文選單

執行以下指令，自動生成 2500x1686 專屬 6 格高對比選單並啟用：
```bash
python3 scripts/setup_rich_menu.py
```

### 5. 執行單元測試

```bash
python3 -m pytest tests/
```

---

## 💬 常用對話與指令手冊

| 功能 | 輸入範例 | 說明 |
| :--- | :--- | :--- |
| **上傳檢驗單** | 點選選單「上傳報告」或直接傳送照片 | 自動辨識 K、P、Hb、Alb、Ca 等數值並送出確認卡片 |
| **手動微調** | 「鉀 4.8」、「Hb 10.5」、「日期 2026-10-15」 | 修改辨識有誤的數值並重新計算 |
| **記錄喝水** | 「喝水 200」、「+100」、「喝水 150」 | 原子累加當日水分，回報上限進度與燈號 |
| **記錄體重** | 「記體重 58.5」、「體重 58.5」 | 記錄當日體重，並比對基準乾體重增幅 % |
| **記錄血壓** | 「記血壓 130/80」、「血壓 135 85」 | 記錄當日早晚血壓，依收縮壓/舒張壓給予燈號 |
| **查看報告** | 「看報告」、「成績單」 | 查看最近一期檢驗報告總覽卡片 |
| **趨勢折線圖** | 「看趨勢」、「看圖表」 | 開啟圖表選單（綜合儀表板、鉀、磷、血紅素等趨勢圖） |
| **今日狀況** | 「今日狀況」、「今日紀錄」 | 彙整今日體重、血壓與喝水量進度 |
| **新增照護經驗** | `#經驗 青菜切小塊先滾水燙3分鐘去鉀` | 存入家庭專屬知識庫，AI 生成建議時優先採用！ |
| **設定乾體重** | `設定乾體重 55` | 更新長輩基準乾體重（供體重增幅 % 計算） |
| **設定長輩稱呼** | `設定稱呼 爸爸` / `設定稱呼 阿嬤` | AI 回覆與語音播報將以此稱呼長輩 |
| **設定限水上限** | `設定限水 1200` | 更新長輩每日建議水分上限 (ml) |

---

## ☁️ Google Cloud Run 部署指引

1. **建置並發布容器**：
```bash
gcloud builds submit --tag gcr.io/<YOUR_PROJECT_ID>/dialysis-care-bot
```

2. **部署至 Cloud Run**：
```bash
gcloud run deploy dialysis-care-bot \
  --image gcr.io/<YOUR_PROJECT_ID>/dialysis-care-bot \
  --platform managed \
  --region asia-east1 \
  --allow-unauthenticated \
  --set-env-vars LINE_CHANNEL_SECRET=...,LINE_CHANNEL_ACCESS_TOKEN=...,GEMINI_API_KEY=...,SUPABASE_URL=...,SUPABASE_SERVICE_ROLE_KEY=...,CRON_SECRET=...
```

3. **設定 Cloud Scheduler 定時提醒**：
建立排程任務（例如每日早晨 07:30 發送晨起體重與透析提醒）：
- **頻率**：`30 7 * * *` (時區 Asia/Taipei)
- **目標**：HTTP POST
- **URL**：`https://<YOUR_CLOUD_RUN_URL>/cron/daily-reminders`
- **Headers**：`Authorization: Bearer <YOUR_CRON_SECRET>`
