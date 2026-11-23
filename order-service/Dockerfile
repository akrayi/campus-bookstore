FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 10001 bookstore

COPY app.py .

USER bookstore

EXPOSE 5002

CMD ["python", "-m", "flask", "--app", "app", "run", "--host=0.0.0.0", "--port=5002"]