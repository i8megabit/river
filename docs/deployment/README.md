# Руководство по развертыванию веб-платформы анализатора

## Обзор

Веб-платформа анализатора состоит из следующих компонентов:
- **Backend API** (FastAPI + Python)
- **Frontend** (HTML/CSS/JavaScript + Nginx)
- **База данных** (PostgreSQL)
- **Кэш** (Redis)
- **Оркестрация** (Docker Compose)

## Системные требования

### Минимальные требования
- **ОС**: Linux, macOS, Windows (с Docker)
- **Docker**: версия 20.0+
- **Docker Compose**: версия 2.0+
- **RAM**: 2GB
- **Диск**: 5GB свободного места
- **CPU**: 2 ядра

### Рекомендуемые требования
- **RAM**: 4GB+
- **Диск**: 20GB+ (для хранения отчетов)
- **CPU**: 4+ ядра
- **Сеть**: стабильное подключение к интернету

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd analyzer
```

### 2. Запуск через Docker Compose

```bash
# Переход в директорию веб-платформы
cd analyzer-platform

# Запуск всех сервисов
docker-compose up -d

# Проверка статуса сервисов
docker-compose ps
```

### 3. Проверка работы

Откройте браузер и перейдите по адресу: http://localhost:3000

API будет доступен по адресу: http://localhost:8000

## Подробное руководство по установке

### Шаг 1: Подготовка окружения

#### На Linux (Ubuntu/Debian):
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Docker Compose
sudo apt install docker-compose-plugin

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker
```

#### На macOS:
```bash
# Установка Docker Desktop
# Скачайте с https://www.docker.com/products/docker-desktop

# Или через Homebrew
brew install --cask docker
```

#### На Windows:
1. Установите Docker Desktop с официального сайта
2. Включите WSL2 support
3. Перезагрузите систему

### Шаг 2: Настройка конфигурации

#### Создание файла окружения:
```bash
cd analyzer-platform
cp .env.example .env
```

#### Редактирование .env файла:
```bash
# Основные настройки
APP_NAME=Анализатор Веб-Платформа
ENVIRONMENT=production
DEBUG=false

# База данных PostgreSQL
POSTGRES_SERVER=postgres
POSTGRES_PORT=5432
POSTGRES_USER=analyzer_user
POSTGRES_PASSWORD=your_strong_password_here
POSTGRES_DB=analyzer_db

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password_here

# Настройки сервера
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Безопасность
SECRET_KEY=your-super-secret-key-change-in-production

# Логирование
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=30

# Настройки файлов
MAX_UPLOAD_SIZE=104857600  # 100MB
REPORT_CLEANUP_DAYS=90
```

### Шаг 3: Настройка Docker Compose

#### Проверка docker-compose.yml:
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 30s
      timeout: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5

  backend:
    build: ./backend
    environment:
      - POSTGRES_SERVER=postgres
      - REDIS_HOST=redis
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    ports:
      - "8000:8000"

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  postgres_data:
  redis_data:
```

### Шаг 4: Запуск и проверка

#### Запуск сервисов:
```bash
# Сборка и запуск в фоновом режиме
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f

# Проверка статуса сервисов
docker-compose ps
```

#### Проверка работоспособности:
```bash
# Проверка API
curl http://localhost:8000/health

# Проверка фронтенда
curl http://localhost:3000

# Проверка базы данных
docker-compose exec postgres psql -U analyzer_user -d analyzer_db -c "\dt"
```

## Настройка в продакшене

### 1. Настройка SSL/TLS

#### Создание SSL сертификатов:
```bash
# Создание директории для сертификатов
mkdir -p ssl

# Генерация самоподписанного сертификата (для тестирования)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout ssl/nginx.key \
    -out ssl/nginx.crt \
    -subj "/C=RU/ST=Moscow/L=Moscow/O=Company/OU=IT/CN=analyzer.company.com"
```

#### Обновление Nginx конфигурации:
```nginx
server {
    listen 80;
    server_name analyzer.company.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name analyzer.company.com;

    ssl_certificate /etc/nginx/ssl/nginx.crt;
    ssl_certificate_key /etc/nginx/ssl/nginx.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. Настройка обратного прокси

#### Пример конфигурации для Nginx (внешний):
```nginx
upstream analyzer_backend {
    server localhost:8000;
}

upstream analyzer_frontend {
    server localhost:3000;
}

server {
    listen 80;
    server_name analyzer.company.com;

    # Основное приложение
    location / {
        proxy_pass http://analyzer_frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API
    location /api/ {
        proxy_pass http://analyzer_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Увеличиваем лимиты для загрузки файлов
        client_max_body_size 100M;
        proxy_request_buffering off;
    }
}
```

### 3. Настройка мониторинга

#### Добавление Prometheus метрик:
```yaml
# docker-compose.prod.yml
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
```

#### Пример prometheus.yml:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'analyzer-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
```

### 4. Резервное копирование

#### Создание скрипта бэкапа:
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Создание директории бэкапов
mkdir -p $BACKUP_DIR

# Бэкап базы данных
docker-compose exec -T postgres pg_dump -U analyzer_user analyzer_db > \
    $BACKUP_DIR/db_backup_$DATE.sql

# Бэкап файлов отчетов
tar -czf $BACKUP_DIR/reports_backup_$DATE.tar.gz ./uploads/

# Очистка старых бэкапов (старше 30 дней)
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

#### Настройка cron для автоматических бэкапов:
```bash
# Редактирование crontab
crontab -e

# Добавление строки для ежедневного бэкапа в 2:00
0 2 * * * /path/to/backup.sh >> /var/log/analyzer_backup.log 2>&1
```

## Управление сервисами

### Основные команды Docker Compose

```bash
# Запуск сервисов
docker-compose up -d

# Остановка сервисов
docker-compose down

# Перезапуск конкретного сервиса
docker-compose restart backend

# Просмотр логов
docker-compose logs -f backend

# Обновление образов
docker-compose pull
docker-compose up -d --build

# Масштабирование сервисов
docker-compose up -d --scale backend=3

# Очистка неиспользуемых ресурсов
docker system prune -a
```

### Обновление приложения

```bash
# 1. Резервное копирование
./backup.sh

# 2. Остановка сервисов
docker-compose down

# 3. Обновление кода
git pull origin main

# 4. Пересборка и запуск
docker-compose up -d --build

# 5. Проверка работоспособности
curl http://localhost:8000/health
```

## Мониторинг и отладка

### Проверка состояния сервисов

```bash
# Статус всех сервисов
docker-compose ps

# Логи конкретного сервиса
docker-compose logs backend

# Использование ресурсов
docker stats

# Подключение к контейнеру
docker-compose exec backend bash
```

### Распространенные проблемы и решения

#### Проблема: Сервис не запускается
```bash
# Проверка логов
docker-compose logs service_name

# Проверка конфигурации
docker-compose config

# Пересборка образа
docker-compose build --no-cache service_name
```

#### Проблема: База данных недоступна
```bash
# Проверка состояния PostgreSQL
docker-compose exec postgres pg_isready -U analyzer_user

# Подключение к базе данных
docker-compose exec postgres psql -U analyzer_user -d analyzer_db

# Проверка логов базы данных
docker-compose logs postgres
```

#### Проблема: Недостаток места на диске
```bash
# Очистка Docker системы
docker system prune -a

# Очистка старых образов
docker image prune -a

# Очистка томов
docker volume prune
```

### Настройка логирования

#### Конфигурация логирования в docker-compose.yml:
```yaml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
  
  frontend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
```

#### Централизованное логирование:
```yaml
# Добавление ELK stack
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.0.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"

  logstash:
    image: docker.elastic.co/logstash/logstash:8.0.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.0.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
```

## Интеграция с анализатором

### Автоматическая загрузка отчетов

#### Создание скрипта интеграции:
```bash
#!/bin/bash
# integration.sh

ANALYZER_PATH="/path/to/analyzer"
UPLOAD_URL="http://localhost:8000/api/v1/reports/upload"

# Запуск анализатора
cd $ANALYZER_PATH
python3 src/analyzer.py --enhanced

# Поиск созданного HTML отчета
REPORT_FILE=$(find . -name "*.html" -newer /tmp/last_upload 2>/dev/null | head -1)

if [ -n "$REPORT_FILE" ]; then
    # Загрузка отчета в веб-платформу
    curl -X POST "$UPLOAD_URL" \
         -F "file=@$REPORT_FILE" \
         -H "accept: application/json"
    
    # Обновление метки времени
    touch /tmp/last_upload
    
    echo "Report uploaded: $REPORT_FILE"
else
    echo "No new reports found"
fi
```

#### Настройка автоматического запуска:
```bash
# Добавление в crontab для запуска каждые 30 минут
*/30 * * * * /path/to/integration.sh >> /var/log/analyzer_integration.log 2>&1
```

## Производительность и оптимизация

### Настройка PostgreSQL

#### Оптимизация postgresql.conf:
```sql
-- Увеличение буферов
shared_buffers = 256MB
effective_cache_size = 1GB

-- Настройка WAL
wal_buffers = 16MB
checkpoint_completion_target = 0.9

-- Настройка планировщика
random_page_cost = 1.1
effective_io_concurrency = 200
```

### Настройка Redis

#### Оптимизация redis.conf:
```conf
# Максимальная память
maxmemory 512mb
maxmemory-policy allkeys-lru

# Сохранение на диск
save 900 1
save 300 10
save 60 10000
```

### Масштабирование

#### Горизонтальное масштабирование backend:
```yaml
services:
  backend:
    deploy:
      replicas: 3
      
  nginx:
    image: nginx
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
    ports:
      - "8000:80"
    depends_on:
      - backend
```

## Безопасность

### Настройки безопасности

1. **Изменение паролей по умолчанию**
2. **Настройка файрвола**
3. **Обновление зависимостей**
4. **Настройка HTTPS**
5. **Ограничение сетевого доступа**

#### Пример настройки файрвола:
```bash
# UFW (Ubuntu)
sudo ufw enable
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw deny 5432/tcp   # PostgreSQL (только внутренний доступ)
sudo ufw deny 6379/tcp   # Redis (только внутренний доступ)
```

## Дополнительная информация

- **[API документация](../api/README.md)** - подробное описание API
- **[Документация веб-интерфейса](../web-interface/README.md)** - руководство пользователя
- **[Примеры интеграции](../api/examples.md)** - готовые скрипты

## Поддержка

Для получения поддержки:
1. Проверьте логи сервисов
2. Ознакомьтесь с разделом "Распространенные проблемы"
3. Создайте issue в репозитории проекта
4. Обратитесь к команде разработки 