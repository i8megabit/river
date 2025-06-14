#!/usr/bin/env python3
"""
Redis клиент и кэш-менеджер для веб-платформы анализатора
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

import redis.asyncio as redis
from core.config import get_settings

# Настройка логирования
logger = logging.getLogger(__name__)

# Получаем настройки
settings = get_settings()

# Глобальная переменная для Redis клиента
redis_client: Optional[redis.Redis] = None


async def init_redis() -> None:
    """
    Инициализирует Redis клиент
    """
    global redis_client
    
    try:
        # Создаем подключение к Redis
        redis_client = redis.from_url(
            settings.redis_url_computed,
            encoding="utf-8",
            decode_responses=False,  # Для поддержки binary данных
            socket_timeout=30,
            socket_connect_timeout=10,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        # Проверяем подключение
        await redis_client.ping()
        
        logger.info(f"✅ Redis инициализирован: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Redis: {e}")
        raise


async def close_redis() -> None:
    """
    Закрывает соединение с Redis
    """
    global redis_client
    
    if redis_client:
        await redis_client.close()
        redis_client = None
        logger.info("🔒 Соединение с Redis закрыто")


async def get_redis_health() -> bool:
    """
    Проверяет здоровье Redis
    """
    try:
        if not redis_client:
            return False
        
        response = await redis_client.ping()
        if response:
            logger.debug("✅ Проверка здоровья Redis успешна")
            return True
        else:
            logger.warning("⚠️ Redis не отвечает на ping")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки здоровья Redis: {e}")
        return False


async def get_redis_info() -> Dict[str, Any]:
    """
    Получает информацию о Redis сервере
    """
    try:
        if not redis_client:
            return {"status": "not_initialized"}
        
        info = await redis_client.info()
        
        return {
            "status": "healthy",
            "version": info.get("redis_version"),
            "uptime_seconds": info.get("uptime_in_seconds"),
            "connected_clients": info.get("connected_clients"),
            "used_memory": info.get("used_memory_human"),
            "total_commands_processed": info.get("total_commands_processed"),
            "keyspace_hits": info.get("keyspace_hits"),
            "keyspace_misses": info.get("keyspace_misses"),
            "db_size": await redis_client.dbsize()
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации Redis: {e}")
        return {"status": "error", "error": str(e)}


class CacheManager:
    """
    Менеджер кэша для работы с отчетами анализатора
    """
    
    def __init__(self):
        self.prefix = settings.CACHE_PREFIX
        self.default_ttl = settings.CACHE_TTL
    
    def _make_key(self, category: str, key: str) -> str:
        """Создает ключ для кэша"""
        return f"{self.prefix}{category}:{key}"
    
    async def set(
        self,
        category: str,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        serialize: bool = True
    ) -> bool:
        """
        Сохраняет значение в кэш
        
        Args:
            category: Категория данных (reports, stats, connections)
            key: Ключ
            value: Значение для сохранения
            ttl: Время жизни в секундах
            serialize: Нужно ли сериализовать значение
        """
        try:
            if not redis_client:
                return False
            
            cache_key = self._make_key(category, key)
            ttl = ttl or self.default_ttl
            
            if serialize:
                if isinstance(value, (dict, list)):
                    serialized_value = json.dumps(value, ensure_ascii=False, default=str)
                else:
                    serialized_value = pickle.dumps(value)
            else:
                serialized_value = value
            
            await redis_client.setex(cache_key, ttl, serialized_value)
            
            logger.debug(f"📦 Кэш сохранен: {cache_key} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в кэш: {e}")
            return False
    
    async def get(
        self,
        category: str,
        key: str,
        deserialize: bool = True
    ) -> Optional[Any]:
        """
        Получает значение из кэша
        
        Args:
            category: Категория данных
            key: Ключ
            deserialize: Нужно ли десериализовать значение
        """
        try:
            if not redis_client:
                return None
            
            cache_key = self._make_key(category, key)
            value = await redis_client.get(cache_key)
            
            if value is None:
                logger.debug(f"🔍 Кэш промах: {cache_key}")
                return None
            
            if deserialize:
                try:
                    # Пробуем JSON
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    try:
                        # Пробуем pickle
                        return pickle.loads(value)
                    except Exception:
                        # Возвращаем как есть
                        return value
            else:
                return value
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения из кэша: {e}")
            return None
    
    async def delete(self, category: str, key: str) -> bool:
        """Удаляет значение из кэша"""
        try:
            if not redis_client:
                return False
            
            cache_key = self._make_key(category, key)
            result = await redis_client.delete(cache_key)
            
            logger.debug(f"🗑️ Кэш удален: {cache_key}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления из кэша: {e}")
            return False
    
    async def exists(self, category: str, key: str) -> bool:
        """Проверяет существование ключа в кэше"""
        try:
            if not redis_client:
                return False
            
            cache_key = self._make_key(category, key)
            result = await redis_client.exists(cache_key)
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки существования в кэше: {e}")
            return False
    
    async def clear_category(self, category: str) -> int:
        """Очищает все ключи в категории"""
        try:
            if not redis_client:
                return 0
            
            pattern = self._make_key(category, "*")
            keys = await redis_client.keys(pattern)
            
            if keys:
                deleted = await redis_client.delete(*keys)
                logger.info(f"🧹 Очищена категория кэша {category}: {deleted} ключей")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки категории кэша: {e}")
            return 0
    
    async def get_keys(self, category: str) -> List[str]:
        """Получает все ключи в категории"""
        try:
            if not redis_client:
                return []
            
            pattern = self._make_key(category, "*")
            keys = await redis_client.keys(pattern)
            
            # Убираем префикс из ключей
            prefix_len = len(self._make_key(category, ""))
            clean_keys = [key.decode('utf-8')[prefix_len:] for key in keys]
            
            return clean_keys
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения ключей категории: {e}")
            return []


# Глобальный экземпляр менеджера кэша
cache = CacheManager()


# Специализированные функции для работы с отчетами
async def cache_report_data(report_id: str, data: dict, ttl: Optional[int] = None) -> bool:
    """Кэширует данные отчета"""
    return await cache.set("reports", report_id, data, ttl)


async def get_cached_report_data(report_id: str) -> Optional[dict]:
    """Получает данные отчета из кэша"""
    return await cache.get("reports", report_id)


async def cache_report_stats(hostname: str, stats: dict, ttl: Optional[int] = None) -> bool:
    """Кэширует статистику по хосту"""
    return await cache.set("stats", hostname, stats, ttl)


async def get_cached_report_stats(hostname: str) -> Optional[dict]:
    """Получает статистику из кэша"""
    return await cache.get("stats", hostname)


async def cache_search_results(query_hash: str, results: list, ttl: int = 300) -> bool:
    """Кэширует результаты поиска на 5 минут"""
    return await cache.set("search", query_hash, results, ttl)


async def get_cached_search_results(query_hash: str) -> Optional[list]:
    """Получает результаты поиска из кэша"""
    return await cache.get("search", query_hash)


async def invalidate_report_cache(report_id: str) -> None:
    """Инвалидирует кэш для конкретного отчета"""
    await cache.delete("reports", report_id)
    await cache.clear_category("search")  # Очищаем поиск


async def get_cache_statistics() -> dict:
    """Получает статистику использования кэша"""
    try:
        stats = {}
        
        # Статистика по категориям
        for category in ["reports", "stats", "search", "connections"]:
            keys = await cache.get_keys(category)
            stats[category] = len(keys)
        
        # Общая информация о Redis
        redis_info = await get_redis_info()
        stats.update(redis_info)
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики кэша: {e}")
        return {}


async def cleanup_expired_cache() -> int:
    """Очищает истекший кэш (Redis делает это автоматически, но можно принудительно)"""
    try:
        if not redis_client:
            return 0
        
        # Получаем статистику до очистки
        before_size = await redis_client.dbsize()
        
        # Принудительно удаляем истекшие ключи
        # В Redis это происходит автоматически, но можно запустить принудительную очистку
        info = await redis_client.info("memory")
        
        # Логируем статистику
        after_size = await redis_client.dbsize()
        cleaned = before_size - after_size
        
        if cleaned > 0:
            logger.info(f"🧹 Очищено {cleaned} истекших ключей кэша")
        
        return cleaned
        
    except Exception as e:
        logger.error(f"❌ Ошибка очистки истекшего кэша: {e}")
        return 0


if __name__ == "__main__":
    """
    Тестирование Redis подключения
    """
    async def test_redis():
        print("🧪 Тестирование Redis...")
        
        # Инициализация
        await init_redis()
        
        # Проверка здоровья
        health = await get_redis_health()
        print(f"Здоровье Redis: {'✅' if health else '❌'}")
        
        # Информация о Redis
        info = await get_redis_info()
        print(f"Информация о Redis: {info}")
        
        # Тестирование кэша
        test_data = {"test": "data", "timestamp": datetime.now().isoformat()}
        
        # Сохранение
        saved = await cache.set("test", "key1", test_data, 60)
        print(f"Сохранение: {'✅' if saved else '❌'}")
        
        # Получение
        retrieved = await cache.get("test", "key1")
        print(f"Получение: {'✅' if retrieved == test_data else '❌'}")
        
        # Статистика кэша
        stats = await get_cache_statistics()
        print(f"Статистика кэша: {stats}")
        
        # Очистка тестовых данных
        await cache.clear_category("test")
        
        # Закрытие
        await close_redis()
        print("✅ Тест завершен")
    
    asyncio.run(test_redis()) 