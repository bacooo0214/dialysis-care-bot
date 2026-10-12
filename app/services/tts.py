"""文字轉語音服務 (TTS)。

使用 gTTS (繁體中文 zh-TW) 生成語音訊息，上傳至 Supabase Storage 並計算毫秒長度供 LINE Audio Message 使用。
"""

from __future__ import annotations

import io
import logging
from gtts import gTTS
from mutagen.mp3 import MP3

from app.services.storage import upload_and_sign

log = logging.getLogger(__name__)


async def generate_speech_audio(text: str, family_id: str) -> tuple[str, int]:
    """將文字轉換為 MP3 語音檔並上傳至 Storage。

    回傳: (signed_url, duration_ms)
    """
    if not text.strip():
        text = "您好，目前沒有新的語音建議。"

    # 1. 產生 MP3 音訊串流
    buf = io.BytesIO()
    tts = gTTS(text=text, lang="zh-tw", slow=False)
    tts.write_to_fp(buf)
    mp3_bytes = buf.getvalue()

    # 2. 透過 mutagen 計算精確長度 (毫秒)
    duration_ms = 3000
    try:
        audio = MP3(io.BytesIO(mp3_bytes))
        if audio.info and audio.info.length:
            duration_ms = max(int(audio.info.length * 1000), 1000)
    except Exception as e:
        log.warning("計算音訊長度失敗，使用預估長度: %s", e)
        # 約每字 250ms 估計
        duration_ms = max(len(text) * 250, 2000)

    # 3. 上傳至 Supabase Storage 並取得 signed URL
    _path, url = await upload_and_sign(
        family_id=family_id,
        folder="audio",
        data=mp3_bytes,
        content_type="audio/mpeg",
        ext="mp3",
    )

    return url, duration_ms
