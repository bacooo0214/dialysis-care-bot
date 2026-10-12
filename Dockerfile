FROM python:3.11-slim

# 安裝繁體中文字型與基本依賴（確保 Matplotlib 渲染中文字型無方塊亂碼）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    fontconfig \
    ffmpeg \
    ca-certificates \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先複製 requirements.txt 享受 Docker layer 快取
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements.txt

# 複製應用程式原始碼
COPY . .

# 設定時區為台北
ENV TZ=Asia/Taipei
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# Cloud Run 會提供 $PORT 環境變數，預設 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
