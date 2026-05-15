"""
BEHAVIOR AI — анализ привычек и поведения.

Функции:
- Изучает поведение пользователя
- Выявляет паттерны: траты по дням недели, импульсивные покупки
- Находит триггеры перерасходов
- Даёт персональные рекомендации по изменению привычек
"""

from datetime import datetime, date, timedelta
from collections import defaultdict
from .base import BaseAgent, AgentResult, UserContext


class BehaviorAI(BaseAgent):
    name = "BEHAVIOR AI"
    role = "behavior_analyst"
    emoji = "🧩"

    system_prompt = """Ты — поведенческий аналитик FRIDAY.
Ты изучаешь финансовые привычки пользователя.
Ты находишь паттерны: в какие дни тратит больше, какие категории растут.
Ты выявляешь импульсивные покупки.
Твоя цель — помочь изменить вредные финансовые привычки."""

    # Дни недели на русском
    WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    def _rule_analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        insights = []
        data = {}

        recent = db_data.get("recent_transactions", [])
        all_transactions = db_data.get("all_transactions", [])

        if not recent and not all_transactions:
            return AgentResult(
                agent=self.name,
                action="analyze_behavior",
                data={},
                insights=["📊 Пока недостаточно данных для анализа привычек. Нужно минимум 10 транзакций."],
                confidence=0.2
            )

        # 1. Паттерны по дням недели
        data["weekday_pattern"] = self._analyze_weekdays(all_transactions or recent)
        if data["weekday_pattern"]:
            insights.append(self._format_weekday_insight(data["weekday_pattern"]))

        # 2. Импульсивные покупки
        data["impulse"] = self._detect_impulse(recent)
        if data["impulse"]:
            insights.append(self._format_impulse_insight(data["impulse"]))

        # 3. Паттерн «маленьких трат»
        data["micro_spending"] = self._analyze_micro_spending(all_transactions or recent)
        if data["micro_spending"]:
            insights.append(data["micro_spending"])

        # 4. Частота транзакций
        data["frequency"] = self._analyze_frequency(all_transactions or recent)
        if data["frequency"]:
            insights.append(data["frequency"])

        return AgentResult(
            agent=self.name,
            action="analyze_behavior",
            data=data,
            insights=insights,
            confidence=0.7 if len(all_transactions or recent) >= 10 else 0.4
        )

    def _analyze_weekdays(self, transactions: list) -> dict:
        """Анализ трат по дням недели"""
        if not transactions:
            return {}

        by_day = defaultdict(float)
        by_day_count = defaultdict(int)

        for tx in transactions:
            if tx.get("type") != "expense":
                continue
            try:
                tx_date = tx.get("date", "")
                if isinstance(tx_date, str):
                    dt = datetime.strptime(tx_date, "%Y-%m-%d")
                else:
                    dt = tx_date
                day_idx = dt.weekday()
                by_day[day_idx] += abs(tx.get("amount", 0))
                by_day_count[day_idx] += 1
            except (ValueError, TypeError):
                continue

        if not by_day:
            return {}

        max_day = max(by_day, key=by_day.get)
        min_day = min(by_day, key=by_day.get)

        return {
            "by_day": {self.WEEKDAYS[k]: v for k, v in sorted(by_day.items())},
            "max_day": self.WEEKDAYS[max_day],
            "max_amount": by_day[max_day],
            "min_day": self.WEEKDAYS[min_day],
            "min_amount": by_day[min_day],
            "counts": {self.WEEKDAYS[k]: v for k, v in sorted(by_day_count.items())},
        }

    def _format_weekday_insight(self, pattern: dict) -> str:
        max_day = pattern.get("max_day", "?")
        max_amt = pattern.get("max_amount", 0)
        min_day = pattern.get("min_day", "?")
        counts = pattern.get("counts", {})

        lines = [f"📅 Анализ по дням недели:"]
        for day, total in sorted(pattern.get("by_day", {}).items()):
            cnt = counts.get(day, 0)
            lines.append(f"  {day}: {total:,.0f} ₽ ({cnt} покупок)")

        if max_amt > 0:
            lines.append(f"\n🔴 Пик трат: {max_day} ({max_amt:,.0f} ₽)")
            lines.append(f"🟢 Минимум трат: {min_day}")

        return "\n".join(lines)

    def _detect_impulse(self, transactions: list) -> list:
        """Находит импульсивные покупки"""
        impulse_categories = {"Развлечения", "Кафе/Рестораны", "Одежда", "Техника"}
        impulse = []

        for tx in transactions:
            if tx.get("type") != "expense":
                continue
            cat_name = tx.get("category_name", "")
            amount = abs(tx.get("amount", 0))
            if cat_name in impulse_categories and amount > 0:
                impulse.append({"category": cat_name, "amount": amount, "date": tx.get("date")})

        return impulse[-7:]  # Последние 7

    def _format_impulse_insight(self, impulse: list) -> str:
        if not impulse:
            return ""
        total = sum(i["amount"] for i in impulse)
        by_cat = defaultdict(float)
        for i in impulse:
            by_cat[i["category"]] += i["amount"]

        lines = [f"⚡ Импульсивные траты (7 дней): {total:,.0f} ₽"]
        for cat, amt in sorted(by_cat.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  • {cat}: {amt:,.0f} ₽")

        if total > 5000:
            lines.append("💡 Попробуй правило 24 часов: перед покупкой >1000₽ жди сутки.")
        return "\n".join(lines)

    def _analyze_micro_spending(self, transactions: list) -> str:
        """Находит «эффект латте» — много мелких трат"""
        expenses = [
            abs(tx["amount"])
            for tx in transactions
            if tx.get("type") == "expense"
        ]
        if not expenses:
            return ""

        micro = [e for e in expenses if e < 500]
        if len(micro) >= 5:
            total_micro = sum(micro)
            return (
                f"☕ Эффект латте: {len(micro)} мелких трат (<500₽) на сумму {total_micro:,.0f} ₽\n"
                f"   В месяц это ~{total_micro * 4:,.0f} ₽ — подумай, всё ли из этого действительно нужно."
            )
        return ""

    def _analyze_frequency(self, transactions: list) -> str:
        """Анализ частоты транзакций"""
        expenses = [
            tx for tx in transactions
            if tx.get("type") == "expense"
        ]
        if len(expenses) < 5:
            return ""

        # Группируем по датам
        dates = defaultdict(int)
        for tx in expenses:
            try:
                d = tx.get("date", "")
                if isinstance(d, str):
                    d = d[:10]
                else:
                    d = str(d)[:10]
                dates[d] += 1
            except (ValueError, TypeError):
                continue

        avg_per_day = len(expenses) / max(len(dates), 1)
        if avg_per_day >= 3:
            return (
                f"📈 Высокая частота: ~{avg_per_day:.1f} покупок в день.\n"
                "   Попробуй объединять мелкие покупки в одну."
            )
        return ""

    def _llm_analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        client = self.get_llm_client()
        if not client:
            return self._rule_analyze(message, context, db_data)

        # Передаём только агрегированные данные, не все транзакции
        prompt = f"""{self.system_prompt}

Контекст:
- Доходы: {context.monthly_income:,.0f} ₽
- Расходы: {context.monthly_expense:,.0f} ₽
- Последние транзакции: {db_data.get('recent_transactions', [])[:20]}

Проанализируй поведение пользователя:
1. Паттерны по дням недели
2. Импульсивные покупки
3. Вредные привычки

Верни JSON: {{"insights": ["..."], "patterns": [...], "recommendations": ["..."]}}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=350
            )
            import json
            result = json.loads(response.choices[0].message.content)
            return AgentResult(
                agent=self.name,
                action="analyze_behavior",
                data=result,
                insights=result.get("insights", []),
                confidence=0.75
            )
        except Exception as e:
            return AgentResult(agent=self.name, action="error", error=str(e), confidence=0)