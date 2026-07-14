# Nomad — Mobile-First AI Agent OS

Battery-aware, offline-first, privacy-sovereign AI agent built for Termux/Android.

Nomad runs a full agent stack on your phone — tools, memory, offline mode, battery throttling — without depending on cloud services. When you're offline, it falls back to cached responses and local knowledge. When you're online, it routes through free-tier model providers.

## Install

```bash
git clone https://github.com/alaamohanad169-ship-it/nomad-agent.git
cd nomad-agent
pip install -e .
```

## Quick Start

```bash
# Run in offline mode (no API key needed)
nomad chat

# Or configure an API key for full model access
export OPENROUTER_API_KEY="your-key"
nomad chat
```

## Features

| Feature | Status |
|---------|--------|
| Battery-aware agent loop | ✅ Throttles iterations in low power |
| Offline mode | ✅ Cached responses + local knowledge |
| Tool system | ✅ 7 tools: terminal, file ops, web, code exec |
| SQLite memory | ✅ FTS5 search across conversations |
| Response cache | ✅ Reuses recent responses |
| Free-tier model router | ✅ OpenRouter, DeepSeek, HuggingFace |
| Rich CLI | ✅ Interactive chat, stats, tool listing |

## Tools

| Tool | Risk | Description |
|------|------|-------------|
| `terminal` | dangerous | Run shell commands |
| `read_file` | safe | Read files with line numbers |
| `write_file` | moderate | Create/overwrite files |
| `search_files` | safe | Regex search across files |
| `web_search` | safe | DuckDuckGo search |
| `web_extract` | safe | Extract text from URLs |
| `execute_code` | dangerous | Run Python code |

## Offline Mode

When no API key is configured, Nomad enters offline mode:

- **Cached responses** — stores recent LLM responses for reuse
- **Knowledge base** — SQLite FTS5 index of conversation history
- **Local tools** — terminal, file ops, and code execution work without internet
- **Graceful fallback** — tells you what it can do offline

## Battery Awareness

Nomad reads your device's battery level and adjusts behavior:

- **FULL (100-50%)** — 10 tool iterations, full model selection
- **BALANCED (50-20%)** — 10 iterations, fastest models preferred
- **LOW (20-5%)** — 3 iterations, minimal API calls
- **CRITICAL (<5%)** — offline mode only

## Configuration

Config at `~/.nomad/config.toml`:

```toml
[agent]
max_iterations = 10
enable_tools = true

[model]
default_provider = "openrouter"

[offline]
enabled = true
cache_size = 1000
```

## Architecture

```
nomad/
├── core/
│   ├── agent.py       # Main agent loop + tool calling
│   ├── context.py     # Battery, connectivity, time awareness
│   └── offline.py     # Offline mode + knowledge base
├── models/
│   ├── router.py      # Free-tier model selection
│   └── cache.py       # Response cache
├── memory/
│   └── store.py       # SQLite + FTS5 memory
├── tools/
│   ├── registry.py    # Tool registration + dispatch
│   └── builtins/      # terminal, file, web, code_exec
├── main.py            # CLI entry point
└── config.py          # Configuration
```

## Philosophy

- **Battery-first** — battery level drives iteration budget, model selection, and tool limits
- **Offline-first** — works without internet, caches everything
- **Privacy-sovereign** — all data stays on-device, no telemetry
- **Free-tier** — uses only free model APIs (OpenRouter, DeepSeek, HuggingFace)
- **Minimal footprint** — single SQLite DB, no heavy dependencies

## License

MIT
