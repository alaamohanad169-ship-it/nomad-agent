# Nomad Architecture

**Mobile-First AI Agent OS** — designed from ground up for phone constraints.

## Core Principles

1. **Battery-aware** — Agent throttles itself based on charge level
2. **Offline-first** — Core works without internet, syncs when connected
3. **Privacy-sovereign** — All data stays on device, no cloud accounts required
4. **Resource-conscious** — Designed for 4GB RAM, limited storage
5. **Context-aware** — Location, time, connectivity, battery state

## Architecture

```
nomad/
├── core/                    # Agent loop (battery-aware, async)
│   ├── agent.py            # Main agent class
│   ├── loop.py             # Conversation loop with battery throttling
│   └── context.py          # Mobile context (battery, connectivity, time)
├── memory/                  # Local memory (SQLite + search)
│   ├── store.py            # SQLite storage
│   ├── search.py           # FTS5 search
│   └── embeddings.py       # Local embeddings (optional)
├── models/                  # Free-tier model router
│   ├── router.py           # Smart routing across free models
│   ├── cache.py            # Response caching (offline support)
│   └── providers/          # Provider adapters
│       ├── deepseek.py
│       ├── gemini.py
│       └── huggingface.py
├── tools/                   # Tool system
│   ├── registry.py         # Tool registration
│   └── builtins/           # Built-in tools
│       ├── terminal.py
│       ├── file.py
│       └── web.py
├── ui/                      # Terminal UI
│   └── tui.py              # Rich-based TUI
├── config.py               # Configuration
├── main.py                 # Entry point
└── pyproject.toml
```

## Core Agent Loop

```python
class NomadAgent:
    async def run(self, message: str) -> str:
        # 1. Check battery level
        battery = await self.context.get_battery()
        
        # 2. Adjust behavior based on battery
        if battery < 20:
            max_tokens = 256
            tools = self.essential_tools
        elif battery < 50:
            max_tokens = 1024
            tools = self.all_tools
        else:
            max_tokens = 4096
            tools = self.all_tools
        
        # 3. Check connectivity
        online = await self.context.is_online()
        if not online:
            return await self.offline_response(message)
        
        # 4. Route to best available model
        model = await self.router.select(
            task_type=self.classify_task(message),
            max_tokens=max_tokens
        )
        
        # 5. Generate response
        response = await model.generate(
            message=message,
            tools=tools,
            memory=self.memory.relevant(message)
        )
        
        # 6. Store in memory
        await self.memory.store(message, response)
        
        return response
```

## Battery-Aware Throttling

| Battery Level | Mode | Max Tokens | Tools | Reasoning |
|---------------|------|------------|-------|-----------|
| > 50% | Full | 4096 | All | Enabled |
| 20-50% | Balanced | 1024 | All | Disabled |
| < 20% | Low Power | 256 | Essential | Disabled |
| < 10% | Critical | 128 | None | Disabled |

## Model Router

Routes to the best free-tier model based on:
- Task type (code, chat, reasoning)
- Current battery level
- Connectivity status
- Model availability
- Response cache hit

Providers:
1. **DeepSeek** — Best for code, free tier available
2. **Gemini Flash** — Fast, free tier via OpenRouter
3. **HuggingFace** — Open models, free inference API
4. **Local** — Small local models (future)

## Memory System

SQLite-based local memory with:
- **Conversations** — Full chat history
- **Facts** — Extracted knowledge
- **Search** — FTS5 full-text search
- **Embeddings** — Optional semantic search (when battery allows)

All data stored in `~/.nomad/` — user owns everything.

## Context System

Mobile-aware context signals:
- **Battery** — Level, charging status, time since last charge
- **Connectivity** — Online/offline, network type (wifi/cellular)
- **Time** — Time of day, day of week, timezone
- **Location** — Optional, if user grants permission
- **Notifications** — Recent notification history (future)

## Offline Mode

When offline:
1. Use cached responses for common queries
2. Access local memory (SQLite)
3. Run local tools (terminal, file operations)
4. Queue messages for sync when reconnected
5. Notify user of degraded capabilities

## Privacy Model

- All data stored locally in `~/.nomad/`
- No cloud accounts required
- API calls go directly to model providers
- User can export/delete all data anytime
- No telemetry, no analytics, no tracking
