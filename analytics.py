"""
Модуль аналитики — отчёты, статистика, рекомендации
"""

from datetime import datetime
from database import get_monthly_stats, get_daily_average, get_top_expenses, get_balance


def format_stats(user_id: int) -> str:
    """Сформировать месячный отчёт."""
    now = datetime.now()
    rows, income, expense = get_monthly_stats(user_id, now.year, now.month)
    balance = get_balance(user_id)
    daily_avg = get_daily_average(user_id, 30)

    lines = [
        f"📊 *Отчёт за {_month_name(now.month)} {now.year}*",
        "",
        f"💰 Доходы: `{income:,.0f}` ₽",
        f"💸 Расходы: `{expense:,.0f}` ₽",
        f"📌 Баланс: `{balance:,.0f}` ₽",
        f"📉 Средний дневной расход (30 дн): `{daily_avg:,.0f}` ₽",
        "",
    ]

    if rows:
        lines.append("*Расходы по категориям:*")
        for icon, name, total in rows:
            pct = (total / expense * 100) if expense > 0 else 0
            bar = _bar(pct)
            lines.append(f"{icon} {name}: `{total:,.0f}` ₽ ({pct:.0f}%) {bar}")
    else:
        lines.append("Нет расходов за этот месяц 🎉")

    return "\n".join(lines)


def format_insights(user_id: int) -> str:
    """Сформировать персонализированные советы на основе данных."""
    top = get_top_expenses(user_id, 5)
    balance = get_balance(user_id)
    daily_avg = get_daily_average(user_id, 30)

    lines = ["💡 *Аналитика и советы*", ""]

    if not top:
        lines.append("Пока недостаточно данных для анализа. Начните записывать траты!")
        return "\n".join(lines)

    # Топ-категории
    biggest = top[0]
    lines.append(f"🔴 *Главная статья расходов:* {biggest['icon']} {biggest['name']} — `{biggest['total']:,.0f}` ₽")
    lines.append("")

    # Советы по категориям
    tips_by_category = {
        "Еда": "🍽 Попробуйте готовить дома — экономия до 40% бюджета на питание.",
        "Транспорт": "🚌 Используйте проездной или каршеринг вместо такси.",
        "Развлечения": "🎯 Установите недельный лимит на развлечения.",
        "Одежда": "👗 Покупайте в межсезонье — скидки до 70%.",
        "Техника": "💻 Сравнивайте цены перед покупкой и ждите акций.",
        "Кафе/Рестораны": "☕️ Кофе с собой — до 5 000 ₽/мес. Термокружка окупается за неделю.",
    }

    for icon, name, total in top[:3]:
        if name in tips_by_category:
            lines.append(tips_by_category[name])

    lines.append("")

    # Баланс и прогноз
    if balance < 0:
        lines.append("⚠️ *Баланс отрицательный!* Срочно пересмотрите расходы.")
    elif daily_avg > 0:
        days_left = balance / daily_avg if balance > 0 else 0
        lines.append(f"📅 При текущем темпе трат вашего баланса хватит на *{days_left:.0f} дней*.")
        if days_left < 15:
            lines.append("⚡ Это меньше двух недель — рекомендую сократить необязательные расходы.")

    return "\n".join(lines)


def format_goals_status(user_id: int, goals) -> str:
    """Форматировать список целей."""
    if not goals:
        return "🎯 У вас пока нет целей. Создайте первую: `/goal`"

    lines = ["🎯 *Мои цели:*", ""]
    for g in goals:
        pct = (g["current_amount"] / g["target_amount"] * 100) if g["target_amount"] > 0 else 0
        bar = _bar(pct)
        deadline = f" до {g['deadline']}" if g["deadline"] else ""
        lines.append(
            f"• *{g['name']}*{deadline}\n"
            f"  `{g['current_amount']:,.0f}` / `{g['target_amount']:,.0f}` ₽ ({pct:.0f}%) {bar}"
        )
    return "\n".join(lines)


def _bar(pct: float, width: int = 10) -> str:
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _month_name(m: int) -> str:
    return [
        "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ][m]
