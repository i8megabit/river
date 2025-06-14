#!/bin/bash

# ========================================
# Скрипт установки тестового окружения веб-платформы анализатора
# Выполняет полную установку с нуля
# ========================================

set -e  # Выход при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Логирование
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка ОС
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

# Проверка Docker
check_docker() {
    log_info "Проверка Docker..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен! Установите Docker и попробуйте снова."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker не запущен! Запустите Docker и попробуйте снова."
        exit 1
    fi
    
    log_success "Docker доступен"
}

# Проверка Docker Compose
check_docker_compose() {
    log_info "Проверка Docker Compose..."
    
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
        log_success "Docker Compose (встроенный) доступен"
    elif command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
        log_success "Docker Compose (отдельный) доступен"
    else
        log_error "Docker Compose не найден! Установите Docker Compose и попробуйте снова."
        exit 1
    fi
}

# Генерация переменных окружения
generate_env() {
    log_info "Создание файла переменных окружения..."
    
    # Генерация случайных паролей
    POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    SECRET_KEY=$(openssl rand -base64 48 | tr -d "=+/" | cut -c1-64)
    
    cat > .env << EOF
# ========================================
# Переменные окружения для тестового развертывания
# Сгенерировано автоматически $(date)
# ========================================

# База данных PostgreSQL
POSTGRES_DB=analyzer_db
POSTGRES_USER=analyzer_user
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# Приложение
SECRET_KEY=${SECRET_KEY}
DEBUG=true
LOG_LEVEL=DEBUG

# Дополнительные настройки
ENVIRONMENT=test
EOF
    
    log_success "Файл .env создан с безопасными паролями"
}

# Очистка предыдущего окружения
cleanup_previous() {
    log_info "Очистка предыдущего окружения..."
    
    # Остановка и удаление контейнеров
    if $DOCKER_COMPOSE_CMD -f docker-compose.test.yml ps -q 2>/dev/null | grep -q .; then
        log_info "Остановка существующих контейнеров..."
        $DOCKER_COMPOSE_CMD -f docker-compose.test.yml down --volumes --remove-orphans 2>/dev/null || true
    fi
    
    # Удаление образов
    log_info "Удаление старых образов..."
    docker rmi analyzer-backend-test:latest 2>/dev/null || true
    docker rmi analyzer-frontend-test:latest 2>/dev/null || true
    
    # Очистка данных
    if [ -d "data" ]; then
        log_info "Очистка данных..."
        rm -rf data/
    fi
    
    if [ -d "logs" ]; then
        log_info "Очистка логов..."
        rm -rf logs/
    fi
    
    log_success "Предыдущее окружение очищено"
}

# Создание необходимых директорий
create_directories() {
    log_info "Создание директорий..."
    
    mkdir -p data/postgres
    mkdir -p data/redis
    mkdir -p data/uploads
    mkdir -p logs
    
    # Установка правильных прав
    OS=$(detect_os)
    if [ "$OS" = "linux" ]; then
        chmod 755 data/postgres
        chmod 755 data/redis
        chmod 755 data/uploads
        chmod 755 logs
    fi
    
    log_success "Директории созданы"
}

# Запуск служб
deploy_services() {
    log_info "Запуск служб..."
    
    # Сборка образов
    log_info "Сборка Docker образов..."
    $DOCKER_COMPOSE_CMD -f docker-compose.test.yml build --no-cache
    
    # Запуск в detached режиме
    log_info "Запуск контейнеров..."
    $DOCKER_COMPOSE_CMD -f docker-compose.test.yml up -d
    
    log_success "Службы запущены"
}

# Ожидание готовности служб
wait_for_services() {
    log_info "Ожидание готовности служб..."
    
    local max_attempts=60
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:18000/health >/dev/null 2>&1; then
            log_success "Backend готов"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "Backend не готов после $max_attempts попыток"
            show_logs
            exit 1
        fi
        
        log_info "Ожидание готовности backend ($attempt/$max_attempts)..."
        sleep 5
        ((attempt++))
    done
    
    # Проверка frontend
    if curl -s http://localhost:8080 >/dev/null 2>&1; then
        log_success "Frontend готов"
    else
        log_warning "Frontend может быть недоступен"
    fi
    
    # Проверка PostgreSQL
    if $DOCKER_COMPOSE_CMD -f docker-compose.test.yml exec -T postgres pg_isready -U analyzer_user >/dev/null 2>&1; then
        log_success "PostgreSQL готов"
    else
        log_warning "PostgreSQL может быть недоступен"
    fi
    
    # Проверка Redis
    if $DOCKER_COMPOSE_CMD -f docker-compose.test.yml exec -T redis redis-cli ping >/dev/null 2>&1; then
        log_success "Redis готов"
    else
        log_warning "Redis может быть недоступен"
    fi
}

# Показать логи при ошибках
show_logs() {
    log_error "Показываю логи служб для диагностики:"
    echo "=================================="
    echo "Backend логи:"
    $DOCKER_COMPOSE_CMD -f docker-compose.test.yml logs --tail=20 backend
    echo "=================================="
}

# Тестирование API
test_api() {
    log_info "Тестирование API..."
    
    # Тест health endpoint
    if ! curl -s http://localhost:18000/health | grep -q "healthy"; then
        log_error "Health check не прошел"
        return 1
    fi
    
    # Тест списка отчетов
    if ! curl -s http://localhost:18000/api/v1/reports | grep -q "reports"; then
        log_error "API списка отчетов недоступен"
        return 1
    fi
    
    log_success "API работает корректно"
}

# Загрузка тестового отчета
upload_test_report() {
    log_info "Поиск и загрузка тестового отчета..."
    
    # Ищем существующие HTML отчеты в корневой папке
    cd ../
    local report_file
    report_file=$(find . -maxdepth 1 -name "*_report_analyzer.html" -type f 2>/dev/null | head -1)
    
    if [ -n "$report_file" ] && [ -f "$report_file" ]; then
        log_info "Найден существующий отчет: $report_file"
        
        # Загрузка отчета через API
        cd analyzer-platform
        if curl -s -X POST "http://localhost:18000/api/v1/reports/upload" \
             -F "file=@../$report_file" | grep -q "success\|report_id"; then
            log_success "Тестовый отчет загружен успешно"
        else
            log_warning "Не удалось загрузить тестовый отчет"
        fi
    else
        log_warning "HTML отчет не найден в корневой папке"
        log_info "Для тестирования загрузки создайте отчет анализатором или поместите готовый HTML файл в корневую папку"
    fi
    
    # Возвращаемся в директорию analyzer-platform
    cd "$(dirname "$0")"
}

# Показать информацию о доступе
show_access_info() {
    log_success "=============================================="
    log_success "УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!"
    log_success "=============================================="
    echo ""
    log_info "Доступ к системе:"
    log_info "🌐 Веб-интерфейс: http://localhost:8080"
    log_info "📡 API Backend:   http://localhost:18000"
    log_info "📖 API Docs:      http://localhost:18000/docs"
    log_info "❤️  Health Check: http://localhost:18000/health"
    echo ""
    log_info "База данных:"
    log_info "🐘 PostgreSQL:    localhost:15432"
    log_info "📦 Redis:         localhost:16379"
    echo ""
    log_info "Управление:"
    log_info "🔧 Остановить:    $DOCKER_COMPOSE_CMD -f docker-compose.test.yml down"
    log_info "📊 Логи:          $DOCKER_COMPOSE_CMD -f docker-compose.test.yml logs -f"
    log_info "🔍 Статус:        $DOCKER_COMPOSE_CMD -f docker-compose.test.yml ps"
    echo ""
}

# Основная функция
main() {
    log_info "=========================================="
    log_info "УСТАНОВКА ТЕСТОВОГО ОКРУЖЕНИЯ АНАЛИЗАТОРА"
    log_info "=========================================="
    
    # Переход в правильную директорию
    cd "$(dirname "$0")"
    
    # Проверки системы
    check_docker
    check_docker_compose
    
    # Подготовка
    generate_env
    cleanup_previous
    create_directories
    
    # Развертывание
    deploy_services
    wait_for_services
    
    # Тестирование
    test_api
    upload_test_report
    
    # Завершение
    show_access_info
}

# Обработка сигналов для корректного завершения
trap 'log_error "Установка прервана пользователем"; exit 1' SIGINT SIGTERM

# Запуск
main "$@" 