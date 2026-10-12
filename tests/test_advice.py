"""語音淨化與衛教建議測試。"""

from app.services.advice import strip_for_speech


def test_strip_for_speech():
    raw_text = "阿公這次的鉀是 5.2 mEq/L 偏高 🟡，青菜要先燙過喔！💪\n\n記得按時吃藥。"
    speech = strip_for_speech(raw_text)

    # 不應包含 emoji 或單位縮寫
    assert "🟡" not in speech
    assert "💪" not in speech
    assert "mEq/L" not in speech
    assert "青菜要先燙過喔" in speech
    assert speech.endswith("。")
