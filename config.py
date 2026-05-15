"""
FRIDAY Configuration — всё через переменные окружения.
Скопируй .env.example в .env и заполни.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ── Telegram ──────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ── Database ──────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "finance.db"))

# ── AI / LLM ──────────────────────────────────────────
AI_ENABLED = os.getenv("AI_ENABLED", "true").lower() == "true"
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.3"))
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "400"))

# ── Logging ───────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "friday.log"))

# ── Memory ────────────────────────────────────────────
MEMORY_MAX_MESSAGES = int(os.getenv("MEMORY_MAX_MESSAGES", "50"))
MEMORY_ENABLED = os.getenv("MEMORY_ENABLED", "true").lower() == "true"

# ── Categories ────────────────────────────────────────
DEFAULT_CATEGORIES = {
    "expense": [
        ("🍔", "Еда"),
        ("🚗", "Транспорт"),
        ("🏠", "Жильё"),
        ("🎮", "Развлечения"),
        ("💊", "Здоровье"),
        ("📚", "Образование"),
        ("👕", "Одежда"),
        ("💻", "Техника"),
        ("📦", "Прочее"),
        ("☕️", "Кафе/Рестораны"),
    ],
    "income": [
        ("💼", "Зарплата"),
        ("🎁", "Подарок"),
        ("📈", "Инвестиции"),
        ("💸", "Фриланс"),
        ("📦", "Прочее"),
    ],
}
