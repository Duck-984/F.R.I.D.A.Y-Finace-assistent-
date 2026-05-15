"""
SAVINGS STRATEGIST AI — стратег накоплений.

Функции:
- Помогает копить деньги
- Строит план накоплений
- Говорит сколько откладывать
- Прогнозирует достижение целей
- Анализирует реалистичность целей
"""

from datetime import datetime, date
from .base import BaseAgent, AgentResult, UserContext


class SavingsStrategist(BaseAgent):
    name = "SAVINGS STRATEGIST"
    role = "strategist"
    emoji = "🎯"

    system_prompt = """Ты — стратег накоплений FRIDAY.
Твоя задача: помочь пользователю копить деньги.
Ты строишь реалистичные планы, считаешь сроки, мотивируешь.
Ты учитываешь доходы и расходы — не предлагаешь нереальное."""

    def _rule_analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        insights = []
        data = {}

        goals = context.active_goals
        monthly_savings = context.monthly_income - context.monthly_expense

        # 1. Анализ активных целей
        if goals:
            for goal in goals:
                name = goal.get("name", "Цель")
                target = goal.get("target_amount", 0)
                current = goal.get("current_amount", 0)
                remaining = target - current
                deadline = goal.get("deadline")
                monthly_contribution = goal.get("monthly_contribution", 0)

                progress_pct = (current / target * 100) if target > 0 else 0

                data[f"goal_{goal.get('id')}"] = {
                    "name": name,
                    "progress": progress_pct,
                    "remaining": remaining,
                    "monthly_needed": monthly_contribution
                }

                # Расчёт достижимости
                if deadline:
                    try:
                        dl = datetime.strptime(deadline, "%Y-%m-%d").date()
                        months_left = max(1, (dl - date.today()).days / 30)
                        needed_monthly = remaining / months_left

                        if needed_monthly <= monthly_savings:
                            insights.append(
                                f"🎯 {name}: {progress_pct:.0f}% (осталось {remaining:,.0f} ₽)\n"
                                f"   Нужно {needed_monthly:,.0f} ₽/мес — ✅ реально"
                            )
                        else:
                            gap = needed_monthly - monthly_savings
                            insights.append(
                                f"🎯 {name}: {progress_pct:.0f}%\n"
                                f"   ⚠️ Нужно {needed_monthly:,.0f} ₽/мес, а свободных только {monthly_savings:,.0f}\n"
                                f"   Дефицит: {gap:,.0f} ₽/мес. Нужно увеличить доход или сдвинуть срок."
                            )
                    except (ValueError, TypeError):
                        insights.append(f"🎯 {name}: {progress_pct:.0f}% (осталось {remaining:,.0f} ₽)")
                else:
                    if monthly_savings > 0:
                        months_to_goal = remaining / monthly_savings
                        insights.append(
                            f"🎯 {name}: {progress_pct:.0f}% — при текущем темпе цель через {months_to_goal:.0f} мес."
                        )
                    else:
                        insights.append(f"🎯 {name}: {progress_pct:.0f}% — нет свободных средств для накопления.")

        # 2. Общая стратегия
        if monthly_savings <= 0:
            insights.append("⚠️ Расходы превышают доходы. Накопления невозможны без сокращения трат.")
        elif monthly_savings > 0 and not goals:
            insights.append(
                f"💡 У тебя {monthly_savings:,.0f} ₽ свободных в месяц. "
                "Поставь цель — и я помогу её достичь: /goal"
            )

        # 3. Правило 50/30/20
        if context.monthly_income > 0:
            needs = context.monthly_income * 0.5
            wants = context.monthly_income * 0.3
            savings_target = context.monthly_income * 0.2
            actual_savings_rate = (monthly_savings / context.monthly_income * 100)

            data["rule_50_30_20"] = {
                "needs": needs,
                "wants": wants,
                "savings_target": savings_target,
                "actual_savings": monthly_savings,
                "savings_rate": actual_savings_rate
            }

            if actual_savings_rate < 20:
                insights.append(
                    f"📐 Правило 50/30/20: ты откладываешь {actual_savings_rate:.0f}% "
                    f"(рекомендуется 20% = {savings_target:,.0f} ₽)"
                )

        return AgentResult(
            agent=self.name,
            action="strategize",
            data=data,
            insights=insights,
            confidence=0.85 if goals else 0.5
        )

    def suggest_goal(self, context: UserContext) -> str:
        """Предлагает реалистичную цель накопления"""
        monthly_savings = context.monthly_income - context.monthly_expense
        if monthly_savings <= 0:
            return "Сейчас нет свободных средств. Давай сначала разберёмся с расходами."

        # Предлагаем цели на 3, 6 и 12 месяцев
        suggestions = [
            (3, monthly_savings * 3, "🎯 Быстрая цель"),
            (6, monthly_savings * 6, "📦 Среднесрочная"),
            (12, monthly_savings * 12, "🏆 Большая цель"),
        ]

        lines = ["💡 Реалистичные цели при текущем темпе:\n"]
        for months, amount, label in suggestions:
            lines.append(f"{label}: {amount:,.0f} ₽ за {months} мес. (по {monthly_savings:,.0f} ₽/мес)")

        return "\n".join(lines)

    def _llm_analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        client = self.get_llm_client()
        if not client:
            return self._rule_analyze(message, context, db_data)

        prompt = f"""{self.system_prompt}

Контекст:
- Доходы: {context.monthly_income:,.0f} ₽
- Расходы: {context.monthly_expense:,.0f} ₽
- Свободно: {context.monthly_income - context.monthly_expense:,.0f} ₽/мес
- Цели: {context.active_goals}

Проанализируй цели пользователя и дай стратегию накоплений.
Верни JSON: {{"insights": ["..."], "recommendations": ["..."], "goal_analysis": [...], "savings_plan": {{...}}}}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=300
            )
            import json
            result = json.loads(response.choices[0].message.content)
            return AgentResult(
                agent=self.name,
                action="strategize",
                data=result,
                insights=result.get("insights", []),
                confidence=0.8
            )
        except Exception as e:
            return AgentResult(agent=self.name, action="error", error=str(e), confidence=0)