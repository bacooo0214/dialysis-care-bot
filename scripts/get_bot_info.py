import os
import re
import httpx

with open(".env", "r", encoding="utf-8") as f:
    env_text = f.read()
token = re.search(r"LINE_CHANNEL_ACCESS_TOKEN=(.*)", env_text).group(1).strip()

headers = {"Authorization": f"Bearer {token}"}
r = httpx.get("https://api.line.me/v2/bot/info", headers=headers)
print("Status:", r.status_code)
print("Data:", r.json())
