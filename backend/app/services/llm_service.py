"""
Hybrid LLM Service supporting Groq, Ollama, and OpenAI-compatible APIs.

Provides unified interface for:
- Fast chat responses (streaming and sync)
- Structured JSON generation
- Provider fallback and health checking
- Connection pooling and timeout handling
"""

from __future__ import annotations

import json
import logging
import re
import time
from enum import Enum
from typing import Any, AsyncGenerator, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OLLAMA = "ollama"
    GROQ = "groq"
    OPENAI = "openai"


class LLMService:
    """
    Hybrid LLM service with Groq, Ollama, and OpenAI support.

    Features:
    - Configurable primary and fallback providers
    - Streaming and synchronous generation
    - JSON mode for structured output
    - Connection pooling
    - Health checks and provider failover
    - Timeout and retry handling
    """

    def __init__(self) -> None:
        # Provider configuration
        self.primary_provider = LLMProvider(settings.AI_PROVIDER.lower())
        self.fallback_provider = LLMProvider(settings.AI_FALLBACK_PROVIDER.lower())
        self.allow_cloud = settings.ALLOW_CLOUD_AI

        # Ollama settings
        self.ollama_base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.ollama_model = settings.OLLAMA_MODEL
        self.ollama_fast_model = settings.OLLAMA_FAST_MODEL
        self.ollama_num_ctx = settings.OLLAMA_NUM_CTX
        self.ollama_num_predict = settings.OLLAMA_NUM_PREDICT
        self.ollama_think = settings.OLLAMA_THINK

        # Groq settings
        self.groq_api_key = settings.GROQ_API_KEY
        self.groq_base_url = settings.GROQ_BASE_URL.rstrip("/")
        self.groq_chat_model = settings.GROQ_CHAT_MODEL
        self.groq_analysis_model = settings.GROQ_ANALYSIS_MODEL

        # OpenAI settings (legacy)
        self.openai_api_key = settings.OPENAI_API_KEY
        self.openai_base_url = settings.OPENAI_BASE_URL.rstrip("/")
        self.openai_model = settings.OPENAI_MODEL

        # Defaults
        self.timeout = 120.0
        self.max_retries = 2

        # HTTP client for connection pooling
        self._client: Optional[httpx.AsyncClient] = None

        # Provider health cache
        self._health_cache: dict[LLMProvider, tuple[bool, float]] = {}
        self._health_cache_ttl = 60.0  # seconds

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create reusable async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # =========================================================
    # PROVIDER HEALTH CHECKS
    # =========================================================

    async def check_provider_health(self, provider: LLMProvider) -> bool:
        """Check if a provider is healthy and available."""
        # Check cache
        if provider in self._health_cache:
            healthy, timestamp = self._health_cache[provider]
            if time.time() - timestamp < self._health_cache_ttl:
                return healthy

        healthy = False
        try:
            client = await self._get_client()

            if provider == LLMProvider.OLLAMA:
                response = await client.get(
                    f"{self.ollama_base_url}/api/tags",
                    timeout=5.0,
                )
                healthy = response.status_code == 200

            elif provider == LLMProvider.GROQ:
                if not self.groq_api_key:
                    healthy = False
                else:
                    response = await client.get(
                        f"{self.groq_base_url}/models",
                        headers={"Authorization": f"Bearer {self.groq_api_key}"},
                        timeout=5.0,
                    )
                    healthy = response.status_code == 200

            elif provider == LLMProvider.OPENAI:
                if not self.openai_api_key:
                    healthy = False
                else:
                    response = await client.get(
                        f"{self.openai_base_url}/models",
                        headers={"Authorization": f"Bearer {self.openai_api_key}"},
                        timeout=5.0,
                    )
                    healthy = response.status_code == 200

        except Exception as e:
            logger.debug(f"Health check failed for {provider}: {e}")
            healthy = False

        self._health_cache[provider] = (healthy, time.time())
        return healthy

    async def get_available_provider(
        self,
        prefer_fast: bool = False,
    ) -> LLMProvider:
        """Get the best available provider."""
        # Try primary first
        if await self.check_provider_health(self.primary_provider):
            return self.primary_provider

        # Try fallback
        if self.fallback_provider != self.primary_provider:
            if await self.check_provider_health(self.fallback_provider):
                logger.info(f"Falling back to {self.fallback_provider}")
                return self.fallback_provider

        # Try any available
        for provider in [LLMProvider.OLLAMA, LLMProvider.GROQ, LLMProvider.OPENAI]:
            if provider not in (self.primary_provider, self.fallback_provider):
                if await self.check_provider_health(provider):
                    logger.info(f"Using alternative provider: {provider}")
                    return provider

        # Default to primary even if unhealthy (will error on use)
        return self.primary_provider

    # =========================================================
    # PROVIDER-SPECIFIC IMPLEMENTATIONS
    # =========================================================

    def _build_ollama_payload(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        use_fast_model: bool = False,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Build request payload for Ollama."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model = self.ollama_fast_model if use_fast_model else self.ollama_model

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "think": self.ollama_think,
            "options": {
                "temperature": 0,
                "num_ctx": self.ollama_num_ctx,
                "num_predict": self.ollama_num_predict,
            },
        }

        if json_mode:
            payload["format"] = "json"

        return payload

    def _build_openai_payload(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        model: str | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Build request payload for OpenAI-compatible APIs (Groq, OpenAI)."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model or self.openai_model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self.ollama_num_predict,
            "stream": stream,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        return payload

    async def _chat_ollama_sync(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        use_fast_model: bool = False,
    ) -> str:
        """Synchronous chat with Ollama."""
        payload = self._build_ollama_payload(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=json_mode,
            use_fast_model=use_fast_model,
            stream=False,
        )

        client = await self._get_client()

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.post(
                    f"{self.ollama_base_url}/api/chat",
                    json=payload,
                )

                # Handle "think" parameter compatibility
                if response.status_code == 400:
                    error_data = response.json()
                    error_text = str(error_data.get("error", ""))
                    if "think" in error_text.lower() and "think" in payload:
                        payload.pop("think", None)
                        response = await client.post(
                            f"{self.ollama_base_url}/api/chat",
                            json=payload,
                        )

                response.raise_for_status()
                break

            except httpx.TimeoutException as exc:
                if attempt == self.max_retries:
                    raise RuntimeError(
                        f"Ollama timed out after {self.timeout} seconds "
                        f"while using model {payload['model']}."
                    ) from exc
                await asyncio.sleep(1 * (attempt + 1))

            except httpx.HTTPStatusError as exc:
                if attempt == self.max_retries:
                    raise RuntimeError(
                        f"Ollama API returned HTTP "
                        f"{exc.response.status_code}: "
                        f"{exc.response.text[:2000]}"
                    ) from exc
                await asyncio.sleep(1 * (attempt + 1))

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError("Ollama returned an invalid API response.") from exc

        if data.get("error"):
            raise RuntimeError(f"Ollama error: {data['error']}")

        message = data.get("message") or {}
        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            thinking = message.get("thinking", "")
            logger.error(
                "Ollama returned empty content. "
                "Model=%s, done_reason=%s, thinking_length=%s",
                payload["model"],
                data.get("done_reason"),
                len(thinking) if isinstance(thinking, str) else 0,
            )
            raise RuntimeError(
                "Ollama returned empty message content. "
                f"Model={payload['model']}, "
                f"done_reason={data.get('done_reason')!r}. "
                "Check Ollama logs and the model response."
            )

        logger.debug(
            "Ollama response received: model=%s, "
            "response_length=%s, done_reason=%s",
            payload["model"],
            len(content),
            data.get("done_reason"),
        )

        return content.strip()

    async def _chat_ollama_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        use_fast_model: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Stream chat with Ollama."""
        payload = self._build_ollama_payload(
            prompt=prompt,
            system_prompt=system_prompt,
            use_fast_model=use_fast_model,
            stream=True,
        )

        client = await self._get_client()

        try:
            async with client.stream(
                "POST",
                f"{self.ollama_base_url}/api/chat",
                json=payload,
            ) as response:
                if response.status_code == 400:
                    error_text = ""
                    async for chunk in response.aiter_text():
                        error_text += chunk
                    if "think" in error_text.lower() and "think" in payload:
                        payload.pop("think", None)
                        async with client.stream(
                            "POST",
                            f"{self.ollama_base_url}/api/chat",
                            json=payload,
                        ) as retry_response:
                            retry_response.raise_for_status()
                            async for chunk in retry_response.aiter_bytes():
                                yield self._parse_ollama_stream_chunk(chunk)
                            return
                else:
                    response.raise_for_status()

                async for chunk in response.aiter_bytes():
                    parsed = self._parse_ollama_stream_chunk(chunk)
                    if parsed:
                        yield parsed

        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.ollama_base_url}. "
                "Make sure Ollama is running."
            ) from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Ollama timed out after {self.timeout} seconds "
                f"while using model {payload['model']}."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama API returned HTTP "
                f"{exc.response.status_code}: "
                f"{exc.response.text[:2000]}"
            ) from exc

    @staticmethod
    def _parse_ollama_stream_chunk(chunk: bytes) -> str | None:
        """Parse a streaming chunk from Ollama."""
        try:
            text = chunk.decode("utf-8").strip()
            if not text:
                return None
            data = json.loads(text)
            message = data.get("message") or {}
            content = message.get("content")
            if content:
                return content
            return None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    async def _chat_openai_compatible_sync(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        provider: LLMProvider = LLMProvider.GROQ,
    ) -> str:
        """Synchronous chat with OpenAI-compatible API (Groq or OpenAI)."""
        if provider == LLMProvider.GROQ:
            api_key = self.groq_api_key
            base_url = self.groq_base_url
            model = self.groq_analysis_model
        else:
            api_key = self.openai_api_key
            base_url = self.openai_base_url
            model = self.openai_model

        if not api_key:
            raise RuntimeError(f"{provider.value} API key not configured.")

        payload = self._build_openai_payload(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=json_mode,
            model=model,
            stream=False,
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        client = await self._get_client()

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                break

            except httpx.TimeoutException as exc:
                if attempt == self.max_retries:
                    raise RuntimeError(f"{provider.value} API timed out.") from exc
                await asyncio.sleep(1 * (attempt + 1))

            except httpx.HTTPStatusError as exc:
                if attempt == self.max_retries:
                    raise RuntimeError(
                        f"{provider.value} API returned HTTP "
                        f"{exc.response.status_code}: {exc.response.text[:2000]}"
                    ) from exc
                await asyncio.sleep(1 * (attempt + 1))

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            raise RuntimeError(f"{provider.value} returned empty content.")

        return content.strip()

    async def _chat_openai_compatible_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        provider: LLMProvider = LLMProvider.GROQ,
    ) -> AsyncGenerator[str, None]:
        """Stream chat with OpenAI-compatible API."""
        if provider == LLMProvider.GROQ:
            api_key = self.groq_api_key
            base_url = self.groq_base_url
            model = self.groq_chat_model
        else:
            api_key = self.openai_api_key
            base_url = self.openai_base_url
            model = self.openai_model

        if not api_key:
            raise RuntimeError(f"{provider.value} API key not configured.")

        payload = self._build_openai_payload(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            stream=True,
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        client = await self._get_client()

        try:
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    parsed = self._parse_openai_stream_chunk(chunk)
                    if parsed:
                        yield parsed
        except httpx.ConnectError as exc:
            raise RuntimeError(f"Cannot connect to {provider.value} API.") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"{provider.value} API timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"{provider.value} API returned HTTP "
                f"{exc.response.status_code}: {exc.response.text[:2000]}"
            ) from exc

    @staticmethod
    def _parse_openai_stream_chunk(chunk: bytes) -> str | None:
        """Parse a streaming chunk from OpenAI-compatible API."""
        try:
            text = chunk.decode("utf-8").strip()
            if not text:
                return None
            for line in text.split("\n"):
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        return None
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        return content
            return None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    # =========================================================
    # PUBLIC METHODS
    # =========================================================

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        use_fast_model: bool = False,
    ) -> str:
        """Generate a response (sync wrapper for backward compatibility)."""
        import asyncio
        return asyncio.run(self.agenerate(prompt, system_prompt, use_fast_model))

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        use_fast_model: bool = False,
    ) -> str:
        """Generate a response asynchronously with automatic provider selection."""
        provider = await self.get_available_provider(prefer_fast=use_fast_model)

        try:
            if provider == LLMProvider.OLLAMA:
                return await self._chat_ollama_sync(
                    prompt, system_prompt, use_fast_model=use_fast_model
                )
            elif provider == LLMProvider.GROQ:
                return await self._chat_openai_compatible_sync(
                    prompt, system_prompt, provider=LLMProvider.GROQ
                )
            else:
                return await self._chat_openai_compatible_sync(
                    prompt, system_prompt, provider=LLMProvider.OPENAI
                )
        except Exception as e:
            logger.warning(f"Primary provider {provider} failed: {e}")
            # Try fallback
            if provider != self.fallback_provider:
                try:
                    if self.fallback_provider == LLMProvider.OLLAMA:
                        return await self._chat_ollama_sync(
                            prompt, system_prompt, use_fast_model=use_fast_model
                        )
                    elif self.fallback_provider == LLMProvider.GROQ:
                        return await self._chat_openai_compatible_sync(
                            prompt, system_prompt, provider=LLMProvider.GROQ
                        )
                    else:
                        return await self._chat_openai_compatible_sync(
                            prompt, system_prompt, provider=LLMProvider.OPENAI
                        )
                except Exception as fallback_e:
                    logger.error(f"Fallback provider also failed: {fallback_e}")
            raise

    async def astream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        use_fast_model: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Stream a response asynchronously with automatic provider selection."""
        provider = await self.get_available_provider(prefer_fast=use_fast_model)

        try:
            if provider == LLMProvider.OLLAMA:
                async for chunk in self._chat_ollama_stream(
                    prompt, system_prompt, use_fast_model=use_fast_model
                ):
                    yield chunk
            elif provider == LLMProvider.GROQ:
                async for chunk in self._chat_openai_compatible_stream(
                    prompt, system_prompt, provider=LLMProvider.GROQ
                ):
                    yield chunk
            else:
                async for chunk in self._chat_openai_compatible_stream(
                    prompt, system_prompt, provider=LLMProvider.OPENAI
                ):
                    yield chunk
        except Exception as e:
            logger.warning(f"Streaming provider {provider} failed: {e}")
            # Try fallback for streaming
            if provider != self.fallback_provider:
                try:
                    if self.fallback_provider == LLMProvider.OLLAMA:
                        async for chunk in self._chat_ollama_stream(
                            prompt, system_prompt, use_fast_model=use_fast_model
                        ):
                            yield chunk
                    elif self.fallback_provider == LLMProvider.GROQ:
                        async for chunk in self._chat_openai_compatible_stream(
                            prompt, system_prompt, provider=LLMProvider.GROQ
                        ):
                            yield chunk
                    else:
                        async for chunk in self._chat_openai_compatible_stream(
                            prompt, system_prompt, provider=LLMProvider.OPENAI
                        ):
                            yield chunk
                except Exception as fallback_e:
                    logger.error(f"Fallback streaming also failed: {fallback_e}")
            raise

    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Generate a JSON response (sync wrapper)."""
        import asyncio
        return asyncio.run(self.agenerate_json(prompt, system_prompt))

    async def agenerate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Generate a JSON response asynchronously."""
        provider = await self.get_available_provider()

        try:
            if provider == LLMProvider.OLLAMA:
                content = await self._chat_ollama_sync(
                    prompt, system_prompt, json_mode=True
                )
            elif provider == LLMProvider.GROQ:
                content = await self._chat_openai_compatible_sync(
                    prompt, system_prompt, json_mode=True, provider=LLMProvider.GROQ
                )
            else:
                content = await self._chat_openai_compatible_sync(
                    prompt, system_prompt, json_mode=True, provider=LLMProvider.OPENAI
                )
        except Exception as e:
            logger.warning(f"JSON generation provider {provider} failed: {e}")
            if provider != self.fallback_provider:
                try:
                    if self.fallback_provider == LLMProvider.OLLAMA:
                        content = await self._chat_ollama_sync(
                            prompt, system_prompt, json_mode=True
                        )
                    elif self.fallback_provider == LLMProvider.GROQ:
                        content = await self._chat_openai_compatible_sync(
                            prompt, system_prompt, json_mode=True, provider=LLMProvider.GROQ
                        )
                    else:
                        content = await self._chat_openai_compatible_sync(
                            prompt, system_prompt, json_mode=True, provider=LLMProvider.OPENAI
                        )
                except Exception as fallback_e:
                    logger.error(f"Fallback JSON generation also failed: {fallback_e}")
                    raise
            else:
                raise

        cleaned = self._clean_json_response(content)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(
                "Invalid JSON from LLM. Error=%s, response=%r",
                exc,
                cleaned[:3000],
            )
            raise RuntimeError(
                "LLM returned invalid JSON. "
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
        """Clean and extract JSON from LLM response."""
        content = content.strip()

        # Remove Markdown code fences
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

        # Remove accidental JSON label
        if content.lower().startswith("json"):
            content = content[4:].strip()

        # Extract outermost JSON object if extra text exists
        start = content.find("{")
        end = content.rfind("}")

        if start != -1 and end > start:
            content = content[start:end + 1]

        return content.strip()

    def get_provider_info(self) -> dict[str, Any]:
        """Get information about current provider configuration."""
        return {
            "primary_provider": self.primary_provider.value,
            "fallback_provider": self.fallback_provider.value,
            "allow_cloud": self.allow_cloud,
            "ollama_model": self.ollama_model,
            "ollama_fast_model": self.ollama_fast_model,
            "groq_chat_model": self.groq_chat_model if self.groq_api_key else "not configured",
            "groq_analysis_model": self.groq_analysis_model if self.groq_api_key else "not configured",
            "openai_model": self.openai_model if self.openai_api_key else "not configured",
        }


import asyncio

llm_service = LLMService()