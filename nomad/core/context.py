"""Mobile context — battery, connectivity, time awareness."""
import asyncio
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class BatteryMode(Enum):
    FULL = "full"           # > 50% - all features, detailed responses
    BALANCED = "balanced"   # 20-50% - normal mode, reduced reasoning
    LOW_POWER = "low"       # 10-20% - minimal tools, short responses
    CRITICAL = "critical"   # < 10% - essential only, save power


@dataclass
class BatteryState:
    level: int              # 0-100
    charging: bool
    mode: BatteryMode

    @property
    def is_low(self) -> bool:
        return self.level < 20

    @property
    def max_tokens(self) -> int:
        if self.level > 50:
            return 4096
        elif self.level > 20:
            return 1024
        elif self.level > 10:
            return 256
        return 128


@dataclass
class ConnectivityState:
    online: bool
    network_type: str  # wifi, cellular, none


class MobileContext:
    """Reads mobile device state for battery-aware agent behavior."""

    def __init__(self):
        self._battery_cache: Optional[BatteryState] = None
        self._battery_cache_time: float = 0
        self._cache_ttl: float = 30  # seconds

    async def get_battery(self) -> BatteryState:
        """Get current battery state with caching."""
        now = time.time()
        if self._battery_cache and (now - self._battery_cache_time) < self._cache_ttl:
            return self._battery_cache

        level, charging = await self._read_battery()
        mode = self._level_to_mode(level)
        state = BatteryState(level=level, charging=charging, mode=mode)

        self._battery_cache = state
        self._battery_cache_time = now
        return state

    async def is_online(self) -> bool:
        """Check internet connectivity."""
        connectivity = await self._check_connectivity()
        return connectivity.online

    async def get_connectivity(self) -> ConnectivityState:
        """Get detailed connectivity state."""
        return await self._check_connectivity()

    def _level_to_mode(self, level: int) -> BatteryMode:
        if level > 50:
            return BatteryMode.FULL
        elif level > 20:
            return BatteryMode.BALANCED
        elif level > 10:
            return BatteryMode.LOW_POWER
        return BatteryMode.CRITICAL

    async def _read_battery(self) -> tuple[int, bool]:
        """Read battery level from system. Returns (level, charging)."""
        # Try Termux:API first (most reliable on Android)
        try:
            proc = await asyncio.create_subprocess_exec(
                "termux-battery-status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                import json
                data = json.loads(stdout.decode())
                return data.get("percentage", 50), data.get("status", "") == "CHARGING"
        except (FileNotFoundError, Exception):
            pass

        # Try /sys/class/power_supply (Linux standard)
        try:
            capacity_path = Path("/sys/class/power_supply/battery/capacity")
            status_path = Path("/sys/class/power_supply/battery/status")
            if capacity_path.exists():
                level = int(capacity_path.read_text().strip())
                charging = False
                if status_path.exists():
                    charging = status_path.read_text().strip() in ("Charging", "Full")
                return level, charging
        except Exception:
            pass

        # Fallback: assume balanced mode
        return 50, False

    async def _check_connectivity(self) -> ConnectivityState:
        """Check network connectivity."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "2", "1.1.1.1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            online = proc.returncode == 0
        except Exception:
            online = False

        network_type = "none"
        if online:
            # Detect wifi vs cellular
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ip", "route",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                route_info = stdout.decode()
                if "wlan" in route_info or "wifi" in route_info:
                    network_type = "wifi"
                elif "rmnet" in route_info or "ccmni" in route_info:
                    network_type = "cellular"
                else:
                    network_type = "unknown"
            except Exception:
                network_type = "unknown"

        return ConnectivityState(online=online, network_type=network_type)
