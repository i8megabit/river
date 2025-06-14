# Механизм дедупликации отчетов

## Обзор

Веб-платформа анализатора теперь включает механизм дедупликации отчетов на основе хеш-id, который предотвращает сохранение дубликатов отчетов от одной и той же системы.

## Как это работает

### 1. Генерация хеша отчета

При загрузке отчета система генерирует уникальный хеш на основе:
- Имени хоста системы
- Названия и версии ОС
- Ключевых метрик (количество соединений, TCP/UDP портов)

```python
# Пример компонентов хеша:
hash_components = [
    'my-server',           # hostname
    'macOS',              # os_name
    '14.5.0',            # os_version
    '15',                # total_connections
    '8',                 # tcp_ports_count
    '3'                  # udp_ports_count
]
```

### 2. Проверка дубликатов

При загрузке нового отчета:
1. Генерируется хеш для нового отчета
2. Проверяется, есть ли в базе данных отчет с таким же хешем
3. Если найден дубликат - старый отчет удаляется (файл + запись в БД)
4. Новый отчет сохраняется с тем же хеш-id

### 3. Структура базы данных

В таблицу `system_reports` добавлено поле:
```sql
report_hash VARCHAR(64) UNIQUE NOT NULL
```

С индексами:
- Уникальный индекс на `report_hash`
- Составной индекс на `(hostname, report_hash)`

## Использование

### Загрузка отчета через API

```bash
curl -X POST "http://localhost:8000/api/v1/reports/upload" \
     -F "file=@my_report.html"
```

Ответ при первой загрузке:
```json
{
    "message": "Отчет успешно загружен",
    "report_id": "12345678-1234-5678-9abc-123456789012",
    "report_hash": "a1b2c3d4e5f6789a",
    "filename": "my_report.html",
    "saved_as": "report_a1b2c3d4e5f6789a.html",
    "hostname": "my-server",
    "is_replacement": false
}
```

Ответ при загрузке дубликата:
```json
{
    "message": "Отчет успешно загружен (заменен дубликат)",
    "report_id": "87654321-4321-8765-cba9-876543210987",
    "report_hash": "a1b2c3d4e5f6789a",
    "filename": "my_report_updated.html",
    "saved_as": "report_a1b2c3d4e5f6789a.html",
    "hostname": "my-server",
    "is_replacement": true,
    "replaced_report": {
        "id": "12345678-1234-5678-9abc-123456789012",
        "hostname": "my-server",
        "generated_at": "2024-12-27T10:30:00"
    }
}
```

### Получение списка отчетов

```bash
curl "http://localhost:8000/api/v1/reports"
```

Ответ включает информацию о хеше:
```json
{
    "reports": [
        {
            "id": "87654321-4321-8765-cba9-876543210987",
            "hostname": "my-server",
            "filename": "report_a1b2c3d4e5f6789a.html",
            "report_hash": "a1b2c3d4e5f6789a",
            "total_connections": 15,
            "tcp_ports_count": 8,
            "udp_ports_count": 3
        }
    ],
    "total": 1
}
```

## Установка и настройка

### 1. Применение миграции

Перед использованием необходимо применить миграцию базы данных:

```bash
cd analyzer-platform/backend
python apply_migration.py
```

### 2. Обновление зависимостей

Убедитесь, что установлены все необходимые пакеты:
```bash
pip install beautifulsoup4 hashlib
```

### 3. Запуск веб-платформы

```bash
cd analyzer-platform
docker-compose up -d
```

## Тестирование

Для проверки работы механизма дедупликации используйте тестовый скрипт:

```bash
python test_deduplication.py
```

Скрипт выполнит следующие тесты:
1. Загрузка первого отчета
2. Загрузка дубликата (должен заменить первый)
3. Загрузка отчета с другими параметрами (должен создать новый)
4. Проверка правильности работы хеширования

## Технические детали

### Алгоритм хеширования

```python
def generate_report_hash(file_path, metadata=None):
    hash_components = [
        metadata.get('hostname', 'unknown'),
        metadata.get('os_name', ''),
        metadata.get('os_version', ''),
        str(metadata.get('total_connections', 0)),
        str(metadata.get('tcp_ports_count', 0)),
        str(metadata.get('udp_ports_count', 0)),
    ]
    
    hash_string = '|'.join(str(component).strip() for component in hash_components)
    hash_object = hashlib.sha256(hash_string.encode('utf-8'))
    return hash_object.hexdigest()[:16]  # Первые 16 символов
```

### Именование файлов

Загруженные отчеты сохраняются с именами на основе хеша:
```
report_{hash}.html
```

Например: `report_a1b2c3d4e5f6789a.html`

### Каскадное удаление

При удалении отчета с дубликатом автоматически удаляются:
- Запись из таблицы `system_reports`
- Связанные записи из таблиц `network_connections`, `network_ports`, etc.
- Файл отчета с диска

## Преимущества

1. **Предотвращение дубликатов**: Автоматическое обнаружение и замена дубликатов
2. **Экономия места**: Нет избыточного хранения одинаковых отчетов
3. **Целостность данных**: Всегда актуальная версия отчета для каждой системы
4. **Быстрый поиск**: Эффективные индексы для поиска по хешу
5. **Простота использования**: Прозрачная работа без изменения пользовательского интерфейса

## Ограничения

1. **Чувствительность к изменениям**: Даже незначительные изменения в метриках создают новый хеш
2. **Коллизии хешей**: Теоретически возможны, но крайне маловероятны
3. **Требует миграции**: Существующие установки требуют обновления БД

## Устранение неполадок

### Ошибка "report_hash field missing"

Убедитесь, что применена миграция:
```bash
python apply_migration.py
```

### Дубликаты все еще создаются

Проверьте логи на предмет ошибок генерации хеша:
```bash
docker-compose logs backend
```

### Проблемы с парсингом HTML

Убедитесь, что HTML отчеты имеют правильную структуру с элементами:
- `<title>Кумулятивный отчет анализатора - {hostname}</title>`
- `<div class="header-info-item">💻 ОС: {os_name}</div>`
- `<div class="stat-number">{connections}</div>` 