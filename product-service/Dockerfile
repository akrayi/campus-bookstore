FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY product-service/requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 10001 bookstore \
    && chown bookstore:bookstore /app

COPY product-service/app.py product-service/schema.sql ./
COPY shared ./shared

USER bookstore

RUN python -c "import sqlite3; from pathlib import Path; db = sqlite3.connect('products.db'); db.executescript(Path('schema.sql').read_text(encoding='utf-8-sig')); db.close()"

EXPOSE 5001

CMD ["gunicorn", "--workers=1", "--threads=4", "--bind=0.0.0.0:5001", "--access-logfile=-", "app:app"]
