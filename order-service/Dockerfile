FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY order-service/requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 10001 bookstore

COPY order-service/app.py .
COPY shared ./shared

USER bookstore

EXPOSE 5002

CMD ["gunicorn", "--workers=1", "--threads=4", "--bind=0.0.0.0:5002", "--access-logfile=-", "app:app"]
