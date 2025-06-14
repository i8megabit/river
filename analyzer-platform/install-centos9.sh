#!/bin/bash

# ========================================
# Скрипт установки Анализатора на CentOS 9 с Podman Compose
# Автоматическая установка всех зависимостей и настройка production среды
# ========================================

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Логирование
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

# Проверка прав root
if [[ $EUID -eq 0 ]]; then
   error "Этот скрипт не должен запускаться от root. Используйте обычного пользователя с sudo."
fi

# Функция проверки команды
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Функция генерации случайного пароля
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

# Функция генерации секретного ключа
generate_secret_key() {
    openssl rand -hex 32
}

# Получение текущего IP адреса
get_server_ip() {
    # Пробуем несколько способов получения IP
    if command_exists ip; then
        ip route get 8.8.8.8 | awk '{print $7; exit}' 2>/dev/null || echo "127.0.0.1"
    elif command_exists hostname; then
        hostname -I | awk '{print $1}' 2>/dev/null || echo "127.0.0.1"
    else
        echo "127.0.0.1"
    fi
}

# Функция проверки статуса systemd службы
check_service_status() {
    local service_name=$1
    if systemctl is-active --quiet "$service_name"; then
        return 0
    else
        return 1
    fi
}

echo ""
echo "🚀 УСТАНОВКА АНАЛИЗАТОРА НА CENTOS 9 (PODMAN COMPOSE)"
echo "=================================================="
echo ""

# Проверяем CentOS 9
if ! grep -q "CentOS Linux release 9\|Rocky Linux release 9\|AlmaLinux release 9\|Red Hat Enterprise Linux release 9" /etc/redhat-release 2>/dev/null; then
    warning "Этот скрипт оптимизирован для CentOS 9 / RHEL 9 / Rocky Linux 9 / AlmaLinux 9"
    echo "Текущая система: $(cat /etc/redhat-release 2>/dev/null || echo 'Unknown')"
    read -p "Продолжить установку? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

log "Обновляем систему..."
sudo dnf update -y

log "Устанавливаем EPEL репозиторий..."
sudo dnf install -y epel-release

log "Устанавливаем необходимые пакеты..."
sudo dnf install -y \
    podman \
    podman-compose \
    curl \
    wget \
    git \
    openssl \
    python3 \
    python3-pip \
    firewalld \
    fail2ban \
    htop \
    tmux \
    nano

# Проверяем установку Podman
if ! command_exists podman; then
    error "Podman не установлен"
fi

# Проверяем установку Podman Compose
if ! command_exists podman-compose; then
    error "Podman Compose не установлен"
fi

success "Зависимости установлены"

log "Настраиваем пользователя для работы с Podman..."

# Включаем lingering для пользователя (чтобы контейнеры запускались без логина)
sudo loginctl enable-linger $(whoami)

# Создаем директории для пользователя
mkdir -p ~/.config/containers
mkdir -p ~/.local/share/containers/storage

# Настраиваем registries для Podman
cat > ~/.config/containers/registries.conf << EOF
[registries.search]
registries = ['docker.io', 'registry.fedoraproject.org', 'quay.io', 'registry.redhat.io']

[registries.insecure]
registries = []

[registries.block]
registries = []
EOF

success "Podman настроен для пользователя"

log "Настраиваем файервол..."

# Включаем и запускаем firewalld
sudo systemctl enable firewalld
sudo systemctl start firewalld

# Открываем порты
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --permanent --add-port=8443/tcp

# Перезагружаем правила
sudo firewall-cmd --reload

success "Файервол настроен"

log "Настраиваем SELinux..."

# Устанавливаем SELinux утилиты
sudo dnf install -y policycoreutils-python-utils

# Разрешаем Podman биндить контейнеры на стандартные порты
sudo setsebool -P container_manage_cgroup on
sudo setsebool -P container_use_cephfs on

success "SELinux настроен"

log "Проверяем рабочую директорию..."

# Проверяем, что мы в правильной директории
if [[ ! -f "docker-compose.production.yml" ]]; then
    error "Файл docker-compose.production.yml не найден. Убедитесь, что вы запускаете скрипт из директории analyzer-platform"
fi

log "Создаем необходимые директории..."

# Создаем директории с правильными правами
mkdir -p data/postgres data/redis logs ssl config/nginx

# Устанавливаем права на директории
chmod 755 data logs ssl config
chmod 700 data/postgres data/redis

success "Директории созданы"

log "Создаем файл переменных окружения..."

# Генерируем пароли и ключи
DB_PASSWORD=$(generate_password)
SECRET_KEY=$(generate_secret_key)
SERVER_IP=$(get_server_ip)

# Создаем .env файл
cat > .env << EOF
# ========================================
# Production Environment Variables
# ========================================

# Database Configuration
POSTGRES_DB=analyzer_db
POSTGRES_USER=analyzer_user
POSTGRES_PASSWORD=$DB_PASSWORD

# Application Security
SECRET_KEY=$SECRET_KEY

# Server Configuration
ALLOWED_HOSTS=localhost,127.0.0.1,$SERVER_IP

# SSL Configuration (если используется)
# SSL_CERT_PATH=/path/to/cert.pem
# SSL_KEY_PATH=/path/to/key.pem

# Backup Configuration
BACKUP_ENABLED=true
BACKUP_SCHEDULE="0 2 * * *"
BACKUP_RETENTION_DAYS=30

# Monitoring
ENABLE_METRICS=true
EOF

# Устанавливаем безопасные права на .env
chmod 600 .env

success "Файл окружения создан (.env)"

log "Создаем конфигурацию Nginx..."

mkdir -p config/nginx

cat > config/nginx/default.conf << 'EOF'
upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:80;
}

server {
    listen 80;
    server_name _;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-XSS-Protection "1; mode=block";
    add_header X-Content-Type-Options "nosniff";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    
    # API запросы к backend
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Health check
    location /health {
        proxy_pass http://backend/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Uploads
    location /uploads/ {
        proxy_pass http://backend/uploads/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml+rss application/atom+xml image/svg+xml;
}
EOF

success "Конфигурация Nginx создана"

log "Создаем скрипт управления..."

cat > manage.sh << 'EOF'
#!/bin/bash

# Скрипт управления Анализатором (CentOS 9 + Podman)

case "$1" in
    start)
        echo "🚀 Запуск Анализатора..."
        podman-compose -f docker-compose.production.yml up -d
        ;;
    stop)
        echo "🛑 Остановка Анализатора..."
        podman-compose -f docker-compose.production.yml down
        ;;
    restart)
        echo "🔄 Перезапуск Анализатора..."
        podman-compose -f docker-compose.production.yml restart
        ;;
    status)
        echo "📊 Статус сервисов:"
        podman-compose -f docker-compose.production.yml ps
        ;;
    logs)
        shift
        podman-compose -f docker-compose.production.yml logs "$@"
        ;;
    backup)
        echo "💾 Создание резервной копии БД..."
        podman exec analyzer-postgres-prod pg_dump -U analyzer_user analyzer_db | gzip > "backup_$(date +%Y%m%d_%H%M%S).sql.gz"
        echo "✅ Резервная копия создана"
        ;;
    update)
        echo "🔄 Обновление образов..."
        podman-compose -f docker-compose.production.yml pull
        podman-compose -f docker-compose.production.yml up -d --force-recreate
        ;;
    clean)
        echo "🧹 Очистка неиспользуемых образов..."
        podman image prune -f
        ;;
    *)
        echo "Использование: $0 {start|stop|restart|status|logs|backup|update|clean}"
        echo ""
        echo "Команды:"
        echo "  start   - Запустить все сервисы"
        echo "  stop    - Остановить все сервисы"
        echo "  restart - Перезапустить все сервисы"
        echo "  status  - Показать статус сервисов"
        echo "  logs    - Показать логи (можно указать сервис)"
        echo "  backup  - Создать резервную копию БД"
        echo "  update  - Обновить образы и перезапустить"
        echo "  clean   - Очистить неиспользуемые образы"
        exit 1
        ;;
esac
EOF

chmod +x manage.sh

success "Скрипт управления создан (manage.sh)"

log "Создаем systemd сервис для автозапуска..."

# Создаем systemd unit для пользователя
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/analyzer.service << EOF
[Unit]
Description=Analyzer Platform
Requires=podman.socket
After=podman.socket

[Service]
Type=oneshot
RemainAfterExit=true
WorkingDirectory=$PWD
ExecStart=/usr/bin/podman-compose -f docker-compose.production.yml up -d
ExecStop=/usr/bin/podman-compose -f docker-compose.production.yml down
TimeoutStartSec=0

[Install]
WantedBy=default.target
EOF

# Перезагружаем systemd и включаем сервис
systemctl --user daemon-reload
systemctl --user enable analyzer.service

success "Systemd сервис создан и включен"

log "Создаем скрипт мониторинга..."

cat > monitor.sh << 'EOF'
#!/bin/bash

# Скрипт мониторинга Анализатора

echo "🔍 МОНИТОРИНГ АНАЛИЗАТОРА"
echo "========================"
echo ""

# Проверка статуса контейнеров
echo "📊 Статус контейнеров:"
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Проверка использования ресурсов
echo "💾 Использование ресурсов:"
podman stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
echo ""

# Проверка здоровья сервисов
echo "🏥 Проверка здоровья:"
for container in analyzer-backend-prod analyzer-frontend-prod analyzer-postgres-prod analyzer-redis-prod; do
    if podman healthcheck run $container >/dev/null 2>&1; then
        echo "✅ $container: здоров"
    else
        echo "❌ $container: проблемы"
    fi
done
echo ""

# Размер БД
echo "📊 Размер базы данных:"
podman exec analyzer-postgres-prod psql -U analyzer_user -d analyzer_db -c "SELECT pg_size_pretty(pg_database_size('analyzer_db'));" 2>/dev/null || echo "БД недоступна"
echo ""

# Использование диска
echo "💽 Использование диска:"
df -h . | tail -n 1
echo ""

# Последние логи ошибок
echo "📝 Последние ошибки:"
podman-compose -f docker-compose.production.yml logs --tail=5 | grep -i error || echo "Ошибок не найдено"
EOF

chmod +x monitor.sh

success "Скрипт мониторинга создан (monitor.sh)"

log "Запускаем сервисы..."

# Запускаем через Podman Compose
podman-compose -f docker-compose.production.yml up -d

# Ждем запуска
sleep 30

log "Проверяем статус сервисов..."

# Проверка статуса
if podman-compose -f docker-compose.production.yml ps | grep -q "Up"; then
    success "Сервисы запущены"
else
    warning "Некоторые сервисы могут не запуститься с первого раза. Проверьте логи."
fi

log "Проверяем доступность API..."

# Проверка API
if curl -s http://localhost:28000/health >/dev/null; then
    success "API доступен"
else
    warning "API пока недоступен. Подождите немного и проверьте логи."
fi

echo ""
echo "🎉 УСТАНОВКА ЗАВЕРШЕНА!"
echo "====================="
echo ""
echo "📱 Доступ к приложению:"
echo "   🌐 Веб-интерфейс: http://$SERVER_IP или http://localhost"
echo "   🔌 API: http://$SERVER_IP:28000 или http://localhost:28000"
echo "   📊 API Документация: http://$SERVER_IP:28000/api/docs"
echo ""
echo "🛠️ Управление:"
echo "   ./manage.sh start    - Запуск"
echo "   ./manage.sh stop     - Остановка"
echo "   ./manage.sh status   - Статус"
echo "   ./manage.sh logs     - Логи"
echo "   ./manage.sh backup   - Резервная копия"
echo ""
echo "📊 Мониторинг:"
echo "   ./monitor.sh         - Проверка состояния"
echo ""
echo "🔐 Безопасность:"
echo "   - Пароли сохранены в файле .env (chmod 600)"
echo "   - Файервол настроен для портов 80, 443, 8080, 8443"
echo "   - SELinux настроен для работы с контейнерами"
echo ""
echo "⚙️ Системные сервисы:"
echo "   systemctl --user start analyzer    - Запуск через systemd"
echo "   systemctl --user enable analyzer   - Автозапуск при входе"
echo ""
warning "ВАЖНО: Сохраните файл .env в безопасном месте!"
echo ""

success "Установка завершена успешно! 🚀" 