"""Response cache for offline support."""
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

from nomad.config import NOMAD_HOME


class ResponseCache:
    """Cache model responses for offline use."""

    def __init__(self, db_path: Optional[Path] = None, ttl: int = 86400):
        self.db_path = db_path or NOMAD_HOME / "cache.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl  # 24 hours default
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    model TEXT,
                    timestamp REAL NOT NULL,
                    hits INTEGER DEFAULT 0
                )
            """)

    def _make_key(self, messages: list[dict], model: str) -> str:
        """Create cache key from messages and model."""
        content = json.dumps({"messages": messages, "model": model}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, messages: list[dict], model: str) -> Optional[str]:
        """Get cached response if valid."""
        key = self._make_key(messages, model)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT response, timestamp FROM cache WHERE key = ?", (key,)
            ).fetchone()
            
            if row and (time.time() - row[1]) < self.ttl:
                conn.execute(
                    "UPDATE cache SET hits = hits + 1 WHERE key = ?", (key,)
                )
                return row[0]
        return None

    def set(self, messages: list[dict], model: str, response: str):
        """Cache a response."""
        key = self._make_key(messages, model)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, response, model, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (key, response, model, time.time())
            )

    def stats(self) -> dict:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            hits = conn.execute("SELECT SUM(hits) FROM cache").fetchone()[0] or 0
        return {"entries": total, "total_hits": hits}
