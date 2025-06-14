#!/usr/bin/env python3
"""
Конфигурация приложения с поддержкой переменных окружения
"""

import os
from functools import lru_cache
from typing import List, Optional, Any, Dict
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import SecretStr


class Settings(BaseSettings):
    """
    Настройки приложения с автоматической загрузкой из переменных окружения
    """
    
    # Основные настройки приложения
    APP_NAME: str = "Analyzer Platform"
    APP_VERSION: str = "v0.0.1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API настройки
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: SecretStr = SecretStr("your-super-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 дней
    
    # Настройки сервера
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    
    # База данных PostgreSQL
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "analyzer_user"
    POSTGRES_PASSWORD: SecretStr = SecretStr("analyzer_password")
    POSTGRES_DB: str = "analyzer_db"
    
    # Настройки пула соединений
    DB_POOL_SIZE: int = 20
    DB_POOL_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    
    # Redis настройки
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[SecretStr] = None
    REDIS_DB: int = 0
    REDIS_URL: Optional[str] = None
    
    # Настройки кэширования
    CACHE_TTL: int = 3600  # 1 час
    CACHE_PREFIX: str = "analyzer:"
    
    # Файловые настройки
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    
    # Настройки логирования
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/analyzer-platform.log"
    LOG_RETENTION_DAYS: int = 30
    LOG_MAX_SIZE: str = "10MB"
    
    # Настройки мониторинга
    ENABLE_METRICS: bool = True
    METRICS_PATH: str = "/metrics"
    
    # Настройки интеграции с анализатором
    ANALYZER_REPORTS_DIR: str = "reports"
    AUTO_IMPORT_REPORTS: bool = True
    REPORT_CLEANUP_DAYS: int = 90
    
    @property
    def database_url(self) -> str:
        """Формирует URL для подключения к базе данных"""
        password = self.POSTGRES_PASSWORD.get_secret_value()
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{password}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def redis_url_computed(self) -> str:
        """Формирует URL для подключения к Redis"""
        if self.REDIS_URL:
            return self.REDIS_URL
        
        auth_part = ""
        if self.REDIS_PASSWORD:
            password = self.REDIS_PASSWORD.get_secret_value()
            auth_part = f":{password}@"
        
        return f"redis://{auth_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def is_production(self) -> bool:
        """Проверяет, является ли окружение продакшеном"""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        """Проверяет, является ли окружение разработкой"""
        return self.ENVIRONMENT == "development"
    
    class Config:
        """Конфигурация Pydantic Settings"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Получает настройки приложения (с кэшированием)
    
    Returns:
        Settings: Объект настроек
    """
    return Settings()


def create_directories():
    """Создает необходимые директории"""
    settings = get_settings()
    
    # Создаем директории если их нет
    directories = [
        settings.UPLOAD_DIR,
        Path(settings.LOG_FILE).parent,
        settings.ANALYZER_REPORTS_DIR
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    """
    Тестирование конфигурации
    """
    settings = get_settings()
    print("🔧 Конфигурация веб-платформы:")
    print(f"   Приложение: {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"   Окружение: {settings.ENVIRONMENT}")
    print(f"   База данных: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    print(f"   Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    print(f"   Сервер: {settings.SERVER_HOST}:{settings.SERVER_PORT}")
    print(f"   Логи: {settings.LOG_FILE}")
    
    # Создаем директории
    create_directories() 