"""
FINANCE ANALYST AI — финансовый аналитик.

Функции:
- Анализ расходов по категориям
- Поиск «сливов денег»
- Расчёт баланса
- Формирование отчётов
- Сравнение с предыдущими периодами
"""

from datetime import datetime, timedelta
from .base import BaseAgent, AgentResult, UserContext


class FinanceAnalyst(BaseAgent):
    name = "FINANCE ANALYST"
    role = "analyst"
    emoji = "📊"

    system_prompt = """Ты — финансовый аналитик FRIDAY.
Твоя задача: анализировать доходы и расходы пользователя.
Ты находишь паттерны трат, «сливы денег», аномалии.
Ты работаешь ТОЛЬКО с реальными данными из БД.
Ты не придумываешь цифры. Только факты."""

    def _rule_analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        """
        Анализирует финансовые данные:
        - db_data['monthly_stats']: статистика по категориям за месяц
        - db_data['recent_transactions']: последние транзакции
        - db_data['category_limits']: лимиты по категориям
        - db_data['prev_month_stats']: статистика за прошлый месяц (если есть)
        """
        insights = []
        data = {}

        # 1. Базовая статистика
        stats = db_data.get("monthly_stats", [])
        if stats:
            total_expense = sum(s["total"] for s in stats)
            data["total_expense"] = total_expense
            data["category_breakdown"] = stats

            # Топ-3 категорий расходов
            top3 = sorted(stats, key=lambda x: x["total"], reverse=True)[:3]
            top3_text = "\n".join(
                f"  {s['icon']} {s['name']}: {s['total']:,.0f} ₽ ({s['total']/total_expense*100:.0f}%)"
                for s in top3 if s['total'] > 0
            )
            if top3_text:
                insights.append(f"📊 Топ трат:\n{top3_text}")

            # Сравнение с прошлым месяцем
            prev_stats = db_data.get("prev_month_stats", [])
            if prev_stats:
                prev_total = sum(s["total"] for s in prev_stats)
                if prev_total > 0:
                    change = ((total_expense - prev_total) / prev_total) * 100
                    arrow = "🔴" if change > 0 else "🟢"
                    insights.append(
                        f"{arrow} vs прошлый месяц: {'+' if change > 0 else ''}{change:.0f}%"
                    )

        # 2. «Сливы денег» — категории без лимита с высокими тратами
        limits = db_data.get("category_limits", {})
        for s in stats:
            cat_name = s["name"]
            if cat_name in limits and s["total"] > limits[cat_name]:
                over = s["total"] - limits[cat_name]
                insights.append(
                    f"⚠️ {s['icon']} {cat_name}: перерасход на {over:,.0f} ₽ (лимит {limits[cat_name]:,.0f})"
                )
                data.setdefault("over_budget", []).append({
                    "category": cat_name,
                    "spent": s["total"],
                    "limit": limits[cat_name],
                    "over": over
                })

        # 3. Аномалии — поиск нетипично крупных транзакций
        recent = db_data.get("recent_transactions", [])
        if recent and len(recent) >= 5:
            expenses = [t for t in recent if t.get("type") == "expense"]
            if expenses:
                avg = sum(abs(t["amount"]) for t in expenses) / len(expenses)
                big = [t for t in expenses if abs(t["amount"]) > avg * 2.5]
                if big:
                    data["anomalies"] = big
                    insights.append(
                        f"🔍 Крупные траты ({len(big)}): " +
                        ", ".join(f"{t.get('category_name', '?')} {abs(t['amount']):,.0f}₽" for t in big)
                    )

        # 4. Баланс
        data["balance"] = context.balance

        return AgentResult(
            agent=self.name,
            action="analyze",
            data=data,
            insights=insights,
            confidence=0.9 if stats else 0.3
        )

    def generate_monthly_report(self, context: UserContext, db_data: dict) -> str:
        """Генерирует полноценный месячный отчёт"""
        stats = db_data.get("monthly_stats", [])
        if not stats:
            return "📊 Нет данных за этот месяц."

        total_income = context.monthly_income
        total_expense = context.monthly_expense
        balance = total_income - total_expense

        lines = ["📊 **Финансовый отчёт**\n"]
        lines.append(f"💰 Доходы: {total_income:,.0f} ₽")
        lines.append(f"💸 Расходы: {total_expense:,.0f} ₽")
        lines.append(f"{'🟢' if balance >= 0 else '🔴'} Баланс: {balance:,.0f} ₽\n")

        # Категории с прогресс-барами
        max_total = max(s["total"] for s in stats) if stats else 1
        lines.append("📂 **По категориям:**")
        for s in sorted(stats, key=lambda x: x["total"], reverse=True):
            if s["total"] == 0:
                continue
            pct = s["total"] / total_expense * 100 if total_expense > 0 else 0
            bar_len = int(s["total"] / max_total * 10)
            bar = "█" * bar_len + "░" * (10 - bar_len)
            lines.append(f"{s['icon']} {s['name']}: {bar} {pct:.0f}% ({s['total']:,.0f} ₽)")

        # Совет
        savings_rate = (total_income - total_expense) / total_income * 100 if total_income > 0 else 0
        if savings_rate < 10:
            lines.append(f"\n💡 Ты откладываешь всего {savings_rate:.0f}% дохода. Рекомендую минимум 20%.")

        return "\n".join(lines)

    def _llm_analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        client = self.get_llm_client()
        if not client:
            return self._rule_analyze(message, context, db_data)

        prompt = f"""{self.system_prompt}

Контекст:
- Баланс: {context.balance:,.0f} ₽
- Доходы: {context.monthly_income:,.0f} ₽
- Расходы: {context.monthly_expense:,.0f} ₽
- Статистика: {db_data.get('monthly_stats', [])}

Проанализируй финансы пользователя. Найди:
1. Топ-3 категорий трат
2. Перерасходы по лимитам
3. Аномалии (нетипично крупные траты)
4. Динамику vs прошлый месяц

Верни JSON: {{"insights": ["...", "..."], "warnings": ["..."], "top_categories": [...], "anomalies": [...]}}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300
            )
            import json
            result = json.loads(response.choices[0].message.content)
            return AgentResult(
                agent=self.name,
                action="analyze",
                data=result,
                insights=result.get("insights", []),
                confidence=0.85
            )
        except Exception as e:
            return AgentResult(agent=self.name, action="error", error=str(e), confidence=0)