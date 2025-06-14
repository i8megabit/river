#!/usr/bin/env python3
"""
Скрипт для полной очистки базы данных от всех отчетов
"""
import requests
import sys
import time

def clear_all_reports():
    """Очищает все отчеты из базы данных"""
    print("🗑️ ОЧИСТКА БАЗЫ ДАННЫХ ОТ ВСЕХ ОТЧЕТОВ")
    print("=" * 50)
    
    base_url = "http://localhost:8000/api/v1/reports"
    
    try:
        # Получаем список всех отчетов
        print("📋 Получение списка отчетов...")
        response = requests.get(f"{base_url}/")
        
        if response.status_code != 200:
            print(f"❌ Ошибка получения списка отчетов: {response.status_code}")
            return False
        
        data = response.json()
        reports = data.get("reports", [])
        total_reports = len(reports)
        
        if total_reports == 0:
            print("✅ База данных уже пуста")
            return True
        
        print(f"📊 Найдено {total_reports} отчетов для удаления")
        
        # Удаляем каждый отчет
        deleted_count = 0
        for i, report in enumerate(reports, 1):
            report_id = report["id"]
            filename = report["filename"]
            
            print(f"🗑️ Удаление {i}/{total_reports}: {filename} (ID: {report_id})")
            
            delete_response = requests.delete(f"{base_url}/{report_id}")
            
            if delete_response.status_code == 200:
                deleted_count += 1
                print(f"✅ Удален: {filename}")
            else:
                print(f"❌ Ошибка удаления {filename}: {delete_response.status_code}")
            
            # Небольшая пауза между удалениями
            time.sleep(0.1)
        
        print(f"\n📊 РЕЗУЛЬТАТ ОЧИСТКИ:")
        print(f"✅ Удалено: {deleted_count} из {total_reports} отчетов")
        
        # Проверяем финальное состояние
        print("\n🔍 Проверка финального состояния...")
        final_response = requests.get(f"{base_url}/")
        if final_response.status_code == 200:
            final_data = final_response.json()
            remaining_reports = len(final_data.get("reports", []))
            print(f"📋 Осталось отчетов: {remaining_reports}")
            
            if remaining_reports == 0:
                print("🎉 База данных полностью очищена!")
                return True
            else:
                print(f"⚠️ Остались неудаленные отчеты: {remaining_reports}")
                return False
        else:
            print(f"❌ Ошибка проверки финального состояния: {final_response.status_code}")
            return False
        
    except requests.exceptions.ConnectionError:
        print("❌ Не удалось подключиться к API. Убедитесь, что сервер запущен.")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

if __name__ == "__main__":
    print("🚀 ЗАПУСК ОЧИСТКИ БАЗЫ ДАННЫХ")
    print("=" * 50)
    
    # Проверяем доступность API
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API доступен")
        else:
            print(f"❌ API недоступен: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Не удалось подключиться к API: {e}")
        print("💡 Убедитесь, что Docker контейнеры запущены: docker-compose up -d")
        sys.exit(1)
    
    # Выполняем очистку
    success = clear_all_reports()
    
    if success:
        print("\n🎉 ОЧИСТКА ЗАВЕРШЕНА УСПЕШНО!")
    else:
        print("\n❌ ОЧИСТКА ЗАВЕРШЕНА С ОШИБКАМИ!")
        sys.exit(1) 