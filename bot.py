"""
Telegram-бот финансового ассистента v2.0
Новое: удаление/редактирование транзакций, лимиты по категориям, CSV-экспорт, AI-советник
"""

import logging
import os
import tempfile
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters,
)
from telegram.constants import ParseMode

from config import BOT_TOKEN, AI_ENABLED, AI_MODEL
from database import (
    init_db, ensure_user, get_categories, add_transaction,
    delete_transaction, update_transaction, get_transaction,
    get_balance, get_recent, get_monthly_stats, get_daily_average,
    add_goal, get_goals, get_total_saved,
    set_budget, get_budgets, delete_budget, check_budget_alerts,
    export_csv, export_all_for_ai, get_top_expenses,
)
from analytics import format_stats, format_insights, format_goals_status
from tips import get_daily_tip, get_tips_by_count

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Этапы ConversationHandler
CHOOSE_TYPE, CHOOSE_CATEGORY, ENTER_AMOUNT, ENTER_DESC = range(4)
GOAL_NAME, GOAL_AMOUNT, GOAL_DEADLINE = range(10, 13)
BUDGET_CATEGORY, BUDGET_AMOUNT = range(20, 22)
EDIT_SELECT, EDIT_FIELD, EDIT_VALUE = range(30, 33)


# ─── Клавиатуры ─────────────────────────────────────────────────

def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Доход", callback_data="add_income"),
            InlineKeyboardButton("➖ Расход", callback_data="add_expense"),
        ],
        [
            InlineKeyboardButton("📊 Баланс", callback_data="balance"),
            InlineKeyboardButton("📋 История", callback_data="history"),
        ],
        [
            InlineKeyboardButton("📈 Статистика", callback_data="stats"),
            InlineKeyboardButton("🤖 AI-совет", callback_data="ai_advice"),
        ],
        [
            InlineKeyboardButton("💡 Совет", callback_data="tip"),
            InlineKeyboardButton("🎯 Цели", callback_data="goals"),
        ],
        [
            InlineKeyboardButton("⏱ Лимиты", callback_data="budgets"),
            InlineKeyboardButton("📥 Экспорт", callback_data="export"),
        ],
    ])


def back_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Назад", callback_data="main_menu"),
    ]])


# ─── Команды ────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username or "", user.first_name or "")
    await update.message.reply_text(
        f"👋 Привет, *{user.first_name or 'друг'}*!\n\n"
        f"Я твой финансовый ассистент. Помогу:\n"
        f"• Учитывать доходы и расходы\n"
        f"• Анализировать траты\n"
        f"• Ставить цели и копить\n"
        f"• Контролировать лимиты по категориям\n"
        f"• Получать AI-советы на основе твоих данных\n\n"
        f"Выбери действие:",
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📋 *Главное меню*",
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── Баланс ─────────────────────────────────────────────────────

async def balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    bal = get_balance(uid)
    daily = get_daily_average(uid, 30)

    text = f"💰 *Баланс:* `{bal:,.0f}` ₽\n📉 *Средний дневной расход (30 дн):* `{daily:,.0f}` ₽"

    # Проверить лимиты
    alerts = check_budget_alerts(uid)
    if alerts:
        text += "\n\n" + "\n".join(alerts)

    await query.edit_message_text(text, reply_markup=back_keyboard(), parse_mode=ParseMode.MARKDOWN)


# ─── Добавление транзакции (Conversation) ───────────────────────

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tx_type = query.data.replace("add_", "")
    context.user_data["tx_type"] = tx_type
    cats = get_categories(tx_type)

    if not cats:
        await query.edit_message_text("Нет категорий.", reply_markup=back_keyboard())
        return ConversationHandler.END

    kb = [[InlineKeyboardButton(f"{r['icon']} {r['name']}", callback_data=f"cat_{r['id']}")] for r in cats]
    kb.append([InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")])

    await query.edit_message_text(
        f"{'💰' if tx_type == 'income' else '💸'} *Выбери категорию:*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.MARKDOWN,
    )
    return CHOOSE_CATEGORY


async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["category_id"] = int(query.data.split("_")[1])
    await query.edit_message_text(
        "✏️ *Введи сумму* (только число, например `1500`):",
        reply_markup=back_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ENTER_AMOUNT


async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введи положительное число.", reply_markup=back_keyboard())
        return ENTER_AMOUNT

    context.user_data["amount"] = amount
    await update.message.reply_text(
        "📝 *Описание* (необязательно) — или отправь `-` чтобы пропустить:",
        reply_markup=back_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ENTER_DESC


async def enter_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if desc == "-":
        desc = ""

    uid = update.effective_user.id
    ensure_user(uid, update.effective_user.username or "", update.effective_user.first_name or "")

    add_transaction(
        uid,
        context.user_data["tx_type"],
        context.user_data["amount"],
        context.user_data["category_id"],
        desc,
    )

    emoji = "💰" if context.user_data["tx_type"] == "income" else "💸"
    await update.message.reply_text(
        f"{emoji} Записано: `{context.user_data['amount']:,.0f}` ₽ {desc}",
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )

    # Проверить лимиты после добавления
    alerts = check_budget_alerts(uid)
    if alerts:
        await update.message.reply_text(
            "\n".join(alerts),
            parse_mode=ParseMode.MARKDOWN,
        )

    return ConversationHandler.END


async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ Отменено.", reply_markup=main_keyboard())
    else:
        await update.message.reply_text("❌ Отменено.", reply_markup=main_keyboard())
    return ConversationHandler.END


# ─── История ────────────────────────────────────────────────────

async def history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    rows = get_recent(uid, 10)

    if not rows:
        await query.edit_message_text("📋 Пока нет транзакций.", reply_markup=back_keyboard())
        return

    lines = ["📋 *Последние операции:*", ""]
    kb_rows = []
    for r in rows:
        sign = "+" if r["type"] == "income" else "-"
        date_str = r["created_at"][:10] if r["created_at"] else "?"
        lines.append(
            f"{sign}`{r['amount']:,.0f}` ₽ {r['icon']} {r['category']} — {date_str}"
        )
        kb_rows.append([
            InlineKeyboardButton(f"✏️ {r['icon']} {r['category']} {r['amount']:,.0f}₽",
                                 callback_data=f"edit_{r['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"del_{r['id']}"),
        ])

    kb_rows.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(kb_rows),
        parse_mode=ParseMode.MARKDOWN,
    )


# ─── Удаление транзакции ───────────────────────────────────────

async def delete_tx_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    tx_id = int(query.data.split("_")[1])

    if delete_transaction(uid, tx_id):
        await query.edit_message_text(
            "🗑 Транзакция удалена.",
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await query.answer("Не удалось удалить.", show_alert=True)


# ─── Редактирование транзакции ─────────────────────────────────

async def edit_tx_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    tx_id = int(query.data.split("_")[1])
    tx = get_transaction(uid, tx_id)

    if not tx:
        await query.edit_message_text("Транзакция не найдена.", reply_markup=back_keyboard())
        return

    context.user_data["edit_tx_id"] = tx_id
    context.user_data["edit_tx_type"] = tx["type"]
    context.user_data["edit_old_amount"] = tx["amount"]
    context.user_data["edit_old_cat"] = tx["category"]

    kb = [
        [InlineKeyboardButton(f"💰 Сумма: {tx['amount']:,.0f} ₽", callback_data="edf_amount")],
        [InlineKeyboardButton(f"📂 Категория: {tx['icon']} {tx['category']}", callback_data="edf_category")],
        [InlineKeyboardButton(f"📝 Описание: {tx['description'] or '—'}", callback_data="edf_desc")],
        [InlineKeyboardButton("✅ Готово", callback_data="edf_done")],
    ]

    await query.edit_message_text(
        f"✏️ *Редактирование транзакции*\n\n"
        f"Тип: {'💰 Доход' if tx['type'] == 'income' else '💸 Расход'}\n"
        f"Сумма: `{tx['amount']:,.0f}` ₽\n"
        f"Категория: {tx['icon']} {tx['category']}\n"
        f"Описание: {tx['description'] or '—'}\n\n"
        f"Что изменить?",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.MARKDOWN,
    )


async def edit_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.replace("edf_", "")
    context.user_data["edit_field"] = field

    if field == "amount":
        await query.edit_message_text(
            "✏️ *Введи новую сумму:*",
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return EDIT_VALUE
    elif field == "category":
        cats = get_categories(context.user_data["edit_tx_type"])
        kb = [[InlineKeyboardButton(f"{r['icon']} {r['name']}", callback_data=f"edcat_{r['id']}")] for r in cats]
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data=f"edit_{context.user_data['edit_tx_id']}")])
        await query.edit_message_text(
            "📂 *Выбери категорию:*",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=ParseMode.MARKDOWN,
        )
        return EDIT_VALUE
    elif field == "desc":
        await query.edit_message_text(
            "📝 *Введи новое описание* (или `-` чтобы очистить):",
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return EDIT_VALUE
    elif field == "done":
        return await edit_done(update, context)


async def edit_apply_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    tx_id = context.user_data["edit_tx_id"]
    field = context.user_data["edit_field"]

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if field == "category":
            cat_id = int(query.data.split("_")[1])
            update_transaction(uid, tx_id, category_id=cat_id)
        return await edit_tx_callback(update, context)

    text = update.message.text.strip()

    if field == "amount":
        try:
            new_amount = float(text.replace(",", "."))
            if new_amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Введи положительное число.", reply_markup=back_keyboard())
            return EDIT_VALUE
        update_transaction(uid, tx_id, amount=new_amount)

    elif field == "desc":
        desc = "" if text == "-" else text
        update_transaction(uid, tx_id, description=desc)

    # Показать обновлённую транзакцию
    tx = get_transaction(uid, tx_id)
    if tx:
        await update.message.reply_text(
            f"✅ Обновлено:\n"
            f"{'💰' if tx['type'] == 'income' else '💸'} "
            f"`{tx['amount']:,.0f}` ₽ {tx['icon']} {tx['category']} — {tx['description'] or '—'}",
            reply_markup=main_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )

    return ConversationHandler.END


async def edit_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ Редактирование завершено.", reply_markup=main_keyboard())
    return ConversationHandler.END


# ─── Статистика ─────────────────────────────────────────────────

async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    text = format_stats(uid)
    await query.edit_message_text(text, reply_markup=back_keyboard(), parse_mode=ParseMode.MARKDOWN)


async def insights_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    text = format_insights(uid)
    await query.edit_message_text(text, reply_markup=back_keyboard(), parse_mode=ParseMode.MARKDOWN)


# ─── AI-советник ────────────────────────────────────────────────

async def ai_advice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    try:
        import openai
        from ai_advice import get_ai_advice
    except ImportError:
        await query.edit_message_text(
            "🤖 *AI-советник недоступен.*\nУстановите `openai`: pip install openai\n"
            "И добавьте OPENAI_API_KEY в Settings → API Keys.",
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await query.edit_message_text("🤖 *Анализирую твои финансы...*", parse_mode=ParseMode.MARKDOWN)

    data = export_all_for_ai(uid)
    balance = get_balance(uid)
    daily_avg = get_daily_average(uid, 30)
    goals = get_goals(uid)
    goals_dicts = [dict(g) for g in goals] if goals else None

    client = openai.OpenAI()
    advice = await get_ai_advice(client, data, balance, daily_avg, goals_dicts)

    if advice:
        await query.edit_message_text(
            f"🤖 *AI-анализ твоих финансов:*\n\n{advice}",
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        # Fallback на статические советы
        text = get_tips_by_count(3)
        await query.edit_message_text(
            f"🤖 AI-советник временно недоступен.\n\n{text}",
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )


# ─── Советы ─────────────────────────────────────────────────────

async def tip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tip = get_daily_tip()
    await query.edit_message_text(tip, reply_markup=back_keyboard(), parse_mode=ParseMode.MARKDOWN)


# ─── Цели (Conversation) ────────────────────────────────────────

async def goals_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    goals = get_goals(uid)
    text = format_goals_status(uid, goals)

    kb = [
        [InlineKeyboardButton("➕ Новая цель", callback_data="new_goal")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")],
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)


async def goal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎯 *Название цели:*\nНапример: «Отпуск», «Квартира», «Подушка безопасности»",
        reply_markup=back_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return GOAL_NAME


async def goal_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["goal_name"] = update.message.text.strip()
    await update.message.reply_text(
        "💰 *Целевая сумма* (только число):",
        reply_markup=back_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return GOAL_AMOUNT


async def goal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target = float(update.message.text.replace(",", "."))
        if target <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введи положительное число.", reply_markup=back_keyboard())
        return GOAL_AMOUNT

    context.user_data["goal_target"] = target
    await update.message.reply_text(
        "📅 *Срок (дедлайн)* — введи дату `ГГГГ-ММ-ДД` или `-` чтобы пропустить:",
        reply_markup=back_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return GOAL_DEADLINE


async def goal_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deadline = update.message.text.strip()
    if deadline == "-":
        deadline = None

    uid = update.effective_user.id
    add_goal(uid, context.user_data["goal_name"], context.user_data["goal_target"], deadline)

    await update.message.reply_text(
        f"🎯 Цель создана: *{context.user_data['goal_name']}* — `{context.user_data['goal_target']:,.0f}` ₽",
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# ─── Лимиты (бюджеты) ───────────────────────────────────────────

async def budgets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    budgets = get_budgets(uid)

    if not budgets:
        text = "⏱ *Лимиты по категориям*\n\nПока нет установленных лимитов."
    else:
        lines = ["⏱ *Лимиты на текущий месяц:*", ""]
        for b in budgets:
            pct = (b["spent"] / b["monthly_limit"] * 100) if b["monthly_limit"] > 0 else 0
            bar = _progress_bar(pct)
            status = "🔴" if pct > 100 else "🟡" if pct > 80 else "🟢"
            lines.append(
                f"{status} {b['icon']} *{b['name']}*: "
                f"`{b['spent']:,.0f}` / `{b['monthly_limit']:,.0f}` ₽ ({pct:.0f}%) {bar}"
            )
        text = "\n".join(lines)

    kb = [
        [InlineKeyboardButton("➕ Установить лимит", callback_data="new_budget")],
    ]
    if budgets:
        for b in budgets:
            kb.append([
                InlineKeyboardButton(f"🗑 Удалить лимит: {b['icon']} {b['name']}",
                                     callback_data=f"delbudget_{b['id']}"),
            ])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)


async def budget_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cats = get_categories("expense")
    kb = [[InlineKeyboardButton(f"{r['icon']} {r['name']}", callback_data=f"bcat_{r['id']}")] for r in cats]
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="budgets")])

    await query.edit_message_text(
        "⏱ *На какую категорию установить лимит?*",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.MARKDOWN,
    )
    return BUDGET_AMOUNT


async def budget_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["budget_cat_id"] = int(query.data.split("_")[1])
        await query.edit_message_text(
            "💰 *Сумма месячного лимита* (только число):",
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return BUDGET_AMOUNT

    try:
        limit = float(update.message.text.replace(",", "."))
        if limit <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введи положительное число.", reply_markup=back_keyboard())
        return BUDGET_AMOUNT

    uid = update.effective_user.id
    set_budget(uid, context.user_data["budget_cat_id"], limit)

    await update.message.reply_text(
        f"✅ Лимит установлен: `{limit:,.0f}` ₽/мес",
        reply_markup=main_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def delete_budget_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    budget_id = int(query.data.split("_")[1])

    if delete_budget(uid, budget_id):
        await query.edit_message_text("🗑 Лимит удалён.", reply_markup=back_keyboard())
    else:
        await query.answer("Не удалось удалить.", show_alert=True)


# ─── Экспорт CSV ────────────────────────────────────────────────

async def export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    csv_data = export_csv(uid)
    if not csv_data or csv_data.count("\n") <= 1:
        await query.edit_message_text(
            "📥 Нет данных для экспорта.",
            reply_markup=back_keyboard(),
        )
        return

    # Сохранить во временный файл и отправить
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8")
    tmp.write(csv_data)
    tmp.close()

    await query.message.reply_document(
        document=open(tmp.name, "rb"),
        filename=f"finance_export_{datetime.now().strftime('%Y%m%d')}.csv",
        caption="📥 Твои финансовые данные",
    )
    os.unlink(tmp.name)

    await query.edit_message_text(
        "📥 Экспорт готов! Файл отправлен выше ↑",
        reply_markup=main_keyboard(),
    )


# ─── Вспомогательное ────────────────────────────────────────────

def _progress_bar(pct: float, width: int = 10) -> str:
    filled = int(min(pct, 100) / 100 * width)
    return "█" * filled + "░" * (width - filled)


# ─── main ───────────────────────────────────────────────────────

def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))

    # Основное меню
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(balance_callback, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(history_callback, pattern="^history$"))
    app.add_handler(CallbackQueryHandler(stats_callback, pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(insights_callback, pattern="^insights$"))
    app.add_handler(CallbackQueryHandler(tip_callback, pattern="^tip$"))
    app.add_handler(CallbackQueryHandler(goals_callback, pattern="^goals$"))
    app.add_handler(CallbackQueryHandler(budgets_callback, pattern="^budgets$"))
    app.add_handler(CallbackQueryHandler(export_callback, pattern="^export$"))
    app.add_handler(CallbackQueryHandler(ai_advice_callback, pattern="^ai_advice$"))

    # Удаление / редактирование
    app.add_handler(CallbackQueryHandler(delete_tx_callback, pattern="^del_"))
    app.add_handler(CallbackQueryHandler(edit_tx_callback, pattern="^edit_"))
    app.add_handler(CallbackQueryHandler(edit_field_callback, pattern="^edf_"))
    app.add_handler(CallbackQueryHandler(edit_apply_value, pattern="^edcat_"))

    # Удаление бюджета
    app.add_handler(CallbackQueryHandler(delete_budget_callback, pattern="^delbudget_"))

    # Conversation: добавление транзакции
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_start, pattern="^add_(income|expense)$")],
        states={
            CHOOSE_CATEGORY: [CallbackQueryHandler(choose_category, pattern="^cat_")],
            ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount)],
            ENTER_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_desc)],
        },
        fallbacks=[CallbackQueryHandler(add_cancel, pattern="^main_menu$")],
    )
    app.add_handler(add_conv)

    # Conversation: цели
    goal_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(goal_start, pattern="^new_goal$")],
        states={
            GOAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_name)],
            GOAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_amount)],
            GOAL_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_deadline)],
        },
        fallbacks=[CallbackQueryHandler(add_cancel, pattern="^main_menu$")],
    )
    app.add_handler(goal_conv)

    # Conversation: лимиты
    budget_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(budget_start, pattern="^new_budget$")],
        states={
            BUDGET_AMOUNT: [
                CallbackQueryHandler(budget_amount, pattern="^bcat_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, budget_amount),
            ],
        },
        fallbacks=[CallbackQueryHandler(budgets_callback, pattern="^budgets$")],
    )
    app.add_handler(budget_conv)

    # Conversation: редактирование транзакции
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_field_callback, pattern="^edf_(amount|category|desc|done)$")],
        states={
            EDIT_VALUE: [
                CallbackQueryHandler(edit_apply_value, pattern="^edcat_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_apply_value),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"),
            CallbackQueryHandler(edit_tx_callback, pattern="^edit_"),
        ],
    )
    app.add_handler(edit_conv)

    logging.info("🤖 Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
