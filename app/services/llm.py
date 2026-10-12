"""Gemini 共用 client。"""

from __future__ import annotations

from google import genai

from app.config import get_settings

_client: genai.Client | None = None


def gemini() -> genai.Client:
    """全域 Gemini client。"""
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_settings().gemini_api_key)
    return _client
