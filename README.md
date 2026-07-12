# 🏕️ Nomad

**Mobile-first AI agent OS** — battery-aware, offline-first, privacy-sovereign.

## What is Nomad?

Nomad is an AI agent designed from the ground up for mobile devices. While other agents assume desktop/server resources, Nomad treats phone constraints as first-class design requirements.

### Core Principles

1. **Battery-aware** — Throttles itself based on charge level. Deep thinking when charging, lightweight on battery.
2. **Offline-first** — Core works without internet. Caches responses, uses local memory.
3. **Privacy-sovereign** — All data stays on device. No cloud accounts required.
4. **Resource-conscious** — Designed for 4GB RAM, limited storage.
5. **Context-aware** — Knows battery, connectivity, time. Adapts behavior accordingly.

## Quick Start

```bash
# Install
pip install -e .

# Setup API keys
nomad setup

# Chat
nomad chat
```

## Battery Modes

| Battery | Mode | Max Tokens | Behavior |
|---------|------|------------|----------|
| > 50% | Full | 4096 | All features, detailed responses |
| 20-50% | Balanced | 1024 | Normal mode, reduced reasoning |
| 10-20% | Low Power | 256 | Minimal tools, short responses |
| < 10% | Critical | 128 | Essential only, save power |

## Model Providers

Nomad routes to the best free-tier model:

- **DeepSeek** — Best for code tasks
- **Gemini Flash** — Fast, good for chat
- **HuggingFace** — Open models (coming soon)

Set API keys:
```bash
export DEEPSEEK_API_KEY="your-key"
export OPENROUTER_API_KEY="your-key"
```

## Memory

All data stored locally in `~/.nomad/`:
- `memory.db` — Conversations and facts
- `cache.db` — Response cache for offline use
- `config.json` — Your settings

## Architecture

```
nomad/
├── core/           # Agent loop, context, battery awareness
├── memory/         # SQLite memory with FTS5 search
├── models/         # Free-tier model router + cache
├── tools/          # Tool system (coming soon)
├── ui/             # Terminal interface
└── config.py       # Configuration
```

## Why Nomad?

Every other AI agent assumes you have a server. Nomad assumes you have a phone.

- **Hermes** — Great agent, but designed for desktop. Runs on mobile via Termux, but doesn't adapt to mobile constraints.
- **ChatGPT/Claude** — Cloud-only. No sovereignty. Data leaves your device.
- **Nomad** — Built for mobile from day one. Battery-aware. Offline-capable. Your data stays yours.

## License

MIT
