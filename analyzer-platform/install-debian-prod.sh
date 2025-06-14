#!/bin/bash

# ========================================
# Скрипт установки продакшен окружения веб-платформы анализатора
# ========================================

set -e  # Выход при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

log_debian() {
    echo -e "${PURPLE}[DEBIAN]${NC} $1"
}

# Проверка ОС
detect_os() {
    if [[ -f /etc/debian_version ]]; then
        echo "debian"
    elif [[ -f /etc/lsb-release ]] && grep -q "Ubuntu" /etc/lsb-release; then
        echo "ubuntu"
    else
        echo "unknown"
    fi
}

# Проверка версии Debian/Ubuntu
check_debian_version() {
    if [[ -f /etc/debian_version ]]; then
        local version=$(cat /etc/debian_version)
        log_debian "Обнаружена Debian версия: $version"
        
        if [[ "$version" =~ ^([0-9]+) ]]; then
            local major_version=${BASH_REMATCH[1]}
            if [[ $major_version -lt 11 ]]; then
                log_warning "Рекомендуется Debian 11+ для продакшена"
            fi
        fi
    elif [[ -f /etc/lsb-release ]]; then
        local version=$(grep DISTRIB_RELEASE /etc/lsb-release | cut -d= -f2)
        log_debian "Обнаружена Ubuntu версия: $version"
        
        if [[ "$version" < "20.04" ]]; then
            log_warning "Рекомендуется Ubuntu 20.04+ для продакшена"
        fi
    fi
}

# Проверка systemd
check_systemd() {
    if systemctl --version &>/dev/null; then
        log_success "Systemd обнаружен - интеграция будет доступна"
        SYSTEMD_AVAILABLE=true
    else
        log_warning "Systemd не обнаружен - интеграция недоступна"
        SYSTEMD_AVAILABLE=false
    fi
}

# Проверка APT пакетов
check_apt_packages() {
    log_debian "Проверка необходимых APT пакетов..."
    
    local required_packages=("curl" "gnupg" "ca-certificates" "lsb-release")
    local missing_packages=()
    
    for package in "${required_packages[@]}"; do
        if ! dpkg -l | grep -q "^ii  $package "; then
            missing_packages+=("$package")
        fi
    done
    
    if [[ ${#missing_packages[@]} -gt 0 ]]; then
        log_warning "Отсутствующие пакеты: ${missing_packages[*]}"
        log_info "Устанавливаем недостающие пакеты..."
        
        sudo apt-get update
        sudo apt-get install -y "${missing_packages[@]}"
    fi
    
    log_success "Все необходимые APT пакеты установлены"
}

# Проверка Docker
check_docker() {
    log_info "Проверка Docker..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен"
        log_info "Инструкции по установке: https://docs.docker.com/engine/install/debian/"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker не запущен или недоступен"
        log_info "Запустите: sudo systemctl start docker"
        exit 1
    fi
    
    local docker_version=$(docker --version | grep -oP '\d+\.\d+\.\d+')
    log_success "Docker установлен: версия $docker_version"
}

# Проверка Docker Compose
check_docker_compose() {
    log_info "Проверка Docker Compose..."
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose не установлен"
        log_info "Инструкции по установке: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    local compose_version=$(docker-compose --version | grep -oP '\d+\.\d+\.\d+')
    log_success "Docker Compose установлен: версия $compose_version"
}

# Проверка доступности Artifactory
check_artifactory() {
    log_info "Проверка доступности Artifactory..."
    
    if curl -s --max-time 10 https://___ > /dev/null; then
        log_success "Artifactory доступен"
    else
        log_warning "Artifactory недоступен - будут использованы fallback образы"
        export DOCKER_REGISTRY="docker.io"
        export PIP_INDEX_URL="https://pypi.org/simple"
        export PIP_TRUSTED_HOST="pypi.org"
    fi
}

# Авторизация в Docker Registry
docker_login() {
    log_info "Проверка авторизации в Docker Registry..."
    
    if [[ "${DOCKER_REGISTRY:-}" == " " ]]; then
        if ! docker pull hello-world:latest &> /dev/null; then
            log_warning "Требуется авторизация в registry"
            log_info "Выполните: docker login  "
            
            read -p "Хотите выполнить авторизацию сейчас? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                docker login  
            else
                log_warning "Используем публичные образы"
                export DOCKER_REGISTRY="docker.io"
            fi
        else
            log_success "Авторизация в  registry успешна"
        fi
    fi
}

# Генерация безопасных паролей
generate_passwords() {
    log_info "Генерация безопасных паролей..."
    
    mkdir -p secrets
    
    # PostgreSQL пароль
    if [[ ! -f secrets/postgres_password.txt ]]; then
        openssl rand -base64 32 > secrets/postgres_password.txt
        log_success "Сгенерирован пароль PostgreSQL"
    fi
    
    # Redis пароль  
    if [[ ! -f secrets/redis_password.txt ]]; then
        openssl rand -base64 32 > secrets/redis_password.txt
        log_success "Сгенерирован пароль Redis"
    fi
    
    # Secret key
    if [[ ! -f secrets/secret_key.txt ]]; then
        openssl rand -base64 64 > secrets/secret_key.txt
        log_success "Сгенерирован секретный ключ"
    fi
    
    chmod 600 secrets/*.txt
}

# Создание переменных окружения
create_env_file() {
    log_info "Создание файла переменных окружения..."
    
    cat > .env.debian-prod << EOF
# Debian Production Environment Variables
# Generated: $(date)

# Docker Registry Configuration
DOCKER_REGISTRY=${DOCKER_REGISTRY:- }
VERSION=${VERSION:-latest}

# Artifactory Configuration
PIP_INDEX_URL=${PIP_INDEX_URL:-https://___repository/pypi/simple}
PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST:-""}

# Database Configuration
POSTGRES_DB=analyzer_db
POSTGRES_USER=analyzer_user
POSTGRES_PASSWORD=$(cat secrets/postgres_password.txt)

# Redis Configuration
REDIS_PASSWORD=$(cat secrets/redis_password.txt)

# Application Configuration
SECRET_KEY=$(cat secrets/secret_key.txt)
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=production

# Security Configuration
ALLOWED_HOSTS=localhost,127.0.0.1

# Debian Specific
DEBIAN_FRONTEND=noninteractive
APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=1
TZ=Europe/Moscow

EOF

    log_success "Файл .env.debian-prod создан"
}

# Остановка предыдущих контейнеров
stop_previous_containers() {
    log_info "Остановка предыдущих контейнеров..."
    
    # Остановка тестового окружения
    if [[ -f docker-compose.test.yml ]]; then
        docker-compose -f docker-compose.test.yml down --volumes 2>/dev/null || true
    fi
    
    # Остановка CentOS продакшена
    if [[ -f docker-compose.centos-prod.yml ]]; then
        docker-compose -f docker-compose.centos-prod.yml down 2>/dev/null || true
    fi
    
    # Остановка предыдущего Debian продакшена
    docker-compose -f docker-compose.debian-prod.yml down 2>/dev/null || true
    
    log_success "Предыдущие контейнеры остановлены"
}

# Сборка и запуск контейнеров
build_and_start() {
    log_info "Сборка и запуск Debian продакшен контейнеров..."
    
    # Загрузка переменных окружения
    export $(cat .env.debian-prod | grep -v '^#' | xargs)
    
    # Сборка образов
    log_debian "Сборка backend образа..."
    docker-compose -f docker-compose.debian-prod.yml build --no-cache backend
    
    log_debian "Сборка frontend образа..."
    docker-compose -f docker-compose.debian-prod.yml build --no-cache frontend
    
    # Запуск сервисов
    log_debian "Запуск основных сервисов..."
    docker-compose -f docker-compose.debian-prod.yml up -d postgres redis
    
    # Ожидание готовности базы данных
    log_info "Ожидание готовности PostgreSQL..."
    timeout=60
    while [[ $timeout -gt 0 ]]; do
        if docker-compose -f docker-compose.debian-prod.yml exec -T postgres pg_isready -U analyzer_user -d analyzer_db &>/dev/null; then
            log_success "PostgreSQL готов"
            break
        fi
        sleep 2
        ((timeout-=2))
    done
    
    if [[ $timeout -le 0 ]]; then
        log_error "PostgreSQL не готов после 60 секунд"
        exit 1
    fi
    
    # Запуск backend и frontend
    log_debian "Запуск backend и frontend..."
    docker-compose -f docker-compose.debian-prod.yml up -d backend frontend
    
    log_success "Все контейнеры запущены"
}

# Проверка состояния сервисов
check_services() {
    log_info "Проверка состояния сервисов..."
    
    # Ожидание готовности backend
    log_info "Ожидание готовности backend API..."
    timeout=120
    while [[ $timeout -gt 0 ]]; do
        if curl -s http://localhost:8000/health | grep -q "healthy"; then
            log_success "Backend API готов"
            break
        fi
        sleep 3
        ((timeout-=3))
    done
    
    if [[ $timeout -le 0 ]]; then
        log_error "Backend API не готов после 120 секунд"
        return 1
    fi
    
    # Проверка frontend
    if curl -s -I http://localhost:80 | grep -q "200 OK"; then
        log_success "Frontend доступен"
    else
        log_warning "Frontend недоступен"
    fi
    
    # Проверка nginx status
    if curl -s http://localhost:8081/nginx_status | grep -q "server accepts handled requests"; then
        log_success "Nginx мониторинг доступен"
    else
        log_warning "Nginx мониторинг недоступен"
    fi
}

# Тестирование API
test_api() {
    log_info "Тестирование API..."
    
    # Тест health endpoint
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        log_success "Health check прошел"
    else
        log_error "Health check не прошел"
        return 1
    fi
    
    # Тест списка отчетов
    if curl -s http://localhost:8000/api/v1/reports | grep -q "reports"; then
        log_success "API списка отчетов работает"
    else
        log_error "API списка отчетов недоступен"
        return 1
    fi
}

# Установка systemd сервисов (опционально)
install_systemd_services() {
    if [[ "$SYSTEMD_AVAILABLE" == "true" ]]; then
        log_debian "Установка systemd сервисов..."
        
        # Создание systemd unit файла
        sudo tee /etc/systemd/system/analyzer-platform.service > /dev/null << EOF
[Unit]
Description=Analyzer Platform - Debian Production
Requires=docker.service
After=docker.service
RequiresMountsFor=/var/lib/docker

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/docker-compose -f docker-compose.debian-prod.yml up -d
ExecStop=/usr/bin/docker-compose -f docker-compose.debian-prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
        
        sudo systemctl daemon-reload
        sudo systemctl enable analyzer-platform.service
        
        log_success "Systemd сервис установлен"
        log_info "Управление: sudo systemctl {start|stop|status} analyzer-platform"
    fi
}

# Показать финальную информацию
show_final_info() {
    log_success "=============================================="
    log_success "DEBIAN ПРОДАКШЕН УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!"
    log_success "=============================================="
    
    echo -e "\n${BLUE}[INFO]${NC} Доступ к системе:"
    echo -e "${BLUE}[INFO]${NC} 🌐 Веб-интерфейс:     http://localhost"
    echo -e "${BLUE}[INFO]${NC} 📡 API Backend:       http://localhost:8000"
    echo -e "${BLUE}[INFO]${NC} 📖 API Docs:          http://localhost:8000/docs"
    echo -e "${BLUE}[INFO]${NC} ❤️  Health Check:     http://localhost:8000/health"
    echo -e "${BLUE}[INFO]${NC} 📊 Nginx Status:      http://localhost:8081/nginx_status"
    
    echo -e "\n${BLUE}[INFO]${NC} База данных:"
    echo -e "${BLUE}[INFO]${NC} 🐘 PostgreSQL:        localhost:5432"
    echo -e "${BLUE}[INFO]${NC} 📦 Redis:             localhost:6379"
    
    echo -e "\n${BLUE}[INFO]${NC} Управление:"
    echo -e "${BLUE}[INFO]${NC} 🔧 Остановить:        docker-compose -f docker-compose.debian-prod.yml down"
    echo -e "${BLUE}[INFO]${NC} 📊 Логи:              docker-compose -f docker-compose.debian-prod.yml logs -f"
    echo -e "${BLUE}[INFO]${NC} 📈 Мониторинг:        docker-compose -f docker-compose.debian-prod.yml --profile monitoring up -d"
    echo -e "${BLUE}[INFO]${NC} 💾 Бэкап:             docker-compose -f docker-compose.debian-prod.yml --profile backup up"
    
    if [[ "$SYSTEMD_AVAILABLE" == "true" ]]; then
        echo -e "\n${PURPLE}[DEBIAN]${NC} Systemd управление:"
        echo -e "${PURPLE}[DEBIAN]${NC} 🔧 Запуск:            sudo systemctl start analyzer-platform"
        echo -e "${PURPLE}[DEBIAN]${NC} 🔧 Остановка:         sudo systemctl stop analyzer-platform"
        echo -e "${PURPLE}[DEBIAN]${NC} 📊 Статус:            sudo systemctl status analyzer-platform"
    fi
    
    echo -e "\n${BLUE}[INFO]${NC} Файлы конфигурации:"
    echo -e "${BLUE}[INFO]${NC} 📄 Environment:       .env.debian-prod"
    echo -e "${BLUE}[INFO]${NC} 🔐 Secrets:           secrets/"
    echo -e "${BLUE}[INFO]${NC} 📊 Логи:              logs/"
    echo -e "${BLUE}[INFO]${NC} 💾 Данные:            data/"
}

# Главная функция
main() {
    echo -e "${PURPLE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PURPLE}║          УСТАНОВКА DEBIAN ПРОДАКШЕН ОКРУЖЕНИЯ             ║${NC}"
    echo -e "${PURPLE}║              Веб-платформа анализатора                     ║${NC}"
    echo -e "${PURPLE}╚════════════════════════════════════════════════════════════╝${NC}"
    
    # Определение ОС
    local os_type=$(detect_os)
    if [[ "$os_type" == "unknown" ]]; then
        log_error "Неподдерживаемая ОС. Требуется Debian или Ubuntu."
        exit 1
    fi
    
    log_debian "Обнаружена ОС: $os_type"
    
    # Проверки системы
    check_debian_version
    check_systemd
    check_apt_packages
    check_docker
    check_docker_compose
    check_artifactory
    docker_login
    
    # Установка
    generate_passwords
    create_env_file
    stop_previous_containers
    build_and_start
    
    # Проверки
    check_services
    test_api
    
    # Опциональные компоненты
    read -p "Установить systemd интеграцию? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_systemd_services
    fi
    
    # Финальная информация
    show_final_info
}

# Запуск скрипта
main "$@" 