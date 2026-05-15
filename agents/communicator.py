"""
COMMUNICATION AI — FRIDAY Voice.

Функции:
- Делает ответы «живыми»
- Короткие фразы
- Стиль Iron Man / JARVIS / FRIDAY assistant
- Решает: текст или голос (будущая фича)
- Адаптирует тон под контекст
"""

import random
from .base import BaseAgent, AgentResult, UserContext


class CommunicationAI(BaseAgent):
    name = "COMMUNICATION AI"
    role = "communicator"
    emoji = "💬"

    system_prompt = """Ты — голос FRIDAY, персонального AI-ассистента.
Стиль: Iron Man's FRIDAY. Чётко, уверенно, иногда с лёгкой иронией.
Короткие фразы. Никакой «воды». Всегда по делу.
Ты адаптируешь ответы — где-то поддержать, где-то предупредить, где-то похвалить."""

    # Вариации приветствий
    GREETINGS = [
        "FRIDAY на связи. Что нужно?",
        "Слушаю, босс.",
        "Готова к работе. Что анализируем?",
        "FRIDAY онлайн. Баланс под контролем.",
        "Привет. Куда смотрим — доходы, расходы, цели?",
    ]

    # Реакции на запись расхода
    EXPENSE_REACTIONS = [
        "Записала.",
        "Принято.",
        "В журнале.",
        "Зафиксировала.",
    ]

    # Реакции на запись дохода
    INCOME_REACTIONS = [
        "Отлично, записала.",
        "Приятная новость. Зафиксировала.",
        "Доход учтён.",
    ]

    # Похвала за экономию
    PRAISE = [
        "Так держать.",
        "Дисциплина — это суперсила.",
        "Хороший контроль.",
        "Стабильность — признак мастерства.",
    ]

    # Предупреждения
    WARNINGS = [
        "Осторожно, так мы бюджет не уложим.",
        "Перерасход — это скользкая дорожка.",
        "Давай притормозим.",
        "Цифры не врут. Пора экономить.",
    ]

    def _rule_analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        """
        Определяет тон ответа и подбирает стилистику.
        Не анализирует финансы — только стиль коммуникации.
        """
        mood = self._detect_mood(context)
        tone = self._pick_tone(context, db_data)

        return AgentResult(
            agent=self.name,
            action="style_response",
            data={
                "mood": mood,
                "tone": tone,
            },
            insights=[],
            confidence=0.9
        )

    def _detect_mood(self, context: UserContext) -> str:
        """Определяет настроение на основе финансовой ситуации"""
        monthly_savings = context.monthly_income - context.monthly_expense

        if context.balance < 0:
            return "concerned"
        if monthly_savings <= 0:
            return "warning"
        if context.budget_alerts:
            return "alert"
        if monthly_savings > context.monthly_income * 0.3:
            return "impressed"
        if context.active_goals:
            return "supportive"
        return "neutral"

    def _pick_tone(self, context: UserContext, db_data: dict) -> str:
        """Выбирает тон общения"""
        if context.balance < 0:
            return "direct"
        if context.monthly_income - context.monthly_expense > 0:
            return "confident"
        return "neutral"

    def wrap_response(self, raw_text: str, mood: str = "neutral") -> str:
        """Оборачивает сырой ответ в стиль FRIDAY"""
        # Убираем излишнюю информацию, делаем лаконичнее
        lines = raw_text.strip().split("\n")
        
        # Добавляем стилистическую подпись в зависимости от настроения
        if mood == "impressed":
            return raw_text + "\n\n👏 " + random.choice(self.PRAISE)
        elif mood == "warning":
            return raw_text + "\n\n⚠️ " + random.choice(self.WARNINGS)
        elif mood == "concerned":
            return "🔴 Ситуация требует внимания.\n\n" + raw_text
        
        return raw_text

    def greet(self) -> str:
        """Приветствие в стиле FRIDAY"""
        return random.choice(self.GREETINGS)

    def confirm_action(self, action: str, success: bool) -> str:
        """Подтверждение действия в стиле FRIDAY"""
        if not success:
            return "❌ Что-то пошло не так. Попробуй ещё раз."

        if action == "add_expense":
            return random.choice(self.EXPENSE_REACTIONS)
        elif action == "add_income":
            return random.choice(self.INCOME_REACTIONS)
        elif action == "delete":
            return "Удалила."
        elif action == "edit":
            return "Исправила."
        return "Сделано."

    def _llm_analyze(self, message: str, context: UserContext, db_data: dict) -> AgentResult:
        client = self.get_llm_client()
        if not client:
            return self._rule_analyze(message, context, db_data)

        prompt = f"""{self.system_prompt}

Контекст:
- Баланс: {context.balance:,.0f} ₽
- Настроение: {self._detect_mood(context)}

Сообщение пользователя: "{message}"

Предложи краткий ответ в стиле FRIDAY (Iron Man assistant).
Верни JSON: {{"response": "...", "tone": "...", "mood": "..."}}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150
            )
            import json
            result = json.loads(response.choices[0].message.content)
            return AgentResult(
                agent=self.name,
                action="style_response",
                data=result,
                insights=[result.get("response", "")],
                confidence=0.85
            )
        except Exception as e:
            return AgentResult(agent=self.name, action="error", error=str(e), confidence=0)