"""Smart model router — picks the best free-tier model for each task."""
import os
from typing import Optional
from dataclasses import dataclass

import httpx

from nomad.core.context import BatteryMode
from nomad.models.cache import ResponseCache


@dataclass
class ModelResponse:
    content: str
    model: str
    tokens_used: int = 0
    cached: bool = False


class ModelRouter:
    """Routes requests to the best available free-tier model."""

    def __init__(self, cache: Optional[ResponseCache] = None):
        self.cache = cache or ResponseCache()
        self.providers = self._init_providers()

    def _init_providers(self) -> dict:
        """Initialize available providers from env vars."""
        providers = {}

        # DeepSeek (free tier via API key)
        deepseek_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
        if deepseek_key:
            providers["deepseek"] = {
                "key": deepseek_key,
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "strengths": ["code", "reasoning"],
            }

        # OpenRouter (Gemini Flash free)
        openrouter_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        if openrouter_key:
            providers["gemini"] = {
                "key": openrouter_key,
                "base_url": "https://openrouter.ai/api/v1",
                "model": "nousresearch/hermes-3-llama-3.1-405b:free",
                "strengths": ["chat", "fast", "reasoning"],
            }
            providers["llama"] = {
                "key": openrouter_key,
                "base_url": "https://openrouter.ai/api/v1",
                "model": "meta-llama/llama-3.3-70b-instruct:free",
                "strengths": ["chat", "code"],
            }

        # HuggingFace (free inference API)
        hf_key = (os.getenv("HF_API_KEY") or os.getenv("HUGGING_FACE_HUB_TOKEN") or "").strip()
        if hf_key:
            providers["huggingface"] = {
                "key": hf_key,
                "base_url": "https://api-inference.huggingface.co/models/",
                "model": "meta-llama/Llama-3-8B-Instruct",
                "strengths": ["chat"],
            }

        return providers

    async def select(
        self,
        messages: list[dict],
        task_type: str = "chat",
        battery_mode: BatteryMode = BatteryMode.FULL,
        preferred: Optional[str] = None,
    ) -> ModelResponse:
        """Select best model and generate response."""

        # Check cache first
        if self.cache:
            cached = self.cache.get(messages, "any")
            if cached:
                return ModelResponse(content=cached, model="cache", cached=True)

        # If no providers configured, use offline response
        if not self.providers:
            return ModelResponse(
                content=self._offline_response(messages),
                model="offline",
            )

        # Select provider based on task type and battery mode
        provider_name = self._select_provider(task_type, battery_mode, preferred)
        provider = self.providers[provider_name]

        # Generate response
        try:
            response = await self._call_provider(provider, messages)
            
            # Cache the response
            if self.cache and response:
                self.cache.set(messages, provider_name, response)

            return ModelResponse(content=response, model=provider_name)
        except Exception as e:
            # Try fallback
            fallback = self._get_fallback(provider_name)
            if fallback and fallback in self.providers:
                response = await self._call_provider(
                    self.providers[fallback], messages
                )
                return ModelResponse(content=response, model=fallback)
            
            return ModelResponse(
                content=f"Error: {str(e)}. No fallback available.",
                model="error",
            )

    def _select_provider(
        self, task_type: str, battery_mode: BatteryMode, preferred: Optional[str]
    ) -> str:
        """Select best provider for task."""
        if preferred and preferred in self.providers:
            return preferred

        # Battery-aware selection
        if battery_mode == BatteryMode.CRITICAL:
            # Use fastest model to save battery
            for name, p in self.providers.items():
                if "fast" in p.get("strengths", []):
                    return name

        # Task-based selection
        candidates = []
        for name, p in self.providers.items():
            if task_type in p.get("strengths", []):
                candidates.append(name)

        if candidates:
            return candidates[0]

        # Default to first available
        return next(iter(self.providers))

    def _get_fallback(self, current: str) -> Optional[str]:
        """Get fallback provider."""
        for name in self.providers:
            if name != current:
                return name
        return None

    async def _call_provider(self, provider: dict, messages: list[dict]) -> str:
        """Call a model provider with retry on rate limits."""
        import asyncio
        
        for attempt in range(3):
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{provider['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {provider['key']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": provider["model"],
                        "messages": messages,
                        "max_tokens": 1024,
                    },
                )
                
                if response.status_code == 429:
                    wait = 2 ** attempt * 3  # 3s, 6s, 12s
                    await asyncio.sleep(wait)
                    continue
                
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        
        raise Exception("Rate limited after 3 retries")

    def _offline_response(self, messages: list[dict]) -> str:
        """Generate offline response when no providers available."""
        last_msg = messages[-1]["content"] if messages else ""
        return (
            f"I'm currently offline and can't connect to any AI models.\n\n"
            f"Your message: {last_msg}\n\n"
            f"Connect to the internet or configure an API key to use Nomad.\n"
            f"Set DEEPSEEK_API_KEY or OPENROUTER_API_KEY in your environment."
        )

    def list_providers(self) -> list[dict]:
        """List available providers."""
        return [
            {"name": name, "model": p["model"], "strengths": p.get("strengths", [])}
            for name, p in self.providers.items()
        ]
