#!/usr/bin/env python3
"""
Скрипт для создания таблиц в базе данных
"""
import asyncio
import sys
import os

# Добавляем backend в путь
sys.path.insert(0, '/app')

async def create_tables():
    try:
        # Импортируем модели
        from models.report import SystemReport, NetworkConnection, NetworkPort, RemoteHost, ChangeHistory, NetworkInterface, ReportFile
        from core.database import create_database_engine, Base
        
        print("🔧 Создаем движок базы данных...")
        engine = await create_database_engine()
        
        print("🔧 Создаем таблицы...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ Таблицы созданы успешно!")
        print(f"📋 Созданные таблицы: {list(Base.metadata.tables.keys())}")
        
        await engine.dispose()
        
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(create_tables()) 