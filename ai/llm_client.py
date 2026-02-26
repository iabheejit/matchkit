"""Unified LLM client for all AI features in MatchKit.

Supports Azure OpenAI (default) and standard OpenAI as fallback.
All AI services use this client for chat completions.
"""
import logging
import time
from typing import Any, Dict, List, Optional

from openai import AzureOpenAI, OpenAI
from config.settings import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM client with retry logic and structured output support."""

    def __init__(self):
        self.client = None
        self.model = settings.azure_openai_chat_deployment

        if settings.azure_openai_endpoint and settings.azure_openai_api_key:
            self.client = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version="2024-06-01",
            )
            logger.info(f"LLM client initialized (Azure OpenAI, model={self.model})")
        else:
            logger.warning("Azure OpenAI not configured — AI features will use fallback responses")

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        retries: int = 3,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Send a chat completion request and return the assistant's response text."""
        if not self.client:
            return None

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        for attempt in range(1, retries + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                return content.strip() if content else None
            except Exception as e:
                logger.warning(f"LLM chat attempt {attempt}/{retries} failed: {e}")
                if attempt < retries:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"LLM chat failed after {retries} attempts: {e}")
                    return None

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Optional[Dict]:
        """Chat completion that returns parsed JSON."""
        import json

        raw = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            return None


# Singleton
llm_client = LLMClient()
