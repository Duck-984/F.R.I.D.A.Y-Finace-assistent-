"""
FRIDAY CORE AI — главный оркестратор системы.

Функции:
- Классифицирует интент сообщения
- Распределяет задачи между агентами
- Формирует финальный ответ
- Управляет цепочкой анализа

Это «личность FRIDAY» — все решения проходят через него.
"""

import re
from typing import Optional
from .base import BaseAgent, AgentResult, UserContext


class FridayCore(BaseAgent):
    name = "FRIDAY CORE"
    role = "orchestrator"
    emoji = "🧠"

    system_prompt = """Ты — FRIDAY, персональный финансовый AI-ассистент.
Твой стиль: Iron Man's assistant. Чётко, коротко, по делу.
Ты не придумываешь данные. Только факты + логика. Всегда думаешь в деньгах.

Твоя задача — понять, что хочет пользователь, и распределить работу между агентами:
- FINANCE ANALYST: анализ расходов, отчёты
- SAVINGS STRATEGIST: накопления, цели
- BEHAVIOR AI: привычки, паттерны
- COMMUNICATION AI: стиль ответа

Ты НЕ анализируешь сам — ты оркестрируешь. Ты решаешь КТО и ЧТО делает."""

    # Паттерны интентов
    INTENT_PATTERNS = {
        "add_expense": [
            r"потратил|расход|купил|заплатил|списал|ушло|минус",
            r"^\d+", r"-\d+"
        ],
        "add_income": [
            r"получил|доход|зарплат|пришло|плюс|заработал",
            r"\+\d+"
        ],
        "report": [
            r"отчёт|отчет|статистик|анализ|итог|сколько потратил|куда ушли",
            r"за месяц|за неделю|за день"
        ],
        "balance": [
            r"баланс|сколько денег|на счету|остаток"
        ],
        "goal": [
            r"цель|накопить|отложить|коплю|хочу купить"
        ],
        "budget": [
            r"бюджет|лимит|огранич|превысил|норма"
        ],
        "advice": [
            r"совет|рекоменд|помоги|что делать|экономи|сократить"
        ],
        "delete": [
            r"удал|убрать запись|отмени"
        ],
        "edit": [
            r"измени|поправ|ошибся|неправильно|исправ"
        ],
        "export": [
            r"выгру|экспорт|csv|скачай"
        ],
    }

    def _rule_analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        """Классифицирует интент на основе правил"""
        msg_lower = message.lower()
        scores = {}

        for intent, patterns in self.INTENT_PATTERNS.items():
            score = 0
            for pat in patterns:
                if re.search(pat, msg_lower):
                    score += 1
            if score > 0:
                scores[intent] = score

        if not scores:
            return AgentResult(
                agent=self.name,
                action="unknown",
                data={"message": message},
                confidence=0.3,
                insights=["Не удалось классифицировать запрос"]
            )

        # Выбираем интент с максимальным score
        primary_intent = max(scores, key=scores.get)
        confidence = min(scores[primary_intent] / 3.0, 1.0)

        # Решаем, какие агенты нужны
        agent_pipeline = self._route_to_agents(primary_intent)

        return AgentResult(
            agent=self.name,
            action=primary_intent,
            data={
                "message": message,
                "intent": primary_intent,
                "scores": scores,
                "pipeline": agent_pipeline
            },
            confidence=confidence,
            insights=[f"Интент: {primary_intent}, цепочка: {' → '.join(agent_pipeline)}"]
        )

    def _route_to_agents(self, intent: str) -> list:
        """Определяет цепочку агентов для обработки интента"""
        routing = {
            "add_expense":    ["analyst"],
            "add_income":     ["analyst"],
            "report":         ["analyst", "behavior"],
            "balance":        ["analyst"],
            "goal":           ["strategist"],
            "budget":         ["analyst", "strategist"],
            "advice":         ["behavior", "strategist", "analyst"],
            "delete":         ["analyst"],
            "edit":           ["analyst"],
            "export":         ["analyst"],
            "unknown":        [],
        }
        return routing.get(intent, [])

    def build_final_response(
        self,
        user_message: str,
        core_result: AgentResult,
        agent_results: list,
        context: UserContext
    ) -> str:
        """
        Собирает финальный ответ из результатов всех агентов.
        Вызывается ПОСЛЕ того, как все агенты отработали.
        """
        parts = []

        # Если ничего не поняли
        if core_result.action == "unknown":
            return (
                "🤔 Я не совсем понял. Я умею:\n\n"
                "💰 Записывать доходы и расходы\n"
                "📊 Показывать отчёты и статистику\n"
                "🎯 Ставить цели накопления\n"
                "📉 Устанавливать лимиты по категориям\n"
                "💡 Давать советы по экономии\n\n"
                "Напиши, например: «Потратил 5000 на продукты» или «Отчёт за месяц»"
            )

        # Добавляем подтверждение действия
        if core_result.action == "add_expense":
            parts.append("✅ Записал расход")
        elif core_result.action == "add_income":
            parts.append("✅ Записал доход")
        elif core_result.action == "delete":
            parts.append("🗑 Запись удалена")
        elif core_result.action == "edit":
            parts.append("✏️ Запись обновлена")

        # Собираем инсайты от агентов
        for ar in agent_results:
            if ar.success and ar.insights:
                for insight in ar.insights:
                    if insight not in parts:
                        parts.append(insight)

        # Добавляем контекст баланса
        if context.balance != 0 and core_result.action in ("add_expense", "add_income", "delete", "edit"):
            parts.append(f"💰 Баланс: {context.balance:,.0f} ₽")

        # Алерты по бюджету
        if context.budget_alerts:
            parts.append("\n⚠️ " + "\n⚠️ ".join(context.budget_alerts))

        return "\n".join(parts) if parts else "Принято. Что дальше?"

    def _llm_analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        """LLM-режим: отправляет промпт и получает структурированный ответ"""
        client = self.get_llm_client()
        if not client:
            return self._rule_analyze(message, context, db_data)

        prompt = f"""{self.system_prompt}

Контекст пользователя:
- Баланс: {context.balance:,.0f} ₽
- Доходы за месяц: {context.monthly_income:,.0f} ₽
- Расходы за месяц: {context.monthly_expense:,.0f} ₽

Сообщение: "{message}"

Определи интент (одно из: add_expense, add_income, report, balance, goal, budget, advice, delete, edit, export, unknown).
Верни JSON: {{"intent": "...", "confidence": 0.X, "entities": {{}}, "reasoning": "..."}}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200
            )
            import json
            result = json.loads(response.choices[0].message.content)
            return AgentResult(
                agent=self.name,
                action=result.get("intent", "unknown"),
                data={"message": message, "llm_response": result},
                confidence=result.get("confidence", 0.5),
                insights=[result.get("reasoning", "")]
            )
        except Exception as e:
            return AgentResult(
                agent=self.name,
                action="error",
                error=f"LLM error: {e}",
                confidence=0
            )