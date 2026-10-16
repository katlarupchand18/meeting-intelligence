from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx


logger = logging.getLogger(__name__)


class LLMService:
    """Local LLM service using Ollama and Qwen3."""

    def __init__(self) -> None:
        self.base_url = "http://127.0.0.1:11434"
        self.model = "qwen3:4b"
        self.timeout = 600.0

    def _chat(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        messages = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "think": False,
            "options": {
                "temperature": 0,
                "num_ctx": 8192,
                "num_predict": 2048,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )

                # Compatibility fallback if this Ollama version
                # does not accept the "think" parameter.
                if response.status_code == 400:
                    try:
                        error_data = response.json()
                        error_text = str(error_data.get("error", ""))
                    except ValueError:
                        error_text = response.text

                    if "think" in error_text.lower():
                        payload.pop("think", None)
                        response = client.post(
                            f"{self.base_url}/api/chat",
                            json=payload,
                        )

                response.raise_for_status()

        except httpx.ConnectError as exc:
            raise RuntimeError(
                "Cannot connect to Ollama at "
                f"{self.base_url}. Make sure Ollama is running."
            ) from exc

        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Ollama timed out after {self.timeout} seconds "
                f"while using model {self.model}."
            ) from exc

        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama API returned HTTP "
                f"{exc.response.status_code}: "
                f"{exc.response.text[:2000]}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "Ollama returned an invalid API response."
            ) from exc

        if data.get("error"):
            raise RuntimeError(
                f"Ollama error: {data['error']}"
            )

        message = data.get("message") or {}
        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            thinking = message.get("thinking", "")

            logger.error(
                "Ollama returned empty content. "
                "Model=%s, done_reason=%s, thinking_length=%s",
                self.model,
                data.get("done_reason"),
                len(thinking) if isinstance(thinking, str) else 0,
            )

            raise RuntimeError(
                "Ollama returned empty message content. "
                f"Model={self.model}, "
                f"done_reason={data.get('done_reason')!r}. "
                "Check Ollama logs and the model response."
            )

        logger.debug(
            "Ollama response received: model=%s, "
            "response_length=%s, done_reason=%s",
            self.model,
            len(content),
            data.get("done_reason"),
        )

        return content.strip()

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        return self._chat(
            prompt=prompt,
            system_prompt=system_prompt,
        )

    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        content = self._chat(
            prompt=prompt,
            system_prompt=system_prompt,
        )

        cleaned = self._clean_json_response(content)

        try:
            parsed = json.loads(cleaned)

        except json.JSONDecodeError as exc:
            logger.error(
                "Invalid JSON from Ollama. Error=%s, response=%r",
                exc,
                cleaned[:3000],
            )

            raise RuntimeError(
                "Ollama returned invalid JSON. "
                f"Parse error: {exc}. "
                f"Response excerpt: {cleaned[:1000]}"
            ) from exc

        if not isinstance(parsed, dict):
            raise RuntimeError(
                "Expected the LLM to return a JSON object, "
                f"but received {type(parsed).__name__}."
            )

        return parsed

    @staticmethod
    def _clean_json_response(content: str) -> str:
        content = content.strip()

        # Remove Markdown code fences.
        content = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            content,
            count=1,
            flags=re.IGNORECASE,
        )

        content = re.sub(
            r"\s*```\s*$",
            "",
            content,
            count=1,
        )

        content = content.strip()

        # Remove an accidental JSON label.
        if content.lower().startswith("json"):
            content = content[4:].strip()

        # Extract the outermost JSON object if extra text exists.
        start = content.find("{")
        end = content.rfind("}")

        if start != -1 and end > start:
            content = content[start : end + 1]

        return content.strip()


llm_service = LLMService()