"""FastAPI 主應用程式。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.line_api import line
from app.routes.cron import router as cron_router
from app.routes.webhook import router as webhook_router

# 設定日誌格式
logging.basicConfig(
    level=getattr(logging, get_settings().log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """應用程式生命週期管理。"""
    log.info("洗腎照護 LINE Bot 後端正在啟動...")
    yield
    log.info("洗腎照護 LINE Bot 後端正在關閉...")
    await line().aclose()


app = FastAPI(
    title="Dialysis Care LINE Bot API",
    description="洗腎病患檢驗報告可視化與 AI 照護後端服務",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS (預留日後 LIFF 或儀表板前端串接)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由
app.include_router(webhook_router)
app.include_router(cron_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """健康檢查端點。"""
    return {"status": "healthy", "service": "dialysis-care-bot"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
