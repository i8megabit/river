#!/usr/bin/env python3
"""
Сервис дедупликации отчетов
Предотвращает дублирование отчетов на основе хеш-id
"""

import hashlib
import os
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import logging

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ReportDeduplicator:
    """Класс для дедупликации отчетов на основе хеш-id"""
    
    def __init__(self):
        pass
    
    def generate_report_hash(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Генерирует уникальный хеш для отчета на основе:
        1. Hostname системы
        2. Основной информации о системе (ОС)
        3. Контрольной суммы ключевых данных отчета
        
        Args:
            file_path: Путь к HTML файлу отчета
            metadata: Предварительно извлеченные метаданные (опционально)
            
        Returns:
            Строка с хешем отчета
        """
        try:
            if metadata is None:
                # Извлекаем метаданные из файла
                metadata = self._extract_key_metadata(file_path)
            
            # Создаем строку для хеширования из ключевых параметров
            hash_components = [
                metadata.get('hostname', 'unknown'),
                metadata.get('os_name', ''),
                metadata.get('os_version', ''),
                # Добавляем нормализованную версию данных для стабильности хеша
                str(metadata.get('total_connections', 0)),
                str(metadata.get('tcp_ports_count', 0)),
                str(metadata.get('udp_ports_count', 0)),
            ]
            
            # Объединяем компоненты
            hash_string = '|'.join(str(component).strip() for component in hash_components)
            
            # Создаем SHA-256 хеш
            hash_object = hashlib.sha256(hash_string.encode('utf-8'))
            content_hash = hash_object.hexdigest()
            
            # Возвращаем первые 16 символов для краткости
            report_hash = content_hash[:16]
            
            logger.debug(f"🔗 Сгенерирован хеш отчета: {report_hash} для {metadata.get('hostname', 'unknown')}")
            logger.debug(f"🔗 Хеш компоненты: {hash_string}")
            
            return report_hash
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации хеша отчета: {e}")
            # В случае ошибки возвращаем хеш имени файла
            return hashlib.md5(os.path.basename(file_path).encode()).hexdigest()[:16]
    
    def generate_content_hash(self, file_path: str) -> str:
        """
        Генерирует хеш содержимого файла
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            SHA-256 хеш содержимого файла
        """
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.error(f"❌ Ошибка генерации хеша содержимого: {e}")
            return ""
    
    def _extract_key_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Извлекает ключевые метаданные из HTML файла для генерации хеша
        Использует быстрый метод без полного парсинга
        
        Args:
            file_path: Путь к HTML файлу
            
        Returns:
            Словарь с ключевыми метаданными
        """
        metadata = {
            'hostname': 'unknown',
            'os_name': '',
            'os_version': '',
            'total_connections': 0,
            'tcp_ports_count': 0,
            'udp_ports_count': 0
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Извлекаем hostname из title
            title = soup.find('title')
            if title:
                title_text = title.text
                if 'отчет анализатора -' in title_text.lower():
                    hostname_part = title_text.split('-')[-1].strip()
                    if hostname_part:
                        metadata['hostname'] = hostname_part
            
            # Извлекаем информацию из header-info секции
            header_info_items = soup.find_all(class_='header-info-item')
            for item in header_info_items:
                text = item.text.strip()
                if '💻 ОС:' in text:
                    os_info = text.replace('💻 ОС:', '').strip()
                    parts = os_info.split(' ', 1)
                    metadata['os_name'] = parts[0]
                    if len(parts) > 1:
                        metadata['os_version'] = parts[1]
            
            # Извлекаем основную статистику из stat-number элементов
            stat_cards = soup.find_all(class_='stat-card')
            for card in stat_cards:
                stat_number = card.find(class_='stat-number')
                stat_label = card.find(class_='stat-label')
                
                if stat_number and stat_label:
                    number = self._extract_number(stat_number.text)
                    label = stat_label.text.strip().lower()
                    
                    if 'соединений' in label and 'всего' in label:
                        metadata['total_connections'] = number
                    elif 'tcp портов' in label:
                        metadata['tcp_ports_count'] = number
                    elif 'udp портов' in label:
                        metadata['udp_ports_count'] = number
            
            logger.debug(f"🔍 Извлечены метаданные: {metadata}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения метаданных: {e}")
        
        return metadata
    
    def _extract_number(self, text: str) -> int:
        """Извлекает число из текста"""
        try:
            import re
            clean_text = re.sub(r'[^\d]', '', text)
            return int(clean_text) if clean_text else 0
        except (ValueError, TypeError):
            return 0
    
    def find_duplicate_reports_by_hash(self, target_hash: str, uploads_dir: str) -> list:
        """
        Находит отчеты с таким же хешем в папке uploads
        
        Args:
            target_hash: Искомый хеш
            uploads_dir: Папка с загруженными отчетами
            
        Returns:
            Список путей к файлам с таким же хешем
        """
        duplicates = []
        
        try:
            if not os.path.exists(uploads_dir):
                return duplicates
            
            for filename in os.listdir(uploads_dir):
                if filename.endswith('.html'):
                    file_path = os.path.join(uploads_dir, filename)
                    
                    try:
                        file_hash = self.generate_report_hash(file_path)
                        if file_hash == target_hash:
                            duplicates.append(file_path)
                            logger.debug(f"🔍 Найден дубликат: {filename} (хеш: {file_hash})")
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка проверки файла {filename}: {e}")
                        continue
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска дубликатов: {e}")
        
        return duplicates
    
    def create_filename_from_hash(self, report_hash: str, original_filename: str) -> str:
        """
        Создает имя файла на основе хеша отчета
        
        Args:
            report_hash: Хеш отчета
            original_filename: Оригинальное имя файла
            
        Returns:
            Новое имя файла
        """
        try:
            file_extension = os.path.splitext(original_filename)[1]
            return f"report_{report_hash}{file_extension}"
        except Exception as e:
            logger.error(f"❌ Ошибка создания имени файла: {e}")
            return original_filename


# Глобальный экземпляр дедупликатора
report_deduplicator = ReportDeduplicator()


def generate_report_hash(file_path: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Высокоуровневая функция для генерации хеша отчета
    
    Args:
        file_path: Путь к HTML файлу отчета
        metadata: Предварительно извлеченные метаданные (опционально)
        
    Returns:
        Строка с хешем отчета
    """
    return report_deduplicator.generate_report_hash(file_path, metadata)


def find_duplicate_reports(target_hash: str, uploads_dir: str) -> list:
    """
    Высокоуровневая функция для поиска дубликатов отчетов
    
    Args:
        target_hash: Искомый хеш
        uploads_dir: Папка с загруженными отчетами
        
    Returns:
        Список путей к файлам с таким же хешем
    """
    return report_deduplicator.find_duplicate_reports_by_hash(target_hash, uploads_dir)


def create_hash_based_filename(report_hash: str, original_filename: str) -> str:
    """
    Высокоуровневая функция для создания имени файла на основе хеша
    
    Args:
        report_hash: Хеш отчета
        original_filename: Оригинальное имя файла
        
    Returns:
        Новое имя файла
    """
    return report_deduplicator.create_filename_from_hash(report_hash, original_filename)


if __name__ == "__main__":
    """
    Тестирование дедупликатора отчетов
    """
    
    def test_deduplicator():
        print("🧪 Тестирование дедупликатора отчетов...")
        
        # Создаем тестовый HTML контент
        test_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Кумулятивный отчет анализатора - test-host</title>
        </head>
        <body>
            <div class="header-info">
                <div class="header-info-item">💻 ОС: macOS 14.5.0</div>
            </div>
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">15</div>
                    <div class="stat-label">Всего соединений</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">8</div>
                    <div class="stat-label">TCP портов</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">3</div>
                    <div class="stat-label">UDP портов</div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Сохраняем тестовый файл
        test_file = "test_report.html"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_html)
        
        try:
            # Генерируем хеш
            report_hash = generate_report_hash(test_file)
            print(f"✅ Сгенерирован хеш: {report_hash}")
            
            # Создаем имя файла на основе хеша
            new_filename = create_hash_based_filename(report_hash, test_file)
            print(f"✅ Новое имя файла: {new_filename}")
            
            # Проверяем повторную генерацию хеша
            report_hash2 = generate_report_hash(test_file)
            print(f"✅ Повторный хеш: {report_hash2}")
            print(f"✅ Хеши совпадают: {report_hash == report_hash2}")
            
        finally:
            # Удаляем тестовый файл
            if os.path.exists(test_file):
                os.remove(test_file)
    
    test_deduplicator() 