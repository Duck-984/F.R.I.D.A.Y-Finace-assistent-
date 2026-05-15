# FRIDAY Docker — multi-stage build
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY . .

# Непривилегированный пользователь
RUN useradd -m -u 1000 friday && chown -R friday:friday /app
USER friday

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import sqlite3; sqlite3.connect('finance.db').execute('SELECT 1')" || exit 1

CMD ["python", "bot.py"]
