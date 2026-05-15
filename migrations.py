"""
Миграции базы данных FRIDAY.
Автоматически применяются при запуске — добавляет индексы и новые колонки.
"""
import sqlite3
from logger import log


MIGRATIONS = [
    # v1 → v2: индексы для быстрых запросов
    """
    CREATE INDEX IF NOT EXISTS idx_tx_user_date
        ON transactions(user_id, date);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_tx_category
        ON transactions(category_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_goals_user
        ON goals(user_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_budgets_user
        ON budgets(user_id, category_id);
    """,
    # v2 → v3: таблица памяти диалогов
    """
    CREATE TABLE IF NOT EXISTS conversation_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_user
        ON conversation_memory(user_id, created_at);
    """,
    # v3 → v4: таблица health-чеков
    """
    CREATE TABLE IF NOT EXISTS health_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service TEXT NOT NULL,
        status TEXT NOT NULL,
        latency_ms REAL,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
]


def run_migrations(db_path: str):
    """Применить все миграции к БД."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    applied = 0
    for i, sql in enumerate(MIGRATIONS):
        try:
            conn.execute(sql)
            applied += 1
        except sqlite3.OperationalError as e:
            log.warning("Миграция %d пропущена: %s", i + 1, e)

    conn.commit()
    conn.close()
    log.info("Миграции: применено %d/%d", applied, len(MIGRATIONS))
