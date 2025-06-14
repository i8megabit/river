# ========================================
# Dockerfile для FastAPI Backend
# Многоэтапная сборка для оптимизации размера
# ========================================

ARG PYTHON_VERSION=3.11

# ========================================
# Базовый образ с зависимостями
# ========================================
FROM python:${PYTHON_VERSION}-slim as base

# Метаданные
LABEL maintainer="analyzer-platform"
LABEL version="v0.0.1"
LABEL description="Веб-платформа анализатора системы"

# Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ========================================
# Образ для зависимостей
# ========================================
FROM base as dependencies

# Обновление pip
RUN pip install --upgrade pip setuptools wheel

# Копирование файла зависимостей
COPY requirements.txt /tmp/requirements.txt

# Установка Python зависимостей
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ========================================
# Продакшен образ
# ========================================
FROM base as production

# Создание пользователя для безопасности
RUN groupadd -r analyzer && useradd -r -g analyzer analyzer

# Создание рабочей директории
WORKDIR /app

# Копирование установленных зависимостей
COPY --from=dependencies /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=dependencies /usr/local/bin/ /usr/local/bin/

# Создание директорий
RUN mkdir -p /app/uploads /app/logs && \
    chown -R analyzer:analyzer /app

# Копирование исходного кода
COPY --chown=analyzer:analyzer . /app/

# Установка прав доступа
RUN chmod +x /app/scripts/entrypoint.sh || echo "No entrypoint script"

# Переключение на пользователя
USER analyzer

# Проверка работоспособности
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Экспорт порта
EXPOSE 8000

# Команда запуска
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# ========================================
# Образ для разработки
# ========================================
FROM production as development

USER root

# Установка дополнительных dev зависимостей
RUN pip install --no-cache-dir \
    debugpy \
    pytest \
    pytest-asyncio \
    pytest-cov

USER analyzer

# Команда для разработки с hot reload
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 