"""
Модуль базы данных — SQLite
Таблицы: users, transactions, goals, budgets
"""

import sqlite3
import csv
import io
from datetime import datetime, date
import config


def get_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Создать таблицы и заполнить категории по умолчанию."""
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                currency TEXT DEFAULT '₽',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                icon TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                UNIQUE(icon, name, type)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                amount REAL NOT NULL,
                category_id INTEGER,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );

            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                target_amount REAL NOT NULL,
                current_amount REAL DEFAULT 0,
                deadline DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                monthly_limit REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (category_id) REFERENCES categories(id),
                UNIQUE(user_id, category_id)
            );

            CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_goals_user ON goals(user_id);
            CREATE INDEX IF NOT EXISTS idx_budgets_user ON budgets(user_id);
        """)

        # Заполнить категории, если таблица пуста
        count = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count == 0:
            for cat_type, items in config.DEFAULT_CATEGORIES.items():
                for icon, name in items:
                    db.execute(
                        "INSERT INTO categories (icon, name, type) VALUES (?, ?, ?)",
                        (icon, name, cat_type),
                    )


# ─── Пользователи ───────────────────────────────────────────────

def ensure_user(user_id: int, username: str = "", first_name: str = ""):
    with get_db() as db:
        db.execute(
            "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name",
            (user_id, username, first_name),
        )


# ─── Категории ──────────────────────────────────────────────────

def get_categories(cat_type: str):
    with get_db() as db:
        return db.execute(
            "SELECT id, icon, name FROM categories WHERE type=? ORDER BY id", (cat_type,)
        ).fetchall()


def get_category_name(category_id: int) -> str:
    with get_db() as db:
        row = db.execute("SELECT name FROM categories WHERE id=?", (category_id,)).fetchone()
    return row["name"] if row else "?"


# ─── Транзакции ─────────────────────────────────────────────────

def add_transaction(user_id: int, tx_type: str, amount: float, category_id: int, description: str = ""):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO transactions (user_id, type, amount, category_id, description) VALUES (?, ?, ?, ?, ?)",
            (user_id, tx_type, amount, category_id, description),
        )
        tx_id = cur.lastrowid
        # Обновить цели (пополнение)
        if tx_type == "income":
            db.execute(
                "UPDATE goals SET current_amount = current_amount + ? WHERE user_id = ? AND current_amount < target_amount",
                (amount, user_id),
            )
        return tx_id


def delete_transaction(user_id: int, tx_id: int) -> bool:
    """Удалить транзакцию. Возвращает True если удалено."""
    with get_db() as db:
        # Сначала получаем данные для отката целей
        tx = db.execute(
            "SELECT type, amount FROM transactions WHERE id=? AND user_id=?", (tx_id, user_id)
        ).fetchone()
        if not tx:
            return False
        db.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (tx_id, user_id))
        # Откатить цели если это был доход
        if tx["type"] == "income":
            db.execute(
                "UPDATE goals SET current_amount = MAX(0, current_amount - ?) WHERE user_id = ?",
                (tx["amount"], user_id),
            )
    return True


def update_transaction(user_id: int, tx_id: int, amount: float = None,
                       category_id: int = None, description: str = None) -> bool:
    """Обновить поля транзакции. Возвращает True если обновлено."""
    with get_db() as db:
        tx = db.execute(
            "SELECT * FROM transactions WHERE id=? AND user_id=?", (tx_id, user_id)
        ).fetchone()
        if not tx:
            return False

        old_amount = tx["amount"]
        new_amount = amount if amount is not None else old_amount
        new_cat = category_id if category_id is not None else tx["category_id"]
        new_desc = description if description is not None else tx["description"]

        db.execute(
            "UPDATE transactions SET amount=?, category_id=?, description=? WHERE id=? AND user_id=?",
            (new_amount, new_cat, new_desc, tx_id, user_id),
        )

        # Скорректировать цели при изменении дохода
        if tx["type"] == "income":
            diff = new_amount - old_amount
            if diff != 0:
                db.execute(
                    "UPDATE goals SET current_amount = MAX(0, current_amount + ?) WHERE user_id = ?",
                    (diff, user_id),
                )
    return True


def get_transaction(user_id: int, tx_id: int):
    """Получить одну транзакцию."""
    with get_db() as db:
        return db.execute(
            """SELECT t.id, t.type, t.amount, c.icon, c.name as category, t.description, t.created_at
               FROM transactions t JOIN categories c ON t.category_id = c.id
               WHERE t.id=? AND t.user_id=?""",
            (tx_id, user_id),
        ).fetchone()


def get_balance(user_id: int) -> float:
    with get_db() as db:
        income = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=? AND type='income'", (user_id,)
        ).fetchone()[0]
        expense = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=? AND type='expense'", (user_id,)
        ).fetchone()[0]
    return income - expense


def get_recent(user_id: int, limit: int = 10):
    with get_db() as db:
        return db.execute(
            """SELECT t.id, t.type, t.amount, c.icon, c.name as category, t.description, t.created_at
               FROM transactions t JOIN categories c ON t.category_id = c.id
               WHERE t.user_id=? ORDER BY t.created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()


def get_monthly_stats(user_id: int, year: int, month: int):
    with get_db() as db:
        rows = db.execute(
            """SELECT c.icon, c.name, SUM(t.amount) as total
               FROM transactions t JOIN categories c ON t.category_id = c.id
               WHERE t.user_id=? AND t.type='expense'
                 AND strftime('%Y', t.created_at)=? AND strftime('%m', t.created_at)=?
               GROUP BY c.id ORDER BY total DESC""",
            (user_id, str(year), f"{month:02d}"),
        ).fetchall()
        total_income = db.execute(
            """SELECT COALESCE(SUM(amount),0) FROM transactions
               WHERE user_id=? AND type='income'
                 AND strftime('%Y', created_at)=? AND strftime('%m', created_at)=?""",
            (user_id, str(year), f"{month:02d}"),
        ).fetchone()[0]
        total_expense = db.execute(
            """SELECT COALESCE(SUM(amount),0) FROM transactions
               WHERE user_id=? AND type='expense'
                 AND strftime('%Y', created_at)=? AND strftime('%m', created_at)=?""",
            (user_id, str(year), f"{month:02d}"),
        ).fetchone()[0]
    return rows, total_income, total_expense


def get_daily_average(user_id: int, days: int = 30):
    with get_db() as db:
        row = db.execute(
            """SELECT COALESCE(SUM(amount)/?, 0) FROM transactions
               WHERE user_id=? AND type='expense' AND created_at >= date('now', ?)""",
            (days, user_id, f"-{days} days"),
        ).fetchone()
    return row[0]


def get_top_expenses(user_id: int, limit: int = 5):
    with get_db() as db:
        return db.execute(
            """SELECT c.icon, c.name, SUM(t.amount) as total
               FROM transactions t JOIN categories c ON t.category_id = c.id
               WHERE t.user_id=? AND t.type='expense'
                 AND t.created_at >= date('now', '-30 days')
               GROUP BY c.id ORDER BY total DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()


# ─── Экспорт ────────────────────────────────────────────────────

def export_csv(user_id: int) -> str:
    """Экспортировать все транзакции пользователя в CSV-строку."""
    with get_db() as db:
        rows = db.execute(
            """SELECT t.id, t.type, t.amount, c.icon || ' ' || c.name as category,
                      t.description, t.created_at
               FROM transactions t JOIN categories c ON t.category_id = c.id
               WHERE t.user_id=? ORDER BY t.created_at DESC""",
            (user_id,),
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Тип", "Сумма", "Категория", "Описание", "Дата"])
    for r in rows:
        writer.writerow([r["id"], r["type"], r["amount"], r["category"],
                         r["description"], r["created_at"]])
    return output.getvalue()


def export_all_for_ai(user_id: int) -> list[dict]:
    """Все транзакции пользователя в виде списка словарей для AI-анализа."""
    with get_db() as db:
        rows = db.execute(
            """SELECT t.type, t.amount, c.icon, c.name as category, t.description, t.created_at
               FROM transactions t JOIN categories c ON t.category_id = c.id
               WHERE t.user_id=? ORDER BY t.created_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ─── Цели ───────────────────────────────────────────────────────

def add_goal(user_id: int, name: str, target: float, deadline: str = None):
    with get_db() as db:
        db.execute(
            "INSERT INTO goals (user_id, name, target_amount, deadline) VALUES (?, ?, ?, ?)",
            (user_id, name, target, deadline),
        )


def get_goals(user_id: int):
    with get_db() as db:
        return db.execute(
            "SELECT * FROM goals WHERE user_id=? ORDER BY created_at DESC", (user_id,)
        ).fetchall()


def get_total_saved(user_id: int) -> float:
    with get_db() as db:
        row = db.execute(
            "SELECT COALESCE(SUM(current_amount), 0) FROM goals WHERE user_id=?", (user_id,)
        ).fetchone()
    return row[0]


# ─── Бюджеты (лимиты) ───────────────────────────────────────────

def set_budget(user_id: int, category_id: int, monthly_limit: float):
    """Установить или обновить месячный лимит по категории."""
    with get_db() as db:
        db.execute(
            """INSERT INTO budgets (user_id, category_id, monthly_limit)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, category_id) DO UPDATE SET monthly_limit=excluded.monthly_limit""",
            (user_id, category_id, monthly_limit),
        )


def get_budgets(user_id: int):
    """Получить все лимиты пользователя с текущими тратами за месяц."""
    with get_db() as db:
        return db.execute(
            """SELECT b.id, c.icon, c.name, b.monthly_limit,
                      COALESCE(
                        (SELECT SUM(t.amount) FROM transactions t
                         WHERE t.user_id=b.user_id AND t.category_id=b.category_id
                           AND t.type='expense'
                           AND strftime('%Y-%m', t.created_at)=strftime('%Y-%m', 'now')),
                        0
                      ) as spent
               FROM budgets b JOIN categories c ON b.category_id = c.id
               WHERE b.user_id=? ORDER BY c.name""",
            (user_id,),
        ).fetchall()


def delete_budget(user_id: int, budget_id: int) -> bool:
    with get_db() as db:
        cur = db.execute("DELETE FROM budgets WHERE id=? AND user_id=?", (budget_id, user_id))
        return cur.rowcount > 0


def check_budget_alerts(user_id: int) -> list[str]:
    """Проверить превышения лимитов. Возвращает список предупреждений."""
    budgets = get_budgets(user_id)
    alerts = []
    for b in budgets:
        if b["monthly_limit"] > 0 and b["spent"] > b["monthly_limit"]:
            over = b["spent"] - b["monthly_limit"]
            pct = (b["spent"] / b["monthly_limit"] * 100) - 100
            alerts.append(
                f"⚠️ {b['icon']} *{b['name']}*: превышен на `{over:,.0f}` ₽ (+{pct:.0f}%) — "
                f"лимит `{b['monthly_limit']:,.0f}`, потрачено `{b['spent']:,.0f}` ₽"
            )
        elif b["monthly_limit"] > 0 and b["spent"] > b["monthly_limit"] * 0.8:
            left = b["monthly_limit"] - b["spent"]
            alerts.append(
                f"⚡ {b['icon']} *{b['name']}*: осталось `{left:,.0f}` ₽ из `{b['monthly_limit']:,.0f}` ₽"
            )
    return alerts
