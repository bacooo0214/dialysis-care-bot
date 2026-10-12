"""自動向 LINE 設定並驗證 Webhook Endpoint。"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
from app.config import get_settings


async def main() -> None:
    settings = get_settings()
    token = settings.line_channel_access_token
    webhook_url = "https://488106c082c34f.lhr.life/callback"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        print(f"1. 設定 Webhook Endpoint 為: {webhook_url}")
        r1 = await client.put(
            "https://api.line.me/v2/bot/channel/webhook/endpoint",
            headers=headers,
            json={"endpoint": webhook_url},
        )
        print("設定結果:", r1.status_code, r1.text)

        print("2. 測試 Webhook 連通性 (LINE Test Endpoint)...")
        r2 = await client.post(
            "https://api.line.me/v2/bot/channel/webhook/test",
            headers=headers,
            json={"endpoint": webhook_url},
        )
        print("測試結果:", r2.status_code, r2.text)


if __name__ == "__main__":
    asyncio.run(main())
