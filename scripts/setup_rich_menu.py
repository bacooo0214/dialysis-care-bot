"""向 LINE Messaging API 註冊並設定預設 Rich Menu。"""

import asyncio
import os
import sys

# 將工作目錄加入 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.line_api import line
from scripts.generate_rich_menu_image import create_rich_menu_image


async def main() -> None:
    print("1. 生成 Rich Menu 圖片 (2500 x 1686)...")
    png_bytes = create_rich_menu_image()

    width = 2500
    height = 1686
    col_w = width // 3
    row_h = height // 2

    rich_menu_body = {
        "size": {"width": width, "height": height},
        "selected": True,
        "name": "洗腎照護主選單",
        "chatBarText": "照護選單 📋",
        "areas": [
            # (0, 0) 上傳報告
            {
                "bounds": {"x": 0, "y": 0, "width": col_w, "height": row_h},
                "action": {"type": "message", "text": "上傳報告"},
            },
            # (1, 0) 檢驗成績單
            {
                "bounds": {"x": col_w, "y": 0, "width": col_w, "height": row_h},
                "action": {"type": "message", "text": "看報告"},
            },
            # (2, 0) 趨勢圖表
            {
                "bounds": {"x": col_w * 2, "y": 0, "width": width - col_w * 2, "height": row_h},
                "action": {"type": "postback", "data": "action=view_charts_menu", "displayText": "我想看數據趨勢圖"},
            },
            # (0, 1) 每日體重
            {
                "bounds": {"x": 0, "y": row_h, "width": col_w, "height": row_h},
                "action": {"type": "postback", "data": "action=prompt_weight", "displayText": "我要記錄體重"},
            },
            # (1, 1) 血壓測量
            {
                "bounds": {"x": col_w, "y": row_h, "width": col_w, "height": row_h},
                "action": {"type": "postback", "data": "action=prompt_bp", "displayText": "我要記錄血壓"},
            },
            # (2, 1) 喝水紀錄
            {
                "bounds": {"x": col_w * 2, "y": row_h, "width": width - col_w * 2, "height": row_h},
                "action": {"type": "message", "text": "今日狀況"},
            },
        ],
    }

    client = line()

    print("2. 建立 Rich Menu 資源...")
    menu_id = await client.create_rich_menu(rich_menu_body)
    print(f"成功建立 Rich Menu ID: {menu_id}")

    print("3. 上傳選單圖片...")
    await client.upload_rich_menu_image(menu_id, png_bytes)
    print("圖片上傳成功！")

    print("4. 設為全域預設 Rich Menu...")
    await client.set_default_rich_menu(menu_id)
    print("Rich Menu 設定成功！已套用為所有使用者的預設圖文選單。")

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
