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

### Технологический стек
- **Backend**: FastAPI + SQLAlchemy + Pydantic
- **База данных**: PostgreSQL 15+
- **Кэширование**: Redis 7+
- **Веб-сервер**: Nginx
- **Контейнеризация**: Docker + Docker Compose

## ⚡ Быстрая установка

### Требования
- Docker 20.10+
- Docker Compose 2.0+

### Установка тестового окружения

```bash
# Клонирование репозитория
git clone <repository-url>
cd analyzer/analyzer-platform

# Автоматическая установка
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

### Доступ к системе

После успешной установки:
- **🌐 Веб-интерфейс**: http://localhost:8080
- **📡 API Backend**: http://localhost:18000
- **📖 API Docs**: http://localhost:18000/docs
- **❤️ Health Check**: http://localhost:18000/health

## 🔧 API

### Основные эндпоинты

```bash
# Получить список отчетов
GET /api/v1/reports

# Загрузить новый отчет
POST /api/v1/reports/upload

# Получить детали отчета
GET /api/v1/reports/{report_id}

# Статистика
GET /api/v1/reports/stats/summary
```

### Примеры использования

```bash
# Загрузка отчета
curl -X POST "http://localhost:18000/api/v1/reports/upload" \
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

## 📊 Мониторинг

### Управление системой

```bash
# Остановить все сервисы
docker compose -f analyzer-platform/docker-compose.test.yml down

# Посмотреть логи
docker compose -f analyzer-platform/docker-compose.test.yml logs -f

# Проверить статус
docker compose -f analyzer-platform/docker-compose.test.yml ps

# Перезапустить
cd analyzer-platform && ./install-test.sh
```

## 📦 Структура проекта

```
analyzer/
├── analyzer-platform/           # Веб-платформа
│   ├── backend/                # FastAPI backend
│   ├── frontend/               # HTML/CSS/JS frontend
│   ├── docker-compose.test.yml # Docker Compose конфигурация
│   ├── install-test.sh         # Скрипт автоматической установки
│   └── README.md              # Документация платформы
├── docs/                       # Документация
└── README.md                  # Этот файл
```

## 🛡️ Безопасность

- Автоматическая генерация безопасных паролей
- Изолированная сеть Docker
- Ограниченный доступ к портам (только localhost)
- Регулярные обновления зависимостей

## 🔍 Отладка

### Типичные проблемы

1. **Проблемы с Docker**
```bash
# Проверить статус Docker
docker info

# Перезапустить Docker Desktop (macOS/Windows)
```

2. **Проблемы с портами**
```bash
# Проверить занятые порты
lsof -i :8080
lsof -i :18000

# Остановить конфликтующие сервисы
```

3. **Полная переустановка**
```bash
cd analyzer-platform
docker compose -f docker-compose.test.yml down --volumes
./install-test.sh
```

## 🆘 Поддержка

Для получения поддержки:
1. Проверьте логи: `docker compose -f analyzer-platform/docker-compose.test.yml logs -f`
2. Проверьте статус: `docker compose -f analyzer-platform/docker-compose.test.yml ps`
3. Перезапустите: `cd analyzer-platform && ./install-test.sh`
4. Создайте issue в репозитории 