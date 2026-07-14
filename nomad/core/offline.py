"""Offline mode — cached responses and local knowledge."""
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

from nomad.config import NOMAD_HOME


class OfflineMode:
    """Handle responses when offline or rate-limited."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or NOMAD_HOME / "offline.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cached_responses (
                    query_hash TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    hits INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT,
                    timestamp REAL NOT NULL
                )
            """)

    def get_cached(self, query: str) -> Optional[str]:
        """Get a cached response for similar queries."""
        import hashlib
        query_hash = hashlib.sha256(query.lower().strip().encode()).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT response, timestamp FROM cached_responses WHERE query_hash = ?",
                (query_hash,)
            ).fetchone()

            if row and (time.time() - row[1]) < 86400:  # 24h cache
                conn.execute(
                    "UPDATE cached_responses SET hits = hits + 1 WHERE query_hash = ?",
                    (query_hash,)
                )
                return row[0]
        return None

    def cache_response(self, query: str, response: str):
        """Cache a response for offline use."""
        import hashlib
        query_hash = hashlib.sha256(query.lower().strip().encode()).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cached_responses (query_hash, response, timestamp) "
                "VALUES (?, ?, ?)",
                (query_hash, response, time.time())
            )

    def add_knowledge(self, topic: str, content: str, source: str = ""):
        """Add knowledge for offline reference."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO knowledge (topic, content, source, timestamp) VALUES (?, ?, ?, ?)",
                (topic, content, source, time.time())
            )

    def search_knowledge(self, query: str, limit: int = 3) -> list[dict]:
        """Search local knowledge base."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT topic, content, source FROM knowledge "
                "WHERE topic LIKE ? OR content LIKE ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit)
            ).fetchall()

        return [{"topic": r[0], "content": r[1], "source": r[2]} for r in rows]

    def get_stats(self) -> dict:
        """Get offline mode statistics."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT COUNT(*) FROM cached_responses").fetchone()
            rows2 = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()
        return {
            "cached_responses": rows[0] if rows else 0,
            "knowledge_entries": rows2[0] if rows2 else 0,
        }

    def get_offline_response(self, query: str) -> str:
        """Generate a response when offline."""
        # Check cache first
        cached = self.get_cached(query)
        if cached:
            return f"[cached] {cached}"

        # Check knowledge base
        knowledge = self.search_knowledge(query, limit=5)
        if knowledge:
            parts = ["I found this in my local knowledge:\n"]
            for k in knowledge:
                parts.append(f"**{k['topic']}**: {k['content'][:200]}")
            return "\n".join(parts)

        # Generic offline response
        return (
            "I'm currently offline and don't have a cached response for this.\n\n"
            "What I can do offline:\n"
            "- Search my memory for previous conversations\n"
            "- Run terminal commands\n"
            "- Read and write files\n\n"
            "Connect to the internet or configure an API key for full capabilities."
        )
