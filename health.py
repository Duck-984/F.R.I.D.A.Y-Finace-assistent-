"""Health check endpoint + мониторинг метрик."""
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime

from config import DB_PATH
from logger import log


@dataclass
class HealthStatus:
    db_ok: bool = False
    db_latency_ms: float = 0
    bot_running: bool = False
    last_check: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return self.db_ok and self.bot_running and not self.errors


def check_db() -> tuple[bool, float]:
    """Проверить БД и замерить latency."""
    start = time.monotonic()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
        latency = (time.monotonic() - start) * 1000
        return True, latency
    except Exception as e:
        log.error(f"DB health check failed: {e}")
        return False, 0


def health_check() -> HealthStatus:
    """Полная проверка здоровья системы."""
    status = HealthStatus(last_check=datetime.now().isoformat())
    status.db_ok, status.db_latency_ms = check_db()
    status.bot_running = True  # Если код выполняется — бот жив

    if not status.db_ok:
        status.errors.append("Database unreachable")
    if status.db_latency_ms > 100:
        status.errors.append(f"Database slow: {status.db_latency_ms:.0f}ms")

    log.info(f"Health check: {'OK' if status.healthy else 'DEGRADED'} "
             f"(db={status.db_latency_ms:.0f}ms, errors={len(status.errors)})")
    return status
