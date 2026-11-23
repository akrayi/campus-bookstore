FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 10001 bookstore \
    && chown bookstore:bookstore /app

COPY app.py schema.sql ./

USER bookstore

RUN python -c "import sqlite3; from pathlib import Path; db = sqlite3.connect('products.db'); db.executescript(Path('schema.sql').read_text(encoding='utf-8-sig')); db.close()"

EXPOSE 5001

CMD ["python", "-m", "flask", "--app", "app", "run", "--host=0.0.0.0", "--port=5001"]