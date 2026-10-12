"""繪製長輩專用高清晰度 LINE Rich Menu 圖文選單圖片 (2500 x 1686)。"""

from __future__ import annotations

import io
from PIL import Image, ImageDraw, ImageFont


def create_rich_menu_image() -> bytes:
    """繪製 2500x1686 的 6 格圖文選單。"""
    width = 2500
    height = 1686
    img = Image.new("RGB", (width, height), color="#FFFFFF")
    draw = ImageDraw.Draw(img)

    # 6 格劃分：2 列 x 3 行
    # 每格寬 = 2500 / 3 ≈ 833.33，每格高 = 1686 / 2 = 843
    col_w = width // 3
    row_h = height // 2

    # 按鈕定義 (col, row, icon, title, subtitle, bg_color, text_color)
    buttons = [
        # 第 1 列
        (0, 0, "📸", "上傳報告", "拍照快速辨識", "#ECFDF5", "#065F46"),
        (1, 0, "📊", "檢驗成績單", "紅綠燈總覽", "#EFF6FF", "#1E40AF"),
        (2, 0, "📈", "趨勢圖表", "掌握數值變化", "#EEF2FF", "#3730A3"),
        # 第 2 列
        (0, 1, "⚖️", "每日體重", "乾體重增幅比對", "#FFFBEB", "#92400E"),
        (1, 1, "❤️", "血壓測量", "早晚血壓追蹤", "#FEF2F2", "#991B1B"),
        (2, 1, "💧", "喝水紀錄", "嚴格控水不超標", "#F0FDF4", "#166534"),
    ]

    # 字型嘗試
    font_candidates = [
        "msjhbd.ttc",  # 微軟正黑體粗體
        "msjh.ttc",
        "NotoSansCJKtc-Bold.otf",
        "NotoSansTC-Bold.otf",
        "Arial.ttf",
    ]
    title_font = None
    sub_font = None
    for fc in font_candidates:
        try:
            title_font = ImageFont.truetype(fc, 96)
            sub_font = ImageFont.truetype(fc, 48)
            break
        except Exception:
            continue

    if not title_font:
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    for col, row, icon, title, subtitle, bg_color, text_color in buttons:
        x1 = col * col_w
        y1 = row * row_h
        x2 = (col + 1) * col_w if col < 2 else width
        y2 = (row + 1) * row_h if row < 1 else height

        # 繪製背景色塊
        draw.rectangle([x1, y1, x2, y2], fill=bg_color)

        # 繪製邊框
        draw.rectangle([x1, y1, x2, y2], outline="#D1D5DB", width=4)

        center_x = (x1 + x2) // 2

        # 繪製大圖標文字 (若無 emoji 字型則以乾淨文字代替)
        try:
            icon_font = ImageFont.truetype("seguiemj.ttf", 160)
            draw.text((center_x, y1 + 180), icon, font=icon_font, anchor="mm")
        except Exception:
            pass

        # 繪製主標題 (超大字)
        draw.text((center_x, y1 + 460), title, font=title_font, fill=text_color, anchor="mm")

        # 繪製副標題
        draw.text((center_x, y1 + 590), subtitle, font=sub_font, fill="#4B5563", anchor="mm")

    # 輸出 JPEG 或 PNG bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


if __name__ == "__main__":
    b = create_rich_menu_image()
    with open("rich_menu.png", "wb") as f:
        f.write(b)
    print("成功產生 rich_menu.png (2500x1686)")
