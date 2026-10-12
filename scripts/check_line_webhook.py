import sys
import httpx
import re

with open(".env", "r", encoding="utf-8") as f:
    text = f.read()

token = re.search(r"LINE_CHANNEL_ACCESS_TOKEN=(.*)", text).group(1).strip()
headers = {"Authorization": f"Bearer {token}"}

try:
    r = httpx.get("https://api.line.me/v2/bot/channel/webhook/endpoint", headers=headers, timeout=10)
    print("Endpoint info:", r.status_code, r.text)
except Exception as e:
    print("Endpoint error:", e)

try:
    r2 = httpx.post("https://api.line.me/v2/bot/channel/webhook/test", headers=headers, json={"endpoint": "https://dialysis-care-bot.onrender.com/callback"}, timeout=10)
    print("Test result:", r2.status_code, r2.text)
except Exception as e:
    print("Test error:", e)
