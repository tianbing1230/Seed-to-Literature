from __future__ import annotations

import json
import os
from typing import Any

from ..clients._http import json_post


class LLMClient:
    def __init__(self, provider: str, model: str) -> None:
        self.provider = provider
        self.model = model
        self.base_url, self.api_key = self._resolve_provider(provider)

    @staticmethod
    def _resolve_provider(provider: str) -> tuple[str, str]:
        key_provider = provider.strip().lower()
        if key_provider == "openrouter":
            return "https://openrouter.ai/api/v1/chat/completions", os.getenv("OPENROUTER_API_KEY", "").strip()
        if key_provider == "openai":
            return "https://api.openai.com/v1/chat/completions", os.getenv("OPENAI_API_KEY", "").strip()
        raise ValueError(f"Unsupported LLM provider: {provider}")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def chat_json(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "error": "missing_api_key_or_model"}

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        resp = json_post(self.base_url, payload, headers=headers)
        if not isinstance(resp, dict):
            return {"ok": False, "error": "http_failure"}
        choices = resp.get("choices")
        usage = resp.get("usage") or {}
        if not isinstance(choices, list) or not choices:
            return {"ok": False, "error": "empty_choices", "usage": usage}
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            return {"ok": False, "error": "invalid_content", "usage": usage}
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {"ok": False, "error": "invalid_json_content", "raw_content": content, "usage": usage}
        return {"ok": True, "data": parsed, "usage": usage}

