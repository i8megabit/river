# Веб-платформа анализатора сетевых соединений

Веб-платформа для анализа и визуализации сетевых соединений, портов и системной активности.

## 🚀 Возможности

- **📊 Интерактивные отчеты**: Загрузка и просмотр HTML отчетов анализатора
- **🔍 Поиск и фильтрация**: Быстрый поиск по хостам, соединениям и портам  
- **📈 Аналитика**: Статистика соединений, портов и системной активности
- **🗄️ База данных**: Хранение и индексация отчетов в PostgreSQL
- **⚡ Кэширование**: Redis для быстрого доступа к данным
- **🔗 REST API**: Полноценный API для интеграции
- **📱 Адаптивный интерфейс**: Работает на всех устройствах

## 🏗️ Архитектура

### Backend (FastAPI)
```
analyzer-platform/backend/
├── api/              # REST API endpoints
├── core/             # Основная логика (конфигурация, БД, Redis)
├── models/           # SQLAlchemy модели
├── services/         # Бизнес-логика
└── main.py           # Точка входа приложения
```

### Технологический стек
- **Backend**: FastAPI + SQLAlchemy + Pydantic
- **База данных**: PostgreSQL 15+
- **Кэширование**: Redis 7+
- **Веб-сервер**: Nginx
- **Контейнеризация**: Docker + Docker Compose

## 🛠️ Установка и запуск

### Требования
- Docker 20.10+
- Docker Compose 2.0+

### ⚡ Быстрая установка

1. **Клонирование репозитория**
```bash
git clone <repository-url>
cd analyzer/analyzer-platform
```

2. **Автоматическая установка тестового окружения**
```bash
chmod +x install-test.sh
./install-test.sh
```

Скрипт автоматически:
- ✅ Проверит Docker и Docker Compose
- ✅ Создаст безопасные пароли и секреты
- ✅ Очистит предыдущие установки
- ✅ Соберёт и запустит все контейнеры
- ✅ Дождётся готовности всех сервисов
- ✅ Протестирует API
- ✅ Загрузит тестовый отчет (если найден)

### 3. Доступ к системе

После успешной установки:
- **🌐 Веб-интерфейс**: http://localhost:8080
- **📡 API Backend**: http://localhost:18000
- **📖 API Docs**: http://localhost:18000/docs
- **❤️ Health Check**: http://localhost:18000/health

### 4. Управление системой

```bash
# Остановить все сервисы
docker compose -f docker-compose.test.yml down

# Посмотреть логи
docker compose -f docker-compose.test.yml logs -f

# Проверить статус
docker compose -f docker-compose.test.yml ps

# Перезапустить
docker compose -f docker-compose.test.yml restart
```

## 🔧 API

### Основные эндпоинты

```bash
# Получить список отчетов
GET /api/v1/reports

# Загрузить новый отчет
POST /api/v1/reports/upload

# Получить детали отчета
GET /api/v1/reports/{report_id}

# Скачать отчет
GET /api/v1/reports/{report_id}/download

# Удалить отчет  
DELETE /api/v1/reports/{report_id}

# Статистика
GET /api/v1/reports/stats/summary
```

### Примеры использования

```bash
# Загрузка отчета
curl -X POST "http://localhost:18000/api/v1/reports/upload" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@report.html"

# Получение списка отчетов
curl "http://localhost:18000/api/v1/reports"

# Получение статистики
curl "http://localhost:18000/api/v1/reports/stats/summary"
```

## 🗄️ База данных

### Модели данных
- **SystemReport**: Основная информация об отчете
- **NetworkConnection**: Сетевые соединения  
- **NetworkPort**: Открытые порты
- **RemoteHost**: Удаленные хосты
- **ChangeHistory**: История изменений
- **NetworkInterface**: Сетевые интерфейсы

### Подключение к базе данных
```bash
# Подключение к PostgreSQL
docker compose -f docker-compose.test.yml exec postgres \
  psql -U analyzer_user -d analyzer_db

# Подключение к Redis
docker compose -f docker-compose.test.yml exec redis redis-cli
```

## 📊 Мониторинг

### Логи
```bash
# Логи всех сервисов
docker compose -f docker-compose.test.yml logs -f

# Логи конкретного сервиса
docker compose -f docker-compose.test.yml logs -f backend
docker compose -f docker-compose.test.yml logs -f postgres
docker compose -f docker-compose.test.yml logs -f redis
```

### Метрики
- Health check: http://localhost:18000/health
- API документация: http://localhost:18000/docs

## 🛡️ Безопасность

- Автоматическая генерация безопасных паролей
- Изолированная сеть Docker
- Ограниченный доступ к портам (только localhost)
- Регулярные обновления зависимостей

## 🔍 Отладка

### Типичные проблемы

1. **Не запускается база данных**
```bash
# Проверить логи PostgreSQL
docker compose -f docker-compose.test.yml logs postgres

# Пересоздать с очисткой данных
docker compose -f docker-compose.test.yml down --volumes
./install-test.sh
```

2. **Ошибки подключения к Redis**
```bash
# Проверить статус Redis
docker compose -f docker-compose.test.yml exec redis redis-cli ping

# Перезапустить Redis
docker compose -f docker-compose.test.yml restart redis
```

3. **Ошибки загрузки отчетов**
```bash
# Проверить логи backend
docker compose -f docker-compose.test.yml logs backend

# Проверить права на папку uploads
docker compose -f docker-compose.test.yml exec backend ls -la uploads/
```

## 📦 Структура проекта

```
analyzer-platform/
├── backend/                 # Backend приложение
│   ├── api/                # REST API
│   ├── core/               # Основная логика
│   ├── models/             # Модели базы данных
│   ├── services/           # Бизнес-логика
│   ├── requirements.txt    # Python зависимости
│   └── main.py            # Точка входа
├── frontend/               # Frontend файлы
│   ├── css/               # Стили
│   ├── js/                # JavaScript
│   └── components/        # HTML компоненты
├── docker-compose.test.yml # Конфигурация для тестирования
├── install-test.sh        # Скрипт автоматической установки
└── README.md             # Этот файл
```

## 🤝 Разработка

### Требования для разработки
- Python 3.11+
- Docker 20.10+
- Docker Compose 2.0+

### Запуск в режиме разработки
```bash
# Использовать готовый скрипт установки
./install-test.sh

# Или запустить вручную
docker compose -f docker-compose.test.yml up -d
```

## 🆘 Поддержка

Для получения поддержки:
1. Проверьте логи: `docker compose -f docker-compose.test.yml logs -f`
2. Проверьте статус: `docker compose -f docker-compose.test.yml ps`
3. Перезапустите: `./install-test.sh`
4. Создайте issue в репозитории 