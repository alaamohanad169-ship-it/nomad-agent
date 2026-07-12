"""Nomad configuration."""
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

NOMAD_HOME = Path.home() / ".nomad"


@dataclass
class ModelConfig:
    name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str = ""
    max_tokens: int = 4096
    enabled: bool = True


@dataclass
class NomadConfig:
    battery_full: int = 50
    battery_balanced: int = 20
    battery_critical: int = 10
    default_provider: str = "deepseek"
    fallback_provider: str = "gemini"
    memory_max_conversations: int = 1000
    memory_search_limit: int = 10
    enable_tools: bool = True
    theme: str = "default"

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "NomadConfig":
        path = config_path or NOMAD_HOME / "config.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        config = cls()
        config.save(path)
        return config

    def save(self, path: Optional[Path] = None):
        path = path or NOMAD_HOME / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in self.__dict__.items()}, f, indent=2)
