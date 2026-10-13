"""環境設定。"""

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """從環境變數 / .env 讀取的設定。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LINE
    line_channel_secret: str
    line_channel_access_token: str

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    # Supabase（service role 只存在後端）
    supabase_url: str
    supabase_service_role_key: str
    storage_bucket: str = "media"
    signed_url_ttl_seconds: int = 60 * 60 * 24 * 365  # LINE 舊訊息點開仍要看得到

    # 隱私：預設不保存含姓名/病歷號的原始照片
    store_original_images: bool = False
    # 群組內未按「上傳報告」時，是否自動判斷照片是不是檢驗單
    group_auto_detect_reports: bool = True

    # Google Sheets（JSON 字串或檔案路徑）
    google_service_account_json: str | None = None

    # LINE LIFF 設定（讓網頁在 LINE 內部瀏覽器開啟）
    liff_id: str | None = None

    # Cloud Scheduler 呼叫 /cron/* 用
    cron_secret: str = "change-me"

    timezone: str = "Asia/Taipei"
    log_level: str = "INFO"

    @property
    def tz(self) -> ZoneInfo:
        """回傳時區物件。"""
        return ZoneInfo(self.timezone)

    def get_dashboard_url(self, family_id: str | None = None) -> str:
        """取得數據中心 URL（優先使用 LINE 內部 LIFF 網址）。"""
        base_domain = "https://dialysis-care-bot.onrender.com"
        if self.liff_id:
            return f"https://liff.line.me/{self.liff_id}?family_id={family_id}" if family_id else f"https://liff.line.me/{self.liff_id}"
        return f"{base_domain}/dashboard?family_id={family_id}" if family_id else f"{base_domain}/dashboard"


@lru_cache
def get_settings() -> Settings:
    """單例設定。"""
    return Settings()  # type: ignore[call-arg]
