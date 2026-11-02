from __future__ import annotations

import os

import httpx


class LLMError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(self):
        self.base_url = os.getenv("OPENAI_COMPAT_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("OPENAI_COMPAT_API_KEY", "")
        self.model = os.getenv("OPENAI_COMPAT_MODEL", "")
        if not self.api_key or not self.model:
            raise LLMError("Set OPENAI_COMPAT_API_KEY and OPENAI_COMPAT_MODEL in .env")

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "messages": messages, "tools": tools,
                          "tool_choice": "auto", "temperature": 0.2},
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"LLM returned HTTP {exc.response.status_code}") from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            # Never include raw response bodies or headers; they may contain credentials.
            raise LLMError(f"LLM request failed ({type(exc).__name__})") from exc

