"""SQLite-based local memory for Nomad."""
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from nomad.config import NOMAD_HOME


@dataclass
class Message:
    role: str           # user, assistant, system
    content: str
    timestamp: float
    session_id: str
    metadata: Optional[dict] = None


class MemoryStore:
    """Local SQLite memory with FTS5 search."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or NOMAD_HOME / "memory.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    session_id TEXT NOT NULL,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    source TEXT,
                    timestamp REAL NOT NULL,
                    importance REAL DEFAULT 0.5
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                    content,
                    content=messages,
                    content_rowid=id
                );

                CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                END;

                CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content) 
                    VALUES ('delete', old.id, old.content);
                END;

                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
                CREATE INDEX IF NOT EXISTS idx_facts_timestamp ON facts(timestamp);
            """)

    def store(self, message: Message):
        """Store a message."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (role, content, timestamp, session_id, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                (message.role, message.content, message.timestamp,
                 message.session_id, json.dumps(message.metadata) if message.metadata else None)
            )

    def search(self, query: str, limit: int = 10) -> list[Message]:
        """Full-text search messages."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp, session_id, metadata "
                "FROM messages_fts "
                "JOIN messages ON messages.id = messages_fts.rowid "
                "WHERE messages_fts MATCH ? "
                "ORDER BY rank "
                "LIMIT ?",
                (query, limit)
            ).fetchall()
        
        return [
            Message(
                role=r[0], content=r[1], timestamp=r[2],
                session_id=r[3], metadata=json.loads(r[4]) if r[4] else None
            )
            for r in rows
        ]

    def recent(self, session_id: str, limit: int = 20) -> list[Message]:
        """Get recent messages for a session."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp, session_id, metadata "
                "FROM messages "
                "WHERE session_id = ? "
                "ORDER BY timestamp DESC "
                "LIMIT ?",
                (session_id, limit)
            ).fetchall()
        
        return [
            Message(
                role=r[0], content=r[1], timestamp=r[2],
                session_id=r[3], metadata=json.loads(r[4]) if r[4] else None
            )
            for r in reversed(rows)
        ]

    def store_fact(self, content: str, source: str = "", importance: float = 0.5):
        """Store an extracted fact."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO facts (content, source, timestamp, importance) "
                "VALUES (?, ?, ?, ?)",
                (content, source, time.time(), importance)
            )

    def search_facts(self, query: str, limit: int = 5) -> list[dict]:
        """Search facts by relevance."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT content, source, importance "
                "FROM facts "
                "WHERE content LIKE ? "
                "ORDER BY importance DESC, timestamp DESC "
                "LIMIT ?",
                (f"%{query}%", limit)
            ).fetchall()
        
        return [{"content": r[0], "source": r[1], "importance": r[2]} for r in rows]

    def get_stats(self) -> dict:
        """Get memory statistics."""
        with sqlite3.connect(self.db_path) as conn:
            messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            facts = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            sessions = conn.execute(
                "SELECT COUNT(DISTINCT session_id) FROM messages"
            ).fetchone()[0]
        
        return {
            "messages": messages,
            "facts": facts,
            "sessions": sessions,
            "db_size_mb": round(self.db_path.stat().st_size / 1024 / 1024, 2)
        }

    def cleanup(self, max_messages: int = 1000):
        """Remove old messages beyond limit per session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM messages WHERE id NOT IN (
                    SELECT id FROM messages 
                    GROUP BY session_id 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                )
            """, (max_messages,))
