"""Nomad agent — battery-aware, tool-using AI agent with offline support."""

import asyncio
import json
import time
import uuid
from typing import Optional

import httpx

from nomad.config import NomadConfig
from nomad.core.context import MobileContext, BatteryMode
from nomad.core.offline import OfflineMode
from nomad.memory.store import MemoryStore, Message
from nomad.models.cache import ResponseCache
from nomad.tools.registry import registry, ToolRisk


class NomadAgent:
    """Main Nomad agent with tool support and offline capabilities."""

    def __init__(self, config: Optional[NomadConfig] = None, auto_tools: bool = True):
        self.config = config or NomadConfig.load()
        self.context = MobileContext()
        self.memory = MemoryStore()
        self.cache = ResponseCache()
        self.offline = OfflineMode()
        self.session_id = str(uuid.uuid4())[:8]
        self._message_count = 0

        # Load tools
        if auto_tools:
            import nomad.tools.builtins  # triggers registration

    async def chat(self, user_message: str, approve_callback=None) -> str:
        """Process a user message with tool calling loop and offline support."""
        self._message_count += 1

        # Get context
        battery = await self.context.get_battery()
        online = await self.context.is_online()

        # Store user message
        self.memory.store(Message(
            role="user",
            content=user_message,
            timestamp=time.time(),
            session_id=self.session_id,
        ))

        # Check offline mode
        if not online:
            return await self._handle_offline(user_message, battery)

        # Build initial messages
        messages = self._build_messages(user_message, battery)

        # Get tool schemas
        tools = registry.to_openai() if self.config.enable_tools else []

        # Tool calling loop (max 10 iterations, reduced in low power mode)
        max_iterations = 10 if battery.mode in (BatteryMode.FULL, BatteryMode.BALANCED) else 3

        for iteration in range(max_iterations):
            # Call model
            response = await self._call_model(messages, tools)

            # Check if response has tool calls
            if "tool_calls" in response:
                tool_calls = response["tool_calls"]

                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": response.get("content"),
                    "tool_calls": tool_calls,
                })

                # Execute each tool call
                for tc in tool_calls:
                    func_name = tc["function"]["name"]
                    try:
                        func_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        func_args = {}

                    # Check risk and ask for approval if needed
                    tool = registry.get(func_name)
                    if tool and tool.risk == ToolRisk.DANGEROUS and approve_callback:
                        approved = await approve_callback(func_name, func_args)
                        if not approved:
                            result = json.dumps({"error": "Tool call denied by user"})
                        else:
                            result = await registry.execute(func_name, func_args)
                    else:
                        result = await registry.execute(func_name, func_args)

                    # Add tool result
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

                continue  # Loop back for model to process results

            # No tool calls — we have the final response
            final_content = response.get("content", "")

            # Cache the response
            self.offline.cache_response(user_message, final_content)

            # Store in memory
            self.memory.store(Message(
                role="assistant",
                content=final_content,
                timestamp=time.time(),
                session_id=self.session_id,
                metadata={"model": self.config.default_provider, "iterations": iteration + 1},
            ))

            return self._format_response(final_content, battery)

        # Max iterations reached
        return self._format_response("[Max tool iterations reached]", battery)

    async def _handle_offline(self, user_message: str, battery) -> str:
        """Handle requests when offline."""
        # Try cached response first
        cached = self.offline.get_cached(user_message)
        if cached:
            return f"[cached] {cached}"

        # Try offline response
        offline_resp = self.offline.get_offline_response(user_message)

        # Check knowledge base
        knowledge = self.offline.search_knowledge(user_message, limit=5)
        if knowledge:
            offline_resp = offline_resp + "\n\nKnowledge from local memory:\n"
            for k in knowledge:
                offline_resp += f"- {k['topic']}: {k['content'][:150]}...\n"

        # Cache the offline response
        self.offline.cache_response(user_message, offline_resp)

        return self._format_response(offline_resp, battery)

    def _build_messages(self, user_message: str, battery) -> list[dict]:
        """Build message list with system prompt and context."""
        messages = []

        # System prompt
        system_parts = [
            "You are Nomad, a mobile-first AI assistant with access to tools and local knowledge.",
            "Use tools when they help answer the question and you are online.",
            "Be concise. You run on a phone — respect battery and data.",
        ]

        if battery.mode == BatteryMode.CRITICAL:
            system_parts.append("CRITICAL BATTERY: Skip tools, give short answers.")
        elif battery.mode == BatteryMode.LOW_POWER:
            system_parts.append("LOW BATTERY: Use tools only if essential.")

        # Add tool descriptions
        if self.config.enable_tools:
            tool_list = [f"- {t.name}: {t.description}" for t in registry.list_tools()]
            system_parts.append(f"\nAvailable tools:\n{"\n".join(tool_list)}")

        messages.append({"role": "system", "content": " ".join(system_parts)})

        # Add recent context from memory
        recent = self.memory.recent(self.session_id, limit=5)
        for msg in recent:
            messages.append({"role": msg.role, "content": msg.content})

        # Add current message
        messages.append({"role": "user", "content": user_message})

        return messages

    async def _call_model(self, messages: list[dict], tools: list[dict]) -> dict:
        """Call the model with messages and tools."""
        # Find the OpenRouter provider
        openrouter_key = None
        for provider_name in ["gemini", "llama"]:
            # Check env
            import os
            key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
            if key:
                openrouter_key = key
                break

        if not openrouter_key:
            return {"content": "No API key configured. Set OPENROUTER_API_KEY."}

        model = "nousresearch/hermes-3-llama-3.1-405b:free"
        url = "https://openrouter.ai/api/v1/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 1024,
        }
        if tools:
            payload["tools"] = tools

        # Retry on rate limits
        for attempt in range(3):
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {openrouter_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if resp.status_code == 429:
                    wait = 2 ** attempt * 3
                    await asyncio.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()

                choice = data["choices"][0]
                message = choice["message"]

                result = {}
                if message.get("content"):
                    result["content"] = message["content"]
                if message.get("tool_calls"):
                    result["tool_calls"] = message["tool_calls"]

                return result

        return {"content": "Rate limited. Try again later."}

    def _format_response(self, content: str, battery) -> str:
        """Format response with status footer."""
        parts = [content]

        status = []
        if battery.level < 30:
            status.append(f"🔋 {battery.level}%")

        if status:
            parts.append(f"\n— [{', '.join(status)}]")

        return "\n".join(parts)

    def get_stats(self) -> dict:
        """Get agent statistics."""
        return {
            "session": self.session_id,
            "messages": self._message_count,
            "memory": self.memory.get_stats(),
            "cache": self.cache.stats(),
            "offline_cache": self.offline.get_stats() if hasattr(self.offline, 'get_stats') else {},
            "tools": [t.name for t in registry.list_tools()],
        }