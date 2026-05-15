"""
Memory / RAG — контекстная память диалогов для FRIDAY.
Хранит последние N сообщений пользователя и ответов.
Используется агентами для понимания контекста.
"""
import sqlite3
from datetime import datetime
from typing import Optional
from config import DB_PATH, MEMORY_MAX_MESSAGES
from logger import log


class ConversationMemory:
    """Управление памятью диалогов."""

    def __init__(self, db_path: str = DB_PATH, max_messages: int = MEMORY_MAX_MESSAGES):
        self.db_path = db_path
        self.max_messages = max_messages

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def add(self, user_id: int, role: str, content: str):
        """Добавить сообщение в память."""
        with self._conn() as db:
            db.execute(
                "INSERT INTO conversation_memory (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content),
            )
            db.commit()

    def get_context(self, user_id: int, limit: int = None) -> list[dict]:
        """Получить последние N сообщений."""
        limit = limit or self.max_messages
        with self._conn() as db:
            rows = db.execute(
                "SELECT role, content FROM conversation_memory "
                "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def get_summary(self, user_id: int) -> str:
        """Сжатая сводка диалога для промпта."""
        msgs = self.get_context(user_id, limit=20)
        if not msgs:
            return ""

        lines = []
        for m in msgs:
            role_tag = "👤" if m["role"] == "user" else "🤖"
            text = m["content"][:120]
            lines.append(f"{role_tag} {text}")
        return "Предыдущий диалог:\n" + "\n".join(lines)

    def clear(self, user_id: int):
        """Очистить память пользователя."""
        with self._conn() as db:
            db.execute("DELETE FROM conversation_memory WHERE user_id = ?", (user_id,))
            db.commit()
        log.info("Память пользователя %d очищена", user_id)

    def trim(self, user_id: int):
        """Удалить старые сообщения сверх лимита."""
        with self._conn() as db:
            count = db.execute(
                "SELECT COUNT(*) as c FROM conversation_memory WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"]
            if count > self.max_messages:
                excess = count - self.max_messages
                db.execute(
                    "DELETE FROM conversation_memory WHERE id IN ("
                    "  SELECT id FROM conversation_memory "
                    "  WHERE user_id = ? ORDER BY created_at ASC LIMIT ?"
                    ")",
                    (user_id, excess),
                )
                db.commit()
                log.debug("Память пользователя %d: удалено %d старых сообщений", user_id, excess)


# Глобальный экземпляр
memory = ConversationMemory()
