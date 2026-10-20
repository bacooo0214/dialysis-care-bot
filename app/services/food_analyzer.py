"""外食與飲食拍照 AI 瞬間快篩模組（能吃嗎？怎麼吃？）。

利用 Gemini 多模態視覺模型辨識餐點、判斷高鉀/高磷/高水鹽風險，並產出洗腎長輩專屬的降雷救援吃法。
"""

from __future__ import annotations

import logging
from typing import Any

from google.genai import types
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.llm import gemini

log = logging.getLogger(__name__)


class FoodAnalysisResult(BaseModel):
    """食物快篩分析結果結構。"""

    is_food: bool = Field(description="這張照片是否包含餐點、菜餚、食物、點心或飲料")
    dish_name: str | None = Field(description="餐點或菜餚名稱，例如：紅燒牛肉麵、番茄炒蛋便當、珍珠奶茶")
    main_ingredients: list[str] = Field(
        default_factory=list, description="辨識出的主要食材清單，例如：['牛肉塊', '白麵條', '青江菜', '高湯']"
    )
    overall_level: str = Field(
        default="yellow", description="整體透析安全等級：green(安心吃) / yellow(注意份量) / red(高雷少碰)"
    )
    potassium_risk: str = Field(
        default="medium", description="鉀離子風險評估：low / medium / high"
    )
    potassium_note: str = Field(
        default="", description="鉀離子分析說明（如：深綠色蔬菜、番茄、高湯含鉀高）"
    )
    phosphorus_risk: str = Field(
        default="medium", description="磷離子風險評估：low / medium / high"
    )
    phosphorus_note: str = Field(
        default="", description="磷離子分析說明（如：加工肉品、起司、肉汁濃湯含無機磷高）"
    )
    sodium_water_note: str = Field(
        default="", description="鈉鹽與水分提醒（如：湯頭鹹度高易口渴積水、勾芡醬汁多）"
    )
    eating_hacks: list[str] = Field(
        default_factory=list,
        description="洗腎長輩降雷救援吃法 2~3 招（如：1. 湯頭一口都別喝 2. 青菜過熱水去除鉀離子 3. 配飯前咬碎磷結合劑）",
    )
    friendly_summary: str = Field(
        default="",
        description="給長輩與家屬的一句白話溫暖總評（60字以內），肯定長輩享受美食，提醒核心安全眉角",
    )


FOOD_PROMPT = """你是台灣頂尖的腎臟專科與血液透析臨床營養專家。
請仔細辨識這張照片中的食物、飲料或餐餚，並針對「正在洗腎（血液透析）的台灣長輩」提供嚴謹且溫暖的外食避雷指南。

分析原則：
1. 先判斷是否為食物/飲品，若不是（例如風景、文件、自拍、藥盒等），is_food 填 false，其餘填 null 或空清單。
2. 鉀離子（K）：
   - 高雷（high）：深綠色蔬菜（地瓜葉、菠菜、空心菜）、番茄醬汁、馬鈴薯、南瓜、香菇木耳、中藥燉補湯、果汁（奇異果、香蕉、楊桃【絕對禁忌！】）。
   - 低雷（low）：白飯、冬粉、汆燙過的白菜/高麗菜、去皮蘋果、水梨。
3. 磷離子（P）：
   - 高雷（high）：內臟、加工肉品（香腸、貢丸、熱狗）、堅果種子、起司乳酪、火鍋高湯、全穀雜糧、碳酸飲料。
   - 低雷（low）：新鮮未加工雞肉、豬里肌、蛋白。
4. 鈉與水：
   - 濃湯、牛肉麵湯、拉麵湯、滷汁、勾芡羹湯（如肉羹、蚵仔麵線）極鹹且含大量水分與無機磷，長輩喝了容易引發口渴、肺水腫與血壓飆高。
5. 降雷救援吃法（eating_hacks）：
   - 務必教長輩「怎麼吃才安全」，而不是全盤否定不能吃！
   - 例如：「湯一口都不要喝」、「肉塊與麵條撈出瀝乾」、「燙青菜再過一次溫熱開水去除部分溶出的鉀離子」、「吃第一口飯時咬碎磷結合劑（如碳酸鈣/醋酸鈣/福斯利諾）」。
6. 語氣溫暖、體貼、白話在地，讓長輩感到被支持，安心享用生活滋味。
"""


async def analyze_food(image: bytes, mime_type: str = "image/jpeg") -> FoodAnalysisResult:
    """呼叫 Gemini 進行食物多模態辨識與透析安全評估。"""
    settings = get_settings()
    try:
        resp = await gemini().aio.models.generate_content(
            model=settings.gemini_model,
            contents=[types.Part.from_bytes(data=image, mime_type=mime_type), FOOD_PROMPT],
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=FoodAnalysisResult,
            ),
        )
        return FoodAnalysisResult.model_validate_json(resp.text or "{}")
    except Exception as e:
        log.exception("食物拍照 AI 快篩失敗: %s", e)
        # 回傳保底安全的結構
        return FoodAnalysisResult(
            is_food=False,
            dish_name=None,
            main_ingredients=[],
            overall_level="yellow",
            potassium_risk="medium",
            potassium_note="暫時無法精確分析鉀離子",
            phosphorus_risk="medium",
            phosphorus_note="暫時無法精確分析磷離子",
            sodium_water_note="外食請記得盡量少喝湯、少沾醬",
            eating_hacks=["湯汁盡量不喝", "菜餚可先過熱開水去鹽去鉀", "肉類搭配隨餐咬碎之磷結合劑"],
            friendly_summary="系統剛才稍微打了瞌睡，但記得外食『吃料不喝湯、青菜過水洗』最安全喔！",
        )
