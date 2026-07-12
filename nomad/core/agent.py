"""Nomad agent — battery-aware, offline-first AI agent."""
import time
import uuid
from typing import Optional

from nomad.config import NomadConfig
from nomad.core.context import MobileContext, BatteryMode
from nomad.memory.store import MemoryStore, Message
from nomad.models.router import ModelRouter, ModelResponse
from nomad.models.cache import ResponseCache


class NomadAgent:
    """Main Nomad agent with battery-aware behavior."""

    def __init__(self, config: Optional[NomadConfig] = None):
        self.config = config or NomadConfig.load()
        self.context = MobileContext()
        self.memory = MemoryStore()
        self.cache = ResponseCache()
        self.router = ModelRouter(cache=self.cache)
        self.session_id = str(uuid.uuid4())[:8]
        self._message_count = 0

    async def chat(self, user_message: str) -> str:
        """Process a user message and return response."""
        self._message_count += 1

        # 1. Get current context
        battery = await self.context.get_battery()
        online = await self.context.is_online()
        connectivity = await self.context.get_connectivity()

        # 2. Store user message
        self.memory.store(Message(
            role="user",
            content=user_message,
            timestamp=time.time(),
            session_id=self.session_id,
        ))

        # 3. Build messages for model
        messages = self._build_messages(user_message, battery)

        # 4. Select and call model
        response = await self.router.select(
            messages=messages,
            task_type=self._classify_task(user_message),
            battery_mode=battery.mode,
        )

        # 5. Store response
        self.memory.store(Message(
            role="assistant",
            content=response.content,
            timestamp=time.time(),
            session_id=self.session_id,
            metadata={"model": response.model, "cached": response.cached},
        ))

        return self._format_response(response, battery, connectivity)

    def _build_messages(self, user_message: str, battery) -> list[dict]:
        """Build message list for model."""
        messages = []

        # System prompt (battery-aware)
        system_parts = [
            "You are Nomad, a mobile-first AI assistant.",
            "Be concise and helpful. You run on a phone, so respect battery and data.",
        ]

        if battery.mode == BatteryMode.CRITICAL:
            system_parts.append(
                "CRITICAL BATTERY: Give extremely short answers. Skip reasoning."
            )
        elif battery.mode == BatteryMode.LOW_POWER:
            system_parts.append(
                "LOW BATTERY: Keep responses brief. No unnecessary detail."
            )

        messages.append({"role": "system", "content": " ".join(system_parts)})

        # Add recent context from memory
        recent = self.memory.recent(self.session_id, limit=5)
        for msg in recent:
            messages.append({"role": msg.role, "content": msg.content})

        # Add current message
        messages.append({"role": "user", "content": user_message})

        return messages

    def _classify_task(self, message: str) -> str:
        """Classify task type for model routing."""
        lower = message.lower()

        code_keywords = ["code", "function", "class", "debug", "error", "python", "script"]
        if any(kw in lower for kw in code_keywords):
            return "code"

        reasoning_keywords = ["why", "explain", "how does", "analyze", "compare"]
        if any(kw in lower for kw in reasoning_keywords):
            return "reasoning"

        return "chat"

    def _format_response(
        self, response: ModelResponse, battery, connectivity
    ) -> str:
        """Format response with status info."""
        parts = [response.content]

        # Add status footer
        status_parts = []
        if response.cached:
            status_parts.append("cached")
        status_parts.append(f"via {response.model}")

        if not connectivity.online:
            status_parts.append("offline")

        if battery.level < 30:
            status_parts.append(f"🔋 {battery.level}%")

        if status_parts:
            parts.append(f"\n— [{', '.join(status_parts)}]")

        return "\n".join(parts)

    def get_stats(self) -> dict:
        """Get agent statistics."""
        return {
            "session": self.session_id,
            "messages": self._message_count,
            "memory": self.memory.get_stats(),
            "cache": self.cache.stats(),
            "providers": self.router.list_providers(),
        }
