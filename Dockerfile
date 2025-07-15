# syntax=docker/dockerfile:1
FROM python:3.11-slim

# 1) Системные пакеты для сборки lxml и других C-расширений
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      python3-dev \
      libxml2-dev \
      libxslt1-dev \
      zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Устанавливаем Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) Копируем весь код приложения
COPY . .

EXPOSE 8000

# 4) Запуск Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]