"""
AI-советник — использует OpenAI для персонализированных финансовых советов.
Анализирует реальные транзакции пользователя и даёт контекстные рекомендации.
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

AI_SYSTEM_PROMPT = """Ты — персональный финансовый ассистент в Telegram-боте. 
Твоя задача: проанализировать транзакции пользователя и дать КОНКРЕТНЫЕ, 
практичные советы по экономии на основе реальных данных.

Правила:
1. Анализируй только то, что видишь в данных. Не придумывай.
2. Выдели 1-2 самые проблемные категории с цифрами.
3. Дай 3-4 конкретных совета с расчётом потенциальной экономии в рублях.
4. Будь дружелюбным, но прямым. Используй эмодзи.
5. Пиши на русском языке.
6. Ответ должен быть 600-1000 символов.
7. Используй Markdown: *жирный* для важного, `код` для цифр."""


def build_analysis_context(user_data: list[dict], balance: float,
                           daily_avg: float, goals: list = None) -> str:
    """Собрать контекст для AI из транзакций."""
    if not user_data:
        return "У пользователя пока нет транзакций."

    # Группировка по категориям
    by_category = {}
    total_income = 0
    total_expense = 0
    for tx in user_data:
        cat = f"{tx.get('icon', '')} {tx.get('category', '?')}"
        by_category.setdefault(cat, 0)
        by_category[cat] += tx["amount"]
        if tx["type"] == "income":
            total_income += tx["amount"]
        else:
            total_expense += tx["amount"]

    top_expenses = sorted(
        [(k, v) for k, v in by_category.items() if "доход" not in k.lower()],
        key=lambda x: x[1], reverse=True
    )[:5]

    lines = [
        f"Баланс: {balance:,.0f} ₽",
        f"Доходы (всего): {total_income:,.0f} ₽",
        f"Расходы (всего): {total_expense:,.0f} ₽",
        f"Средний дневной расход: {daily_avg:,.0f} ₽",
        f"Всего транзакций: {len(user_data)}",
        "",
        "Топ расходов по категориям:",
    ]
    for cat, amt in top_expenses:
        pct = (amt / total_expense * 100) if total_expense > 0 else 0
        lines.append(f"  {cat}: {amt:,.0f} ₽ ({pct:.0f}%)")

    if goals:
        lines.append("")
        lines.append("Цели накоплений:")
        for g in goals:
            pct = (g["current_amount"] / g["target_amount"] * 100) if g["target_amount"] > 0 else 0
            lines.append(f"  {g['name']}: {g['current_amount']:,.0f} / {g['target_amount']:,.0f} ₽ ({pct:.0f}%)")

    return "\n".join(lines)


async def get_ai_advice(openai_client, user_data: list[dict], balance: float,
                        daily_avg: float, goals: list = None) -> str:
    """Получить AI-совет на основе транзакций."""
    context = build_analysis_context(user_data, balance, daily_avg, goals)

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {"role": "user", "content": f"Вот мои финансовые данные за последнее время:\n\n{context}\n\nДай персонализированный анализ и советы."},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"AI advice failed: {e}")
        return None
