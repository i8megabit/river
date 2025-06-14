#!/usr/bin/env python3
"""
Модуль работы с базой данных PostgreSQL
"""

import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    create_async_engine, 
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from core.config import get_settings

logger = logging.getLogger(__name__)

# Глобальные переменные для движка и сессии
async_engine: Optional[AsyncEngine] = None
async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


class Base(DeclarativeBase):
    """Базовый класс для всех моделей SQLAlchemy"""
    pass


async def create_database_engine() -> AsyncEngine:
    """
    Создает асинхронный движок базы данных
    """
    settings = get_settings()
    
    # Создаем асинхронный движок
    engine = create_async_engine(
        settings.database_url,
        echo=settings.DEBUG,
        future=True,
        # Настройки пула соединений для asyncio
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_POOL_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=True,
    )
    
    return engine


async def init_db() -> None:
    """
    Инициализация базы данных
    """
    global async_engine, async_session_factory
    
    try:
        # Создаем движок
        async_engine = await create_database_engine()
        
        # Создаем фабрику сессий
        async_session_factory = async_sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )
        
        # Проверяем соединение
        async with async_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        
        # Создаем таблицы
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ База данных PostgreSQL инициализирована")
        print("✅ Таблицы созданы/проверены")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        raise


async def close_db() -> None:
    """
    Закрытие соединения с базой данных
    """
    global async_engine
    
    if async_engine:
        await async_engine.dispose()
        print("✅ Соединение с БД закрыто")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Получение сессии базы данных для dependency injection
    """
    if not async_session_factory:
        raise RuntimeError("База данных не инициализирована")
    
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_health() -> bool:
    """
    Проверка здоровья базы данных
    """
    try:
        if not async_engine:
            return False
        
        async with async_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        
        return True
    except Exception as e:
        print(f"❌ Проблема с БД: {e}")
        return False


@asynccontextmanager
async def get_db_transaction():
    """
    Контекстный менеджер для транзакций
    """
    if not async_session_factory:
        raise RuntimeError("База данных не инициализирована")
    
    async with async_session_factory() as session:
        async with session.begin():
            try:
                yield session
            except Exception:
                await session.rollback()
                raise


async def get_db_info() -> dict:
    """
    Получает информацию о базе данных
    """
    try:
        if not async_engine:
            return {"status": "not_initialized"}
        
        async with async_engine.begin() as conn:
            # Версия PostgreSQL
            version_result = await conn.execute(text("SELECT version()"))
            version = version_result.fetchone()[0]
            
            # Размер базы данных
            size_result = await conn.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
            database_size = size_result.fetchone()[0]
            
            # Количество активных соединений
            connections_result = await conn.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            )
            active_connections = connections_result.fetchone()[0]
            
            # Общее количество соединений
            total_connections_result = await conn.execute(
                text("SELECT count(*) FROM pg_stat_activity")
            )
            total_connections = total_connections_result.fetchone()[0]
            
            return {
                "status": "healthy",
                "version": version,
                "database_size": database_size,
                "active_connections": active_connections,
                "total_connections": total_connections,
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_POOL_MAX_OVERFLOW
            }
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации о БД: {e}")
        return {"status": "error", "error": str(e)}


async def execute_migration(migration_sql: str) -> bool:
    """
    Выполняет SQL миграцию
    """
    try:
        if not async_engine:
            raise RuntimeError("База данных не инициализирована")
        
        async with async_engine.begin() as conn:
            await conn.execute(text(migration_sql))
            await conn.commit()
        
        logger.info("✅ Миграция выполнена успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения миграции: {e}")
        return False


async def cleanup_old_data(days: int = 90) -> int:
    """
    Очищает старые данные (старше указанного количества дней)
    """
    try:
        if not async_session_factory:
            raise RuntimeError("База данных не инициализирована")
        
        from models.report import SystemReport
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted_count = 0
        
        async with async_session_factory() as session:
            # Удаляем старые отчеты (каскадно удалятся связанные данные)
            result = await session.execute(
                text("""
                    DELETE FROM system_reports 
                    WHERE created_at < :cutoff_date
                    RETURNING id
                """),
                {"cutoff_date": cutoff_date}
            )
            
            deleted_rows = result.fetchall()
            deleted_count = len(deleted_rows)
            
            await session.commit()
        
        logger.info(f"🧹 Очищено {deleted_count} старых отчетов (старше {days} дней)")
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ Ошибка очистки старых данных: {e}")
        return 0


async def get_table_stats() -> dict:
    """
    Получает статистику по таблицам
    """
    try:
        if not async_engine:
            return {}
        
        async with async_engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_tuples,
                    n_dead_tup as dead_tuples
                FROM pg_stat_user_tables 
                ORDER BY tablename
            """))
            
            stats = {}
            for row in result.fetchall():
                stats[row.tablename] = {
                    "schema": row.schemaname,
                    "inserts": row.inserts,
                    "updates": row.updates,
                    "deletes": row.deletes,
                    "live_tuples": row.live_tuples,
                    "dead_tuples": row.dead_tuples
                }
            
            return stats
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики таблиц: {e}")
        return {}


# Dependency для FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency для получения сессии БД
    """
    async for session in get_db_session():
        yield session


if __name__ == "__main__":
    """
    Тестирование подключения к базе данных
    """
    async def test_db():
        print("🧪 Тестирование подключения к БД...")
        
        # Инициализация
        await init_db()
        
        # Проверка здоровья
        health = await get_db_health()
        print(f"Здоровье БД: {'✅' if health else '❌'}")
        
        # Информация о БД
        info = await get_db_info()
        print(f"Информация о БД: {info}")
        
        # Статистика таблиц
        stats = await get_table_stats()
        print(f"Статистика таблиц: {len(stats)} таблиц")
        
        # Закрытие
        await close_db()
        print("✅ Тест завершен")
    
    asyncio.run(test_db()) 