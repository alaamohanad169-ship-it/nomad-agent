"""Tool registry — discover, validate, and dispatch tools."""
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from enum import Enum


class ToolRisk(Enum):
    SAFE = "safe"         # Read-only, no side effects
    MODERATE = "moderate"  # File writes, network calls
    DANGEROUS = "dangerous"  # Shell commands, system changes


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict  # JSON Schema
    risk: ToolRisk = ToolRisk.SAFE
    handler: Optional[Callable] = None

    def to_openai(self) -> dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class ToolRegistry:
    """Register, discover, and dispatch tools."""

    def __init__(self):
        self._tools: dict[str, ToolSchema] = {}

    def register(self, schema: ToolSchema):
        """Register a tool."""
        self._tools[schema.name] = schema

    def get(self, name: str) -> Optional[ToolSchema]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[ToolSchema]:
        """List all registered tools."""
        return list(self._tools.values())

    def to_openai(self) -> list[dict]:
        """Get all tools in OpenAI format."""
        return [t.to_openai() for t in self._tools.values()]

    async def execute(self, name: str, args: dict) -> str:
        """Execute a tool by name."""
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"Unknown tool: {name}"})
        if not tool.handler:
            return json.dumps({"error": f"Tool {name} has no handler"})
        
        try:
            result = await tool.handler(**args)
            return result
        except Exception as e:
            return json.dumps({"error": str(e)})

    def by_risk(self, risk: ToolRisk) -> list[ToolSchema]:
        """Get tools by risk level."""
        return [t for t in self._tools.values() if t.risk == risk]


# Global registry
registry = ToolRegistry()
