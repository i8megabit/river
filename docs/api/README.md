# API Документация для Анализатора

## Обзор

Веб-платформа анализатора предоставляет RESTful API для управления отчетами системного анализа. API построен на FastAPI и поддерживает операции загрузки, просмотра, поиска и удаления отчетов.

## Базовый URL

```
http://localhost:8000/api/v1
```

## Аутентификация

В текущей версии API не требует аутентификации. В продакшене рекомендуется настроить аутентификацию.

## Формат ответов

Все ответы возвращаются в формате JSON. В случае ошибки возвращается объект с полем `detail`:

```json
{
  "detail": "Описание ошибки"
}
```

## Endpoints

### 1. Проверка состояния API

**GET** `/health`

Проверяет доступность API.

#### Пример с curl:
```bash
curl -X GET "http://localhost:8000/api/v1/health" \
     -H "accept: application/json"
```

#### Пример с Python:
```python
import requests

response = requests.get("http://localhost:8000/api/v1/health")
print(response.json())
```

#### Ответ:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "1.0.0"
}
```

---

### 2. Получение списка отчетов

**GET** `/reports`

Возвращает список всех загруженных отчетов.

#### Пример с curl:
```bash
curl -X GET "http://localhost:8000/api/v1/reports" \
     -H "accept: application/json"
```

#### Пример с Python:
```python
import requests

response = requests.get("http://localhost:8000/api/v1/reports")
data = response.json()

print(f"Всего отчетов: {data['total']}")
for report in data['reports']:
    print(f"- {report['hostname']}: {report['filename']}")
```

#### Ответ:
```json
{
  "reports": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "hostname": "myserver",
      "filename": "myserver_macos_network_report_2024-01-15_10-30-00.html",
      "generated_at": "2024-01-15T10:30:00.000Z",
      "os_name": "macOS",
      "total_connections": 45,
      "file_size": 156780,
      "report_hash": "a1b2c3d4e5f6",
      "tcp_ports_count": 12,
      "udp_ports_count": 8,
      "file_exists": true,
      "processing_status": "processed"
    }
  ],
  "total": 1
}
```

---

### 3. Загрузка отчета

**POST** `/reports/upload`

Загружает HTML отчет анализатора в систему.

#### Пример с curl:
```bash
curl -X POST "http://localhost:8000/api/v1/reports/upload" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@myserver_macos_network_report.html"
```

#### Пример с Python:
```python
import requests

# Загрузка файла
with open('myserver_macos_network_report.html', 'rb') as f:
    files = {'file': f}
    response = requests.post(
        "http://localhost:8000/api/v1/reports/upload",
        files=files
    )
    
if response.status_code == 200:
    data = response.json()
    print(f"Отчет загружен: {data['id']}")
    print(f"Статус дедупликации: {data['deduplication_status']}")
else:
    print(f"Ошибка: {response.json()}")
```

#### Ответ при успехе:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Отчет успешно загружен и обработан",
  "filename": "myserver_macos_network_report.html",
  "deduplication_status": "new_report",
  "report_hash": "a1b2c3d4e5f6",
  "processing_status": "processed"
}
```

#### Ответ при дубликате:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Найден дубликат отчета",
  "filename": "myserver_macos_network_report.html",
  "deduplication_status": "duplicate",
  "report_hash": "a1b2c3d4e5f6",
  "existing_report_id": "existing-uuid-here"
}
```

---

### 4. Получение детальной информации об отчете

**GET** `/reports/{report_id}`

Возвращает подробную информацию об отчете, включая все соединения, порты и статистику.

#### Пример с curl:
```bash
curl -X GET "http://localhost:8000/api/v1/reports/123e4567-e89b-12d3-a456-426614174000" \
     -H "accept: application/json"
```

#### Пример с Python:
```python
import requests

report_id = "123e4567-e89b-12d3-a456-426614174000"
response = requests.get(f"http://localhost:8000/api/v1/reports/{report_id}")

if response.status_code == 200:
    data = response.json()
    
    print(f"Хост: {data['hostname']}")
    print(f"ОС: {data['os_name']} {data['os_version']}")
    print(f"Соединений: {data['total_connections']}")
    
    # Вывод TCP портов
    print("\nTCP порты:")
    for port in data['tcp_ports'][:5]:  # Первые 5
        print(f"  {port['port']}: {port['description']}")
    
    # Вывод соединений
    print("\nСоединения:")
    for conn in data['connections'][:5]:  # Первые 5
        print(f"  {conn['local']} -> {conn['remote']['address']} ({conn['protocol']})")
else:
    print(f"Ошибка: {response.status_code}")
```

#### Ответ:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "hostname": "myserver",
  "os_name": "macOS",
  "os_version": "14.1",
  "total_connections": 45,
  "tcp_ports_count": 12,
  "udp_ports_count": 8,
  "tcp_ports": [
    {
      "port": 22,
      "description": "SSH (Secure Shell)",
      "status": "listening"
    }
  ],
  "udp_ports": [
    {
      "port": 53,
      "description": "DNS (Domain Name System)",
      "status": "listening"
    }
  ],
  "connections": [
    {
      "local": "192.168.1.100:22",
      "remote": {
        "address": "192.168.1.50:54321",
        "name": "client.local"
      },
      "protocol": "tcp",
      "process": "sshd",
      "first_seen": "2024-01-15T10:00:00",
      "last_seen": "2024-01-15T10:30:00"
    }
  ],
  "network_interfaces": [
    {
      "name": "en0",
      "packets_in": 12345,
      "packets_out": 9876,
      "bytes_in": 1234567,
      "bytes_out": 987654
    }
  ],
  "file_info": {
    "filename": "myserver_macos_network_report.html",
    "file_size": 156780,
    "generated_at": "2024-01-15T10:30:00"
  }
}
```

---

### 5. Скачивание отчета

**GET** `/reports/{report_id}/download`

Скачивает оригинальный HTML файл отчета.

#### Пример с curl:
```bash
curl -X GET "http://localhost:8000/api/v1/reports/123e4567-e89b-12d3-a456-426614174000/download" \
     -H "accept: text/html" \
     -o downloaded_report.html
```

#### Пример с Python:
```python
import requests

report_id = "123e4567-e89b-12d3-a456-426614174000"
response = requests.get(f"http://localhost:8000/api/v1/reports/{report_id}/download")

if response.status_code == 200:
    with open('downloaded_report.html', 'wb') as f:
        f.write(response.content)
    print("Отчет скачан")
else:
    print(f"Ошибка: {response.status_code}")
```

---

### 6. Удаление отчета

**DELETE** `/reports/{report_id}`

Удаляет отчет из системы (как из базы данных, так и файл).

#### Пример с curl:
```bash
curl -X DELETE "http://localhost:8000/api/v1/reports/123e4567-e89b-12d3-a456-426614174000" \
     -H "accept: application/json"
```

#### Пример с Python:
```python
import requests

report_id = "123e4567-e89b-12d3-a456-426614174000"
response = requests.delete(f"http://localhost:8000/api/v1/reports/{report_id}")

if response.status_code == 200:
    data = response.json()
    print(f"Отчет удален: {data['message']}")
else:
    print(f"Ошибка: {response.status_code}")
```

#### Ответ:
```json
{
  "message": "Отчет успешно удален",
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "files_removed": [
    "/app/uploads/myserver_macos_network_report.html"
  ]
}
```

---

### 7. Получение сводной статистики

**GET** `/reports/stats/summary`

Возвращает общую статистику по всем отчетам в системе.

#### Пример с curl:
```bash
curl -X GET "http://localhost:8000/api/v1/reports/stats/summary" \
     -H "accept: application/json"
```

#### Пример с Python:
```python
import requests

response = requests.get("http://localhost:8000/api/v1/reports/stats/summary")
data = response.json()

print(f"Всего отчетов: {data['total_reports']}")
print(f"Уникальных хостов: {data['unique_hosts']}")
print(f"Общее количество соединений: {data['total_connections']}")
print(f"Общее количество портов: {data['total_ports']}")
```

#### Ответ:
```json
{
  "total_reports": 25,
  "unique_hosts": 18,
  "total_connections": 1250,
  "total_ports": 180,
  "most_common_os": "Ubuntu",
  "latest_report": "2024-01-15T10:30:00",
  "storage_used_mb": 45.6
}
```

---

## Примеры рабочих сценариев

### Полный цикл работы с API

```python
import requests
import json

# 1. Проверим состояние API
health = requests.get("http://localhost:8000/api/v1/health")
print(f"API статус: {health.json()['status']}")

# 2. Загрузим отчет
with open('myserver_report.html', 'rb') as f:
    upload_response = requests.post(
        "http://localhost:8000/api/v1/reports/upload",
        files={'file': f}
    )

if upload_response.status_code == 200:
    report_data = upload_response.json()
    report_id = report_data['id']
    print(f"Отчет загружен с ID: {report_id}")
    
    # 3. Получим детальную информацию
    details = requests.get(f"http://localhost:8000/api/v1/reports/{report_id}")
    if details.status_code == 200:
        report_details = details.json()
        print(f"Хост: {report_details['hostname']}")
        print(f"Соединений: {report_details['total_connections']}")
    
    # 4. Получим общую статистику
    stats = requests.get("http://localhost:8000/api/v1/reports/stats/summary")
    if stats.status_code == 200:
        stats_data = stats.json()
        print(f"Всего отчетов в системе: {stats_data['total_reports']}")
```

### Мониторинг через API

```python
import requests
import time

def monitor_system():
    """Мониторинг системы через API"""
    while True:
        try:
            # Проверяем health
            health = requests.get("http://localhost:8000/api/v1/health", timeout=5)
            
            if health.status_code == 200:
                # Получаем статистику
                stats = requests.get("http://localhost:8000/api/v1/reports/stats/summary")
                if stats.status_code == 200:
                    data = stats.json()
                    print(f"[{time.strftime('%H:%M:%S')}] Отчетов: {data['total_reports']}, "
                          f"Хостов: {data['unique_hosts']}")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Ошибка получения статистики")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] API недоступен")
                
        except requests.exceptions.ConnectionError:
            print(f"[{time.strftime('%H:%M:%S')}] Соединение с API потеряно")
            
        time.sleep(30)  # Проверяем каждые 30 секунд

# Запуск мониторинга
# monitor_system()
```

## Коды ошибок

| Код | Описание |
|-----|----------|
| 200 | Успешный запрос |
| 400 | Неправильный запрос (некорректные данные) |
| 404 | Отчет не найден |
| 409 | Конфликт (дубликат отчета) |
| 422 | Ошибка валидации данных |
| 500 | Внутренняя ошибка сервера |

## Ограничения

- Максимальный размер загружаемого файла: 100MB
- Поддерживаемые форматы файлов: HTML (созданные анализатором)
- Максимальное количество запросов: не ограничено (в продакшене рекомендуется настроить rate limiting)

## Дополнительная информация

- [Руководство по развертыванию](../deployment/README.md)
- [Документация веб-интерфейса](../web-interface/README.md)
- [Примеры интеграции](./examples.md)

## Поддержка

Для получения поддержки или сообщения об ошибках создайте issue в репозитории проекта. 