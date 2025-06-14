#!/usr/bin/env python3
import asyncio
from services.html_parser import parse_analyzer_html_file

async def test():
    try:
        result = await parse_analyzer_html_file('uploads/test-report-correct.html')
        print('✅ Парсинг завершен успешно!')
        
        # Проверяем структуру портов
        ports = result.get("ports", {})
        tcp_ports = ports.get("tcp", [])
        udp_ports = ports.get("udp", [])
        
        print(f'TCP портов: {len(tcp_ports)}')
        print(f'UDP портов: {len(udp_ports)}')
        
        # Отладка структуры данных
        print('\n🔍 Структура TCP портов:')
        for i, port in enumerate(tcp_ports):
            print(f'  {i}: {port} (тип: {type(port)})')
            if isinstance(port, dict):
                print(f'      ключи: {list(port.keys())}')
        
        print('\n🔍 Структура UDP портов:')
        for i, port in enumerate(udp_ports[:3]):  # Показываем только первые 3
            print(f'  {i}: {port} (тип: {type(port)})')
            if isinstance(port, dict):
                print(f'      ключи: {list(port.keys())}')
        
        # Проверяем полученную структуру
        print('\n📊 Полученные данные:')
        print(f'- Хост: {result.get("hostname", "не найден")}')
        print(f'- ОС: {result.get("os_name", "не найдена")}')
        print(f'- Всего соединений: {result.get("total_connections", 0)}')
        print(f'- TCP портов: {result.get("tcp_ports_count", 0)}')
        print(f'- UDP портов: {result.get("udp_ports_count", 0)}')
        
    except Exception as e:
        print(f'❌ Ошибка парсинга: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test()) 