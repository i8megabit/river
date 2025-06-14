#!/usr/bin/env python3
"""
Тестирование API фронтенда для проверки отображения портов
"""

import requests
import json

def test_reports_api():
    """Тестирует API отчетов"""
    print("🧪 ТЕСТИРОВАНИЕ API ОТЧЕТОВ")
    print("=" * 50)
    
    try:
        # Проверяем API отчетов
        response = requests.get("http://localhost:8000/api/v1/reports")
        
        if response.status_code == 200:
            data = response.json()
            reports = data.get("reports", [])
            
            print(f"✅ API доступен")
            print(f"📊 Найдено отчетов: {len(reports)}")
            
            for i, report in enumerate(reports, 1):
                print(f"\n📋 Отчет {i}:")
                print(f"   🖥️ Hostname: {report.get('hostname', 'N/A')}")
                print(f"   🔗 Соединения: {report.get('total_connections', 0)}")
                print(f"   🚪 TCP порты: {report.get('tcp_ports_count', 0)}")
                print(f"   🚪 UDP порты: {report.get('udp_ports_count', 0)}")
                print(f"   📊 Всего портов: {(report.get('tcp_ports_count', 0) or 0) + (report.get('udp_ports_count', 0) or 0)}")
                print(f"   📅 Дата: {report.get('generated_at', 'N/A')}")
                print(f"   💾 Размер файла: {report.get('file_size', 0)} байт")
                print(f"   🔑 ID: {report.get('id', 'N/A')}")
                
                # Проверяем, что поля портов не None и не пустые
                tcp_count = report.get('tcp_ports_count')
                udp_count = report.get('udp_ports_count')
                
                if tcp_count is None:
                    print(f"   ⚠️ tcp_ports_count is None")
                if udp_count is None:
                    print(f"   ⚠️ udp_ports_count is None")
                    
                if tcp_count == 0 and udp_count == 0:
                    print(f"   ⚠️ Оба счетчика портов равны 0")
        else:
            print(f"❌ API недоступен: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка тестирования API: {e}")

def test_frontend():
    """Тестирует фронтенд"""
    print("\n🌐 ТЕСТИРОВАНИЕ ФРОНТЕНДА")
    print("=" * 50)
    
    try:
        # Проверяем доступность фронтенда
        response = requests.get("http://localhost:3000")
        
        if response.status_code == 200:
            print(f"✅ Фронтенд доступен")
            
            # Проверяем JavaScript файл
            js_response = requests.get("http://localhost:3000/js/app.js")
            if js_response.status_code == 200:
                js_content = js_response.text
                
                # Проверяем наличие кода обработки портов
                if "tcp_ports_count" in js_content and "udp_ports_count" in js_content:
                    print(f"✅ JavaScript содержит код обработки портов")
                else:
                    print(f"❌ JavaScript не содержит код обработки портов")
                    
                # Проверяем формулу суммирования портов
                if "(report.tcp_ports_count || 0) + (report.udp_ports_count || 0)" in js_content:
                    print(f"✅ Формула суммирования портов найдена")
                else:
                    print(f"❌ Формула суммирования портов не найдена")
            else:
                print(f"❌ JavaScript файл недоступен: {js_response.status_code}")
        else:
            print(f"❌ Фронтенд недоступен: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка тестирования фронтенда: {e}")

if __name__ == "__main__":
    test_reports_api()
    test_frontend()
    
    print("\n" + "=" * 50)
    print("🎯 РЕКОМЕНДАЦИИ:")
    print("1. Откройте http://localhost:3000 в браузере")
    print("2. Откройте Developer Tools (F12)")
    print("3. Перейдите на вкладку Console")
    print("4. Обновите страницу (F5)")
    print("5. Найдите сообщения '📡 Данные от API:' и '🔍 Отладка портов в отчетах:'")
    print("6. Проверьте, что tcp_ports_count и udp_ports_count не равны 0")
    print("=" * 50) 