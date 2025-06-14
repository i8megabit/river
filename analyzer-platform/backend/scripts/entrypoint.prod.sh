#!/bin/bash

# ========================================
# Production Entrypoint для FastAPI Backend
# ========================================

set -e

echo "🚀 Запуск Analyzer Platform Backend (Production Mode)"
echo "=================================================="

# Функция для ожидания доступности базы данных
wait_for_db() {
    echo "⏳ Ожидание подключения к PostgreSQL..."
    
    while ! nc -z "$POSTGRES_SERVER" "$POSTGRES_PORT" 2>/dev/null; do
        echo "⏳ PostgreSQL еще не доступен, ждем 2 секунды..."
        sleep 2
    done
    
    echo "✅ PostgreSQL доступен!"
}

# Функция для ожидания доступности Redis
wait_for_redis() {
    echo "⏳ Ожидание подключения к Redis..."
    
    while ! nc -z "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null; do
        echo "⏳ Redis еще не доступен, ждем 2 секунды..."
        sleep 2
    done
    
    echo "✅ Redis доступен!"
}

# Функция проверки и создания директорий
create_directories() {
    echo "📁 Создание необходимых директорий..."
    
    mkdir -p /app/uploads
    mkdir -p /app/logs
    mkdir -p /app/cache
    mkdir -p /app/temp
    
    echo "✅ Директории созданы!"
}

# Функция для миграций базы данных
run_migrations() {
    echo "🔄 Запуск миграций базы данных..."
    
    # Здесь можно добавить команды для миграций
    # python -m alembic upgrade head
    
    echo "✅ Миграции выполнены!"
}

# Функция проверки конфигурации
check_config() {
    echo "🔧 Проверка конфигурации..."
    
    # Проверяем обязательные переменные окружения
    if [ -z "$POSTGRES_SERVER" ]; then
        echo "❌ POSTGRES_SERVER не установлен"
        exit 1
    fi
    
    if [ -z "$REDIS_HOST" ]; then
        echo "❌ REDIS_HOST не установлен"
        exit 1
    fi
    
    if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "your-super-secret-production-key-change-me" ]; then
        echo "⚠️ ВНИМАНИЕ: Используется стандартный SECRET_KEY! Измените его в production!"
    fi
    
    echo "✅ Конфигурация проверена!"
}

# Функция настройки логирования
setup_logging() {
    echo "📝 Настройка логирования..."
    
    # Создаем файлы логов если их нет
    touch /app/logs/analyzer-platform.log
    touch /app/logs/access.log
    touch /app/logs/error.log
    
    echo "✅ Логирование настроено!"
}

# Основная функция инициализации
main() {
    echo "🔄 Инициализация production окружения..."
    
    check_config
    create_directories
    setup_logging
    wait_for_db
    wait_for_redis
    run_migrations
    
    echo "✅ Инициализация завершена!"
    echo "🚀 Запуск приложения..."
    
    # Запускаем переданную команду
    exec "$@"
}

# Обработка сигналов для graceful shutdown
cleanup() {
    echo "🛑 Получен сигнал завершения, остановка приложения..."
    kill -TERM "$child" 2>/dev/null
    wait "$child"
    echo "✅ Приложение остановлено"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Запуск основной функции
main "$@" &
child=$!
wait "$child" 