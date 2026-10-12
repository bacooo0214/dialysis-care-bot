import httpx
import sys

api_key = "u3833130-5d1155e631d12ab24a6468e3"

print("1. 修改現有 Monitor (id: 804204621) 為 dialysis-care-bot...")
payload = {
    "api_key": api_key,
    "format": "json",
    "id": 804204621,
    "friendly_name": "dialysis-care-bot",
    "url": "https://dialysis-care-bot.onrender.com/health",
    "status": 1,
}

r = httpx.post("https://api.uptimerobot.com/v2/editMonitor", data=payload)
print("建立結果:", r.status_code, r.text)

print("\n2. 查詢所有 Monitors...")
r2 = httpx.post("https://api.uptimerobot.com/v2/getMonitors", data={"api_key": api_key, "format": "json"})
print("查詢結果:", r2.status_code, r2.text)
