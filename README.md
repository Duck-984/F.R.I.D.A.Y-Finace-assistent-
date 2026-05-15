# 🤖 FRIDAY — Финансовый AI-ассистент в Telegram

**Multi-Agent система** с 5 специализированными AI-агентами.

> «FRIDAY, сколько я потратил на кофе в этом месяце?»
> «Затянул с подписками, босс. 3 200 ₽ — на 40% больше прошлого месяца.»

---

## 🧠 Архитектура

```
Пользователь → Telegram Bot → Brain (оркестратор)
                                  ├── CORE AI (классификация интента)
                                  ├── FINANCE ANALYST (анализ расходов)
                                  ├── SAVINGS STRATEGIST (план накоплений)
                                  ├── BEHAVIOR AI (привычки и паттерны)
                                  └── COMMUNICATOR AI (стиль FRIDAY)
```

5 агентов работают параллельно (asyncio), каждый со своей специализацией. Без API-ключа агенты работают в rule-based режиме. С ключом OpenAI/Anthropic/OpenRouter — включается настоящий LLM-reasoning.

---

## 🚀 Быстрый старт

### 1. Получить токен бота
Напиши [@BotFather](https://t.me/BotFather) в Telegram:
```
/newbot → имя → юзернейм → получить токен
```

### 2. Настроить окружение
```bash
cp .env.example .env
# Отредактируй BOT_TOKEN=...
```

### 3. Запустить

**Docker (рекомендуется):**
```bash
docker compose up -d
```

**Без Docker:**
```bash
pip install -r requirements.txt
python bot.py
```

---

## ⚙️ Переменные окружения

| Переменная | Обязательно | Описание |
|---|---|---|
| `BOT_TOKEN` | Да | Токен от @BotFather |
| `OPENAI_API_KEY` | Нет | Ключ OpenAI для AI-советника |
| `ANTHROPIC_API_KEY` | Нет | Ключ Anthropic (Claude) |
| `OPENROUTER_API_KEY` | Нет | Ключ OpenRouter (бесплатные модели) |
| `DB_PATH` | Нет | Путь к SQLite (по умолчанию finance.db) |
| `LOG_LEVEL` | Нет | Уровень логов (DEBUG/INFO/WARNING) |

---

## 🧪 Тесты

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

Покрытие: база данных, LLM-слой, агенты, оркестратор.

---

## 📦 Деплой

```bash
docker compose up -d              # Запуск
docker compose logs -f friday     # Логи
docker compose exec friday python -c "from health import health_check; print(health_check())"
```

Watchtower-профиль для автообновления:
```bash
docker compose --profile monitoring up -d
```

---

## 📂 Структура проекта

```
friday/
├── agents/           # 5 AI-агентов
│   ├── core.py       # Оркестратор интентов
│   ├── analyst.py    # Анализ расходов
│   ├── strategist.py # План накоплений
│   ├── behavior.py   # Поведенческие паттерны
│   └── communicator.py # Стиль FRIDAY
├── brain.py          # Синхронный оркестратор
├── brain_async.py    # Асинхронный оркестратор (продакшен)
├── llm.py            # Pluggable LLM (OpenAI/Anthropic/OpenRouter)
├── memory.py         # RAG-память диалогов
├── database.py       # SQLite (транзакции, цели, лимиты)
├── bot.py            # Telegram-бот на python-telegram-bot
├── config.py         # Конфигурация из .env
├── logger.py         # Структурированное логирование
├── health.py         # Health-check
├── migrations.py     # Автоматические миграции
├── ai_advice.py      # AI-советы
├── analytics.py      # Аналитика
├── tips.py           # Советы дня
├── tests/            # Тесты (pytest)
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── requirements.txt
└── pytest.ini
```

---

## 🔮 Roadmap

- [x] Multi-agent архитектура (5 агентов)
- [x] SQLite с индексами и миграциями
- [x] Pluggable LLM с rule-based fallback
- [x] Docker + docker-compose
- [x] Асинхронный brain (параллельные агенты)
- [x] Health-check и логирование
- [x] Тесты (pytest)
- [ ] Веб-хуки вместо polling
- [ ] Redis для кэша и очередей
- [ ] Whisper/TTS для голосовых сообщений
- [ ] Веб-дашборд аналитики
- [ ] Распознавание чеков (GPT-4 Vision)

---

**Лицензия:** MIT
