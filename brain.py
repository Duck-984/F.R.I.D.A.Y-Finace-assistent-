"""
FRIDAY BRAIN — Multi-Agent Orchestration Pipeline.

Поток обработки:
1. FRIDAY CORE → классифицирует интент
2. Определяет цепочку агентов
3. Запускает каждого агента последовательно
4. COMMUNICATION AI → оформляет финальный ответ
5. Возвращает пользователю

Каждый агент получает:
- сообщение пользователя
- контекст (UserContext)
- данные из БД (db_data)
"""

import sys
import os
from datetime import datetime, date
from typing import Optional

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm import is_llm_available, get_llm
from agents.base import UserContext
from agents.core import FridayCore
from agents.analyst import FinanceAnalyst
from agents.strategist import SavingsStrategist
from agents.behavior import BehaviorAI
from agents.communicator import CommunicationAI


class FridayBrain:
    """Главный мозг FRIDAY — оркестрирует всех агентов"""

    def __init__(self, db_module):
        self.db = db_module
        self.use_llm = is_llm_available()

        # Инициализируем всех агентов
        self.core = FridayCore(use_llm=self.use_llm)
        self.analyst = FinanceAnalyst(use_llm=self.use_llm)
        self.strategist = SavingsStrategist(use_llm=self.use_llm)
        self.behavior = BehaviorAI(use_llm=self.use_llm)
        self.communicator = CommunicationAI(use_llm=self.use_llm)

        # Маппинг агентов
        self.agents = {
            "analyst": self.analyst,
            "strategist": self.strategist,
            "behavior": self.behavior,
            "communicator": self.communicator,
        }

        print(f"🧠 FRIDAY Brain initialized (LLM: {'✅' if self.use_llm else '⚠️ rule-based'})")

    def process(self, user_id: int, message: str, username: str = "", first_name: str = "") -> str:
        """
        Главный метод обработки сообщения.
        
        Args:
            user_id: Telegram user ID
            message: текст сообщения
            username: Telegram username
            first_name: имя пользователя
        
        Returns:
            str: финальный ответ для пользователя
        """
        # 1. Получаем контекст пользователя из БД
        context = self._build_context(user_id, username, first_name)

        # 2. Получаем данные из БД для анализа
        db_data = self._gather_db_data(user_id)

        # 3. FRIDAY CORE — классифицируем интент
        core_result = self.core.analyze(message, context, db_data)

        if core_result.action == "unknown":
            return self.communicator.wrap_response(
                self.core.build_final_response(message, core_result, [], context),
                mood="neutral"
            )

        # 4. Запускаем цепочку агентов
        pipeline = core_result.data.get("pipeline", [])
        agent_results = []

        for agent_key in pipeline:
            agent = self.agents.get(agent_key)
            if agent:
                result = agent.analyze(message, context, db_data)
                agent_results.append(result)

        # 5. COMMUNICATION AI — стилизуем ответ
        comm_result = self.communicator.analyze(message, context, db_data)

        # 6. FRIDAY CORE — собираем финальный ответ
        raw_response = self.core.build_final_response(
            message, core_result, agent_results, context
        )

        # 7. COMMUNICATION AI — оборачиваем в стиль
        mood = comm_result.data.get("mood", "neutral")
        final_response = self.communicator.wrap_response(raw_response, mood=mood)

        return final_response

    def _build_context(self, user_id: int, username: str, first_name: str) -> UserContext:
        """Строит контекст пользователя из БД"""
        self.db.ensure_user(user_id, username, first_name)

        balance = self.db.get_balance(user_id) or 0.0

        # Данные за текущий месяц
        now = datetime.now()
        monthly = self.db.get_month_summary(user_id, now.year, now.month)

        goals = self.db.get_goals(user_id) or []

        # Проверка бюджетных алертов
        budget_alerts = self._check_budget_alerts(user_id)

        return UserContext(
            user_id=user_id,
            username=username,
            first_name=first_name,
            balance=balance,
            monthly_income=monthly.get("income", 0.0),
            monthly_expense=monthly.get("expense", 0.0),
            active_goals=goals,
            budget_alerts=budget_alerts,
        )

    def _gather_db_data(self, user_id: int) -> dict:
        """Собирает все необходимые данные из БД"""
        now = datetime.now()

        # Статистика за текущий месяц
        monthly_stats = self.db.get_monthly_stats(user_id, now.year, now.month) or []

        # Статистика за прошлый месяц
        if now.month == 1:
            prev_year, prev_month = now.year - 1, 12
        else:
            prev_year, prev_month = now.year, now.month - 1
        prev_month_stats = self.db.get_monthly_stats(user_id, prev_year, prev_month) or []

        # Последние транзакции
        recent = self.db.get_transactions(user_id, limit=30) or []

        # Лимиты по категориям
        limits = self.db.get_budgets(user_id) or []
        category_limits = {b["category_name"]: b["limit_amount"] for b in limits}

        return {
            "monthly_stats": monthly_stats,
            "prev_month_stats": prev_month_stats,
            "recent_transactions": recent,
            "all_transactions": recent,
            "category_limits": category_limits,
        }

    def _check_budget_alerts(self, user_id: int) -> list:
        """Проверяет превышение бюджетных лимитов"""
        now = datetime.now()
        budgets = self.db.get_budgets(user_id) or []
        alerts = []

        for budget in budgets:
            cat_name = budget["category_name"]
            limit = budget["limit_amount"]
            spent = self.db.get_category_spending(user_id, cat_name, now.year, now.month)

            if spent and spent > limit:
                pct = (spent / limit) * 100
                alerts.append(
                    f"{budget.get('icon', '📊')} {cat_name}: {spent:,.0f} ₽ из {limit:,.0f} ₽ ({pct:.0f}%)"
                )

        return alerts

    def handle_transaction(
        self, user_id: int, amount: float, category_name: str,
        tx_type: str, note: str = "", username: str = "", first_name: str = ""
    ) -> str:
        """Обрабатывает добавление транзакции через весь пайплайн"""
        self.db.ensure_user(user_id, username, first_name)

        # Ищем ID категории по имени
        cat_type = "expense" if tx_type == "expense" else "income"
        categories = self.db.get_categories(cat_type)
        category_id = None
        for cat in categories:
            if cat["name"].lower() == category_name.lower():
                category_id = cat["id"]
                break

        if category_id is None:
            return f"❌ Категория «{category_name}» не найдена."

        # Добавляем транзакцию
        self.db.add_transaction(
            user_id=user_id,
            type=tx_type,
            amount=amount,
            category_id=category_id,
            note=note,
        )

        # Запускаем пайплайн анализа
        context = self._build_context(user_id, username, first_name)
        db_data = self._gather_db_data(user_id)

        # Анализируем после добавления
        core_result = self.core.analyze(f"{'Потратил' if tx_type == 'expense' else 'Получил'} {amount} ({category_name})", context, db_data)
        agent_results = []

        # FINANCE ANALYST + BEHAVIOR после расхода
        if tx_type == "expense":
            agent_results.append(self.analyst.analyze("", context, db_data))
            agent_results.append(self.behavior.analyze("", context, db_data))
        agent_results.append(self.strategist.analyze("", context, db_data))

        raw = self.core.build_final_response("", core_result, agent_results, context)
        comm = self.communicator.analyze("", context, db_data)
        mood = comm.data.get("mood", "neutral")

        return self.communicator.wrap_response(raw, mood=mood)

    def generate_report(self, user_id: int, username: str = "", first_name: str = "") -> str:
        """Генерирует полный отчёт"""
        context = self._build_context(user_id, username, first_name)
        db_data = self._gather_db_data(user_id)
        return self.analyst.generate_monthly_report(context, db_data)

    def suggest_goals(self, user_id: int, username: str = "", first_name: str = "") -> str:
        """Предлагает цели накопления"""
        context = self._build_context(user_id, username, first_name)
        return self.strategist.suggest_goal(context)

    @property
    def llm_status(self) -> str:
        if self.use_llm:
            return "✅ LLM mode — все 5 агентов на AI"
        return "⚠️ Rule-based mode — агенты работают на правилах (API-ключ не настроен)"