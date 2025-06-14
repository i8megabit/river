# Примеры использования API

## Обзор

Данный документ содержит практические примеры использования API веб-платформы анализатора. Примеры включают готовые скрипты на Python и bash для автоматизации работы с отчетами.

## Быстрые примеры

### Проверка состояния API

```bash
# Быстрая проверка
curl -s http://localhost:8000/api/v1/health | jq '.'
```

```python
import requests

def check_api_health():
    try:
        response = requests.get("http://localhost:8000/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("✅ API доступен")
            return True
        else:
            print(f"❌ API недоступен: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка подключения: {e}")
        return False
```

### Загрузка одного отчета

```bash
#!/bin/bash
# upload_report.sh
REPORT_FILE="$1"
API_URL="http://localhost:8000/api/v1/reports/upload"

if [ -z "$REPORT_FILE" ]; then
    echo "Использование: $0 <путь_к_отчету.html>"
    exit 1
fi

if [ ! -f "$REPORT_FILE" ]; then
    echo "Файл $REPORT_FILE не найден"
    exit 1
fi

echo "Загружаем $REPORT_FILE..."
curl -X POST "$API_URL" \
     -F "file=@$REPORT_FILE" \
     -H "accept: application/json" | jq '.'
```

```python
def upload_report(file_path):
    """Загружает отчет в систему"""
    import requests
    
    url = "http://localhost:8000/api/v1/reports/upload"
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, files=files)
            
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Отчет загружен: {data['id']}")
            print(f"📊 Статус: {data['deduplication_status']}")
            return data['id']
        else:
            print(f"❌ Ошибка загрузки: {response.status_code}")
            print(response.text)
            return None
            
    except FileNotFoundError:
        print(f"❌ Файл {file_path} не найден")
        return None
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None
```

## Массовые операции

### Загрузка множественных отчетов

```python
#!/usr/bin/env python3
"""
Скрипт для массовой загрузки отчетов
"""
import os
import requests
import time
from pathlib import Path

class ReportUploader:
    def __init__(self, api_base_url="http://localhost:8000/api/v1"):
        self.api_base_url = api_base_url
        self.upload_url = f"{api_base_url}/reports/upload"
        
    def upload_file(self, file_path):
        """Загружает один файл"""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(self.upload_url, files=files)
                
            return response.status_code == 200, response.json()
        except Exception as e:
            return False, {'error': str(e)}
    
    def upload_directory(self, directory_path, pattern="*.html"):
        """Загружает все HTML файлы из директории"""
        directory = Path(directory_path)
        html_files = list(directory.glob(pattern))
        
        if not html_files:
            print(f"В директории {directory_path} не найдены HTML файлы")
            return
        
        print(f"Найдено {len(html_files)} файлов для загрузки")
        
        results = {"success": 0, "errors": 0, "duplicates": 0}
        
        for file_path in html_files:
            print(f"Загружаем {file_path.name}...", end=" ")
            
            success, data = self.upload_file(file_path)
            
            if success:
                status = data.get('deduplication_status', 'unknown')
                if status == 'duplicate':
                    results["duplicates"] += 1
                    print("🔄 дубликат")
                else:
                    results["success"] += 1
                    print("✅ успешно")
            else:
                results["errors"] += 1
                print(f"❌ ошибка: {data.get('error', 'unknown')}")
            
            # Пауза между загрузками
            time.sleep(0.5)
        
        print(f"\n📊 Результаты:")
        print(f"✅ Успешно: {results['success']}")
        print(f"🔄 Дубликаты: {results['duplicates']}")
        print(f"❌ Ошибки: {results['errors']}")

# Использование
if __name__ == "__main__":
    uploader = ReportUploader()
    uploader.upload_directory("./reports")
```

### Bash версия для массовой загрузки

```bash
#!/bin/bash
# bulk_upload.sh

API_URL="http://localhost:8000/api/v1/reports/upload"
REPORTS_DIR="${1:-./reports}"

if [ ! -d "$REPORTS_DIR" ]; then
    echo "Директория $REPORTS_DIR не найдена"
    exit 1
fi

SUCCESS=0
ERRORS=0
DUPLICATES=0

echo "Загружаем отчеты из $REPORTS_DIR..."

for file in "$REPORTS_DIR"/*.html; do
    if [ ! -f "$file" ]; then
        continue
    fi
    
    filename=$(basename "$file")
    echo -n "Загружаем $filename... "
    
    response=$(curl -s -X POST "$API_URL" -F "file=@$file" -H "accept: application/json")
    status=$(echo "$response" | jq -r '.deduplication_status // "error"')
    
    case "$status" in
        "new_report")
            echo "✅ успешно"
            ((SUCCESS++))
            ;;
        "duplicate")
            echo "🔄 дубликат"
            ((DUPLICATES++))
            ;;
        *)
            echo "❌ ошибка"
            ((ERRORS++))
            ;;
    esac
    
    sleep 0.5
done

echo ""
echo "📊 Результаты:"
echo "✅ Успешно: $SUCCESS"
echo "🔄 Дубликаты: $DUPLICATES"
echo "❌ Ошибки: $ERRORS"
```

## Мониторинг и аналитика

### Скрипт мониторинга системы

```python
#!/usr/bin/env python3
"""
Скрипт для мониторинга состояния веб-платформы
"""
import requests
import time
import json
from datetime import datetime

class AnalyzerMonitor:
    def __init__(self, api_base_url="http://localhost:8000/api/v1"):
        self.api_base_url = api_base_url
        
    def get_health(self):
        """Проверяет здоровье API"""
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=5)
            return response.status_code == 200, response.json()
        except Exception as e:
            return False, {'error': str(e)}
    
    def get_stats(self):
        """Получает статистику системы"""
        try:
            response = requests.get(f"{self.api_base_url}/reports/stats/summary", timeout=10)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, {'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return False, {'error': str(e)}
    
    def get_reports_list(self):
        """Получает список отчетов"""
        try:
            response = requests.get(f"{self.api_base_url}/reports", timeout=10)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, {'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return False, {'error': str(e)}
    
    def monitor_loop(self, interval=60):
        """Основной цикл мониторинга"""
        print("🔍 Запуск мониторинга...")
        print(f"📊 Интервал проверки: {interval} секунд")
        print("-" * 50)
        
        while True:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Проверяем здоровье API
            health_ok, health_data = self.get_health()
            
            if health_ok:
                # Получаем статистику
                stats_ok, stats_data = self.get_stats()
                
                if stats_ok:
                    print(f"[{timestamp}] ✅ API работает")
                    print(f"  📊 Отчетов: {stats_data.get('total_reports', 'N/A')}")
                    print(f"  🖥️  Хостов: {stats_data.get('unique_hosts', 'N/A')}")
                    print(f"  🔗 Соединений: {stats_data.get('total_connections', 'N/A')}")
                    print(f"  🚪 Портов: {stats_data.get('total_ports', 'N/A')}")
                    print(f"  💾 Хранилище: {stats_data.get('storage_used_mb', 'N/A')} MB")
                else:
                    print(f"[{timestamp}] ⚠️ API работает, но статистика недоступна")
                    print(f"  ❌ Ошибка: {stats_data.get('error', 'unknown')}")
            else:
                print(f"[{timestamp}] ❌ API недоступен")
                print(f"  ❌ Ошибка: {health_data.get('error', 'unknown')}")
            
            print("-" * 50)
            time.sleep(interval)

# Использование
if __name__ == "__main__":
    monitor = AnalyzerMonitor()
    try:
        monitor.monitor_loop(interval=30)
    except KeyboardInterrupt:
        print("\n🛑 Мониторинг остановлен")
```

### Генерация отчета о состоянии

```python
#!/usr/bin/env python3
"""
Генератор отчета о состоянии системы
"""
import requests
import json
from datetime import datetime
from collections import Counter

class StatusReporter:
    def __init__(self, api_base_url="http://localhost:8000/api/v1"):
        self.api_base_url = api_base_url
        
    def generate_report(self, output_file="status_report.json"):
        """Генерирует полный отчет о состоянии системы"""
        report = {
            "generated_at": datetime.now().isoformat(),
            "api_health": None,
            "summary_stats": None,
            "reports_analysis": None,
            "recommendations": []
        }
        
        # Проверяем здоровье API
        try:
            health_response = requests.get(f"{self.api_base_url}/health", timeout=5)
            report["api_health"] = {
                "status": "healthy" if health_response.status_code == 200 else "unhealthy",
                "response_time_ms": health_response.elapsed.total_seconds() * 1000,
                "data": health_response.json() if health_response.status_code == 200 else None
            }
        except Exception as e:
            report["api_health"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Получаем статистику
        try:
            stats_response = requests.get(f"{self.api_base_url}/reports/stats/summary", timeout=10)
            if stats_response.status_code == 200:
                report["summary_stats"] = stats_response.json()
        except Exception as e:
            report["summary_stats"] = {"error": str(e)}
        
        # Анализируем отчеты
        try:
            reports_response = requests.get(f"{self.api_base_url}/reports", timeout=10)
            if reports_response.status_code == 200:
                reports_data = reports_response.json()
                report["reports_analysis"] = self._analyze_reports(reports_data["reports"])
        except Exception as e:
            report["reports_analysis"] = {"error": str(e)}
        
        # Генерируем рекомендации
        report["recommendations"] = self._generate_recommendations(report)
        
        # Сохраняем отчет
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"📊 Отчет сохранен в {output_file}")
        return report
    
    def _analyze_reports(self, reports):
        """Анализирует список отчетов"""
        if not reports:
            return {"error": "No reports available"}
        
        # Анализ операционных систем
        os_counter = Counter()
        total_connections = 0
        total_size = 0
        
        for report in reports:
            os_name = report.get("os_name", "unknown")
            os_counter[os_name] += 1
            total_connections += report.get("total_connections", 0)
            total_size += report.get("file_size", 0)
        
        return {
            "total_reports": len(reports),
            "os_distribution": dict(os_counter),
            "average_connections_per_report": total_connections / len(reports) if reports else 0,
            "total_storage_bytes": total_size,
            "average_file_size_bytes": total_size / len(reports) if reports else 0
        }
    
    def _generate_recommendations(self, report):
        """Генерирует рекомендации на основе анализа"""
        recommendations = []
        
        # Проверяем здоровье API
        if report["api_health"]["status"] != "healthy":
            recommendations.append({
                "type": "critical",
                "message": "API недоступен или работает с ошибками",
                "action": "Проверьте логи сервера и перезапустите сервисы"
            })
        
        # Проверяем использование места
        if report["summary_stats"] and "storage_used_mb" in report["summary_stats"]:
            storage_mb = report["summary_stats"]["storage_used_mb"]
            if storage_mb > 1000:  # Больше 1GB
                recommendations.append({
                    "type": "warning",
                    "message": f"Высокое использование дискового пространства: {storage_mb} MB",
                    "action": "Рассмотрите возможность очистки старых отчетов"
                })
        
        # Проверяем количество отчетов
        if report["summary_stats"] and "total_reports" in report["summary_stats"]:
            total_reports = report["summary_stats"]["total_reports"]
            if total_reports > 1000:
                recommendations.append({
                    "type": "info",
                    "message": f"Большое количество отчетов: {total_reports}",
                    "action": "Рассмотрите архивирование старых отчетов"
                })
        
        return recommendations

# Использование
if __name__ == "__main__":
    reporter = StatusReporter()
    report = reporter.generate_report("status_report.json")
    
    # Выводим краткую сводку
    print("\n📊 КРАТКАЯ СВОДКА:")
    print(f"🔗 API: {report['api_health']['status']}")
    
    if report["summary_stats"] and "total_reports" in report["summary_stats"]:
        stats = report["summary_stats"]
        print(f"📄 Отчетов: {stats['total_reports']}")
        print(f"🖥️ Хостов: {stats['unique_hosts']}")
        print(f"💾 Хранилище: {stats['storage_used_mb']} MB")
    
    if report["recommendations"]:
        print(f"\n⚠️ Рекомендации ({len(report['recommendations'])}):")
        for rec in report["recommendations"]:
            icon = "🔴" if rec["type"] == "critical" else "🟡" if rec["type"] == "warning" else "ℹ️"
            print(f"  {icon} {rec['message']}")
```

## Интеграция с анализатором

### Автоматическая интеграция

```python
#!/usr/bin/env python3
"""
Полная интеграция: запуск анализатора + загрузка отчета
"""
import subprocess
import os
import time
import requests
from pathlib import Path

class AnalyzerIntegration:
    def __init__(self, analyzer_path="./src/analyzer.py", api_url="http://localhost:8000/api/v1"):
        self.analyzer_path = analyzer_path
        self.api_url = api_url
        self.upload_url = f"{api_url}/reports/upload"
        
    def run_analyzer(self, enhanced=True):
        """Запускает анализатор"""
        cmd = ["python3", self.analyzer_path]
        if enhanced:
            cmd.append("--enhanced")
        
        print("🔍 Запуск анализатора...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print("✅ Анализатор завершен успешно")
                return True
            else:
                print(f"❌ Ошибка анализатора: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print("❌ Таймаут выполнения анализатора")
            return False
        except Exception as e:
            print(f"❌ Ошибка запуска анализатора: {e}")
            return False
    
    def find_latest_report(self, search_dir=".", pattern="*.html"):
        """Находит последний созданный отчет"""
        path = Path(search_dir)
        html_files = list(path.glob(pattern))
        
        if not html_files:
            return None
        
        # Сортируем по времени модификации
        latest_file = max(html_files, key=lambda x: x.stat().st_mtime)
        
        # Проверяем, что файл создан недавно (в течение 10 минут)
        if time.time() - latest_file.stat().st_mtime < 600:
            return latest_file
        
        return None
    
    def upload_report(self, file_path):
        """Загружает отчет в веб-платформу"""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(self.upload_url, files=files)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Отчет загружен: {data['id']}")
                print(f"📊 Статус: {data['deduplication_status']}")
                return True
            else:
                print(f"❌ Ошибка загрузки: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка загрузки: {e}")
            return False
    
    def run_full_cycle(self):
        """Выполняет полный цикл: анализ + загрузка"""
        print("🚀 Запуск полного цикла анализа...")
        
        # Запускаем анализатор
        if not self.run_analyzer():
            return False
        
        # Ищем созданный отчет
        print("🔍 Поиск созданного отчета...")
        report_file = self.find_latest_report()
        
        if not report_file:
            print("❌ Новый отчет не найден")
            return False
        
        print(f"📄 Найден отчет: {report_file}")
        
        # Загружаем отчет
        return self.upload_report(report_file)

# Использование
if __name__ == "__main__":
    integration = AnalyzerIntegration()
    success = integration.run_full_cycle()
    
    if success:
        print("🎉 Полный цикл выполнен успешно!")
    else:
        print("💥 Ошибка выполнения цикла")
```

### Cron интеграция

```bash
#!/bin/bash
# cron_integration.sh - Скрипт для добавления в cron

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYZER_DIR="$SCRIPT_DIR/../"
API_URL="http://localhost:8000/api/v1"
LOG_FILE="/var/log/analyzer_integration.log"

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_message "🚀 Запуск автоматической интеграции"

# Переходим в директорию анализатора
cd "$ANALYZER_DIR" || {
    log_message "❌ Не удалось перейти в директорию $ANALYZER_DIR"
    exit 1
}

# Проверяем доступность API
if ! curl -s "$API_URL/health" > /dev/null; then
    log_message "❌ API недоступен по адресу $API_URL"
    exit 1
fi

log_message "✅ API доступен"

# Запускаем анализатор
log_message "🔍 Запуск анализатора..."
if python3 src/analyzer.py --enhanced > /tmp/analyzer_output.log 2>&1; then
    log_message "✅ Анализатор завершен успешно"
else
    log_message "❌ Ошибка выполнения анализатора"
    cat /tmp/analyzer_output.log >> "$LOG_FILE"
    exit 1
fi

# Ищем созданный отчет
REPORT_FILE=$(find . -name "*.html" -newer /tmp/last_integration 2>/dev/null | head -1)

if [ -n "$REPORT_FILE" ]; then
    log_message "📄 Найден отчет: $REPORT_FILE"
    
    # Загружаем отчет
    UPLOAD_RESULT=$(curl -s -X POST "$API_URL/reports/upload" -F "file=@$REPORT_FILE")
    
    if echo "$UPLOAD_RESULT" | jq -e '.id' > /dev/null 2>&1; then
        REPORT_ID=$(echo "$UPLOAD_RESULT" | jq -r '.id')
        STATUS=$(echo "$UPLOAD_RESULT" | jq -r '.deduplication_status')
        log_message "✅ Отчет загружен: $REPORT_ID (статус: $STATUS)"
        
        # Обновляем метку времени
        touch /tmp/last_integration
    else
        log_message "❌ Ошибка загрузки отчета"
        echo "$UPLOAD_RESULT" >> "$LOG_FILE"
        exit 1
    fi
else
    log_message "ℹ️ Новых отчетов не найдено"
fi

log_message "🎉 Интеграция завершена успешно"

# Добавить в crontab:
# */30 * * * * /path/to/cron_integration.sh
```

## Полезные утилиты

### Очистка старых отчетов

```python
#!/usr/bin/env python3
"""
Утилита для очистки старых отчетов
"""
import requests
from datetime import datetime, timedelta

def cleanup_old_reports(days_old=30, api_url="http://localhost:8000/api/v1"):
    """Удаляет отчеты старше указанного количества дней"""
    
    # Получаем список всех отчетов
    reports_response = requests.get(f"{api_url}/reports")
    if reports_response.status_code != 200:
        print("❌ Не удалось получить список отчетов")
        return
    
    reports = reports_response.json()["reports"]
    cutoff_date = datetime.now() - timedelta(days=days_old)
    
    old_reports = []
    for report in reports:
        report_date = datetime.fromisoformat(report["generated_at"].replace("Z", "+00:00"))
        if report_date < cutoff_date:
            old_reports.append(report)
    
    if not old_reports:
        print(f"✅ Отчетов старше {days_old} дней не найдено")
        return
    
    print(f"🗑️ Найдено {len(old_reports)} отчетов для удаления")
    
    deleted_count = 0
    for report in old_reports:
        print(f"Удаляем {report['filename']}...", end=" ")
        
        delete_response = requests.delete(f"{api_url}/reports/{report['id']}")
        if delete_response.status_code == 200:
            deleted_count += 1
            print("✅")
        else:
            print("❌")
    
    print(f"🎉 Удалено {deleted_count} из {len(old_reports)} отчетов")

if __name__ == "__main__":
    cleanup_old_reports(days_old=30)
```

### Экспорт данных

```python
#!/usr/bin/env python3
"""
Экспорт данных в различные форматы
"""
import requests
import csv
import json
from datetime import datetime

def export_reports_to_csv(filename="reports_export.csv", api_url="http://localhost:8000/api/v1"):
    """Экспортирует список отчетов в CSV"""
    
    response = requests.get(f"{api_url}/reports")
    if response.status_code != 200:
        print("❌ Ошибка получения данных")
        return
    
    reports = response.json()["reports"]
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['hostname', 'filename', 'os_name', 'generated_at', 
                     'total_connections', 'file_size', 'tcp_ports_count', 'udp_ports_count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for report in reports:
            writer.writerow({field: report.get(field, '') for field in fieldnames})
    
    print(f"📊 Данные экспортированы в {filename}")

if __name__ == "__main__":
    export_reports_to_csv()
```

## Дополнительная информация

- **[API документация](./README.md)** - полное описание API
- **[Руководство по развертыванию](../deployment/README.md)** - установка системы
- **[Документация веб-интерфейса](../web-interface/README.md)** - руководство пользователя 