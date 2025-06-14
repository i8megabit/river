#!/usr/bin/env python3
"""
Миграция для добавления полей tcp_connections, udp_connections, icmp_connections
"""

import asyncio
import asyncpg
from core.config import get_settings

settings = get_settings()

async def apply_migration():
    """Применяет миграции к базе данных"""
    print("🔄 Применение миграций для полей соединений...")
    
    try:
        # Подключаемся к базе данных
        conn = await asyncpg.connect(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD,
            database=settings.DATABASE_NAME
        )
        
        print("✅ Подключение к базе данных установлено")
        
        # Проверяем, существуют ли новые поля
        check_columns_query = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'system_reports' 
        AND column_name IN ('tcp_connections', 'udp_connections', 'icmp_connections');
        """
        
        existing_columns = await conn.fetch(check_columns_query)
        existing_column_names = [row['column_name'] for row in existing_columns]
        
        print(f"🔍 Существующие поля: {existing_column_names}")
        
        # Добавляем недостающие поля
        migrations = []
        
        if 'tcp_connections' not in existing_column_names:
            migrations.append("ALTER TABLE system_reports ADD COLUMN tcp_connections INTEGER DEFAULT 0;")
            
        if 'udp_connections' not in existing_column_names:
            migrations.append("ALTER TABLE system_reports ADD COLUMN udp_connections INTEGER DEFAULT 0;")
            
        if 'icmp_connections' not in existing_column_names:
            migrations.append("ALTER TABLE system_reports ADD COLUMN icmp_connections INTEGER DEFAULT 0;")
        
        if migrations:
            print(f"📝 Применяем {len(migrations)} миграций...")
            
            for i, migration in enumerate(migrations, 1):
                print(f"🔄 Миграция {i}/{len(migrations)}: {migration}")
                await conn.execute(migration)
                print(f"✅ Миграция {i} применена")
        else:
            print("✅ Все поля уже существуют, миграции не требуются")
        
        # Обновляем существующие записи, если есть данные в raw_data
        print("🔄 Обновление существующих записей...")
        
        update_query = """
        UPDATE system_reports 
        SET 
            tcp_connections = COALESCE((raw_data->>'tcp_connections')::integer, 0),
            udp_connections = COALESCE((raw_data->>'udp_connections')::integer, 0),
            icmp_connections = COALESCE((raw_data->>'icmp_connections')::integer, 0)
        WHERE raw_data IS NOT NULL 
        AND (tcp_connections = 0 OR udp_connections = 0 OR icmp_connections = 0);
        """
        
        result = await conn.execute(update_query)
        print(f"✅ Обновлено записей: {result}")
        
        await conn.close()
        print("✅ Миграции успешно применены")
        
    except Exception as e:
        print(f"❌ Ошибка применения миграций: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(apply_migration()) 