"""
Главный роутер API v1
"""

import os
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, status
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from services.html_parser import parse_analyzer_html_file
from models.report import Melt, NetworkConnection, NetworkPort, RemoteHost
from pydantic import BaseModel
from services.report_deduplication import generate_report_hash, find_duplicate_reports, create_hash_based_filename
from sqlalchemy import select, desc, or_, func
import json
from sqlalchemy.orm import selectinload

# Создаем главный роутер
api_router = APIRouter()

# Pydantic модели для ответов
class MeltSummary(BaseModel):
    id: str
    hostname: str
    filename: str
    generated_at: str
    os_name: Optional[str]
    total_connections: int
    file_size: int
    report_hash: Optional[str] = None  # Добавляем поле для хеша отчета
    tcp_ports_count: int = 0  # Убираем Optional, всегда число
    udp_ports_count: int = 0  # Убираем Optional, всегда число
    file_exists: Optional[bool] = True
    processing_status: Optional[str] = "processed"
    
class MeltsList(BaseModel):
    melts: List[MeltSummary]
    total: int

def serialize_datetime_for_json(obj):
    """Сериализует datetime объекты для JSON"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_datetime_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime_for_json(item) for item in obj]
    else:
        return obj

def _format_os_name(os_name: str, os_version: str) -> str:
    """
    Форматирует информацию об операционной системе
    
    Args:
        os_name: Название ОС
        os_version: Версия ОС
        
    Returns:
        Отформатированная строка с информацией об ОС
    """
    # Если нет информации об ОС
    if not os_name or os_name.lower() in ['unknown', 'none', 'null', '']:
        return "Неизвестная ОС"
    
    # Если есть только название ОС
    if not os_version or os_version.lower() in ['unknown', 'none', 'null', '']:
        return os_name
    
    # Если есть и название, и версия
    return f"{os_name} {os_version}".strip()

@api_router.get("/")
async def root():
    """Корневой endpoint API"""
    return {"message": "Анализатор API v1", "version": "v0.0.1"}

@api_router.get("/reports", response_model=MeltsList)
async def get_melts(db: AsyncSession = Depends(get_db)):
    """Получение списка всех отчетов из базы данных"""
    print(f"🔍 [DEBUG] Начинаем получение отчетов из БД...")
    
    try:
        # Получаем все отчеты из базы данных, сортируем по дате создания
        print(f"🔍 [DEBUG] Выполняем запрос к БД...")
        stmt = select(Melt).order_by(desc(Melt.generated_at))
        result = await db.execute(stmt)
        melts = result.scalars().all()
        
        print(f"🔍 [DEBUG] Получено {len(melts)} отчетов из БД")
        
        # Формируем список отчетов для ответа
        melts_list = []
        
        for i, melt in enumerate(melts):
            print(f"🔍 [DEBUG] Обрабатываем отчёт {i+1}/{len(melts)}: {melt.hostname}")
            print(f"🔍 [DEBUG] - ID: {melt.id}")
            print(f"🔍 [DEBUG] - TCP порты: {melt.tcp_ports_count}")
            print(f"🔍 [DEBUG] - UDP порты: {melt.udp_ports_count}")
            print(f"🔍 [DEBUG] - Соединения: {melt.total_connections}")
            print(f"🔍 [DEBUG] - HTML файл: {melt.html_file_path}")
            
            # Проверяем существование файла
            file_exists = bool(melt.html_file_path and os.path.exists(melt.html_file_path))
            print(f"🔍 [DEBUG] - Файл существует: {file_exists}")
            
            melt_summary = MeltSummary(
                id=str(melt.id),
                hostname=melt.hostname,
                filename=os.path.basename(melt.html_file_path) if melt.html_file_path else "unknown.html",
                generated_at=melt.generated_at.isoformat() if melt.generated_at else "",
                os_name=melt.os_name or "Неизвестная ОС",
                total_connections=melt.total_connections or 0,
                file_size=melt.file_size or 0,
                report_hash=melt.report_hash,
                tcp_ports_count=int(melt.tcp_ports_count or 0),  # Принудительно int
                udp_ports_count=int(melt.udp_ports_count or 0),  # Принудительно int
                file_exists=file_exists,
                processing_status=melt.processing_status or 'unknown'
            )
            
            melts_list.append(melt_summary)
            print(f"🔍 [DEBUG] ✅ Отчет {i+1} добавлен в список")
        
        print(f"📋 [SUCCESS] Возвращено {len(melts_list)} отчетов из базы данных")
        
        # Если БД пуста, переходим к fallback
        if len(melts_list) == 0:
            print(f"⚠️ [WARNING] База данных пуста, переходим к fallback парсингу файлов...")
            raise Exception("База данных пуста, нужен fallback")
        
        return MeltsList(
            melts=melts_list,
            total=len(melts_list)
        )
        
    except Exception as e:
        print(f"❌ [ERROR] Ошибка получения списка отчетов из БД: {e}")
        print(f"🔍 [DEBUG] Тип ошибки: {type(e)}")
        print(f"🔄 [FALLBACK] Переходим к получению отчетов из файловой системы...")
        
        # Fallback: получаем отчеты из файловой системы
        try:
            from services.html_parser import parse_analyzer_html_file
            
            uploads_dir = "uploads"
            melts_list = []
            
            print(f"🔍 [FALLBACK] Проверяем папку {uploads_dir}...")
            
            if os.path.exists(uploads_dir):
                html_files = [f for f in os.listdir(uploads_dir) if f.endswith('.html')]
                print(f"🔍 [FALLBACK] Найдено HTML файлов: {len(html_files)}")
                
                for i, filename in enumerate(html_files[:50]):  # Ограничиваем количество
                    file_path = os.path.join(uploads_dir, filename)
                    
                    print(f"🔍 [FALLBACK] Обрабатываем файл {i+1}/{min(len(html_files), 50)}: {filename}")
                    
                    try:
                        # Получаем размер файла
                        file_size = os.path.getsize(file_path)
                        
                        print(f"🔍 [FALLBACK] Начинаем парсинг файла {filename}, размер: {file_size}")
                        
                        # Быстро парсим основную информацию
                        parsed_data = await parse_analyzer_html_file(file_path)
                        
                        print(f"🔍 [FALLBACK] Парсинг {filename}: найдено ключей {len(parsed_data.keys())}")
                        print(f"🔍 [FALLBACK] Ключи: {list(parsed_data.keys())}")
                        print(f"🔍 [FALLBACK] Тип ports: {type(parsed_data.get('ports', 'НЕТ'))}")
                        if parsed_data.get('ports'):
                            print(f"🔍 [FALLBACK] Количество портов: {len(parsed_data['ports'])}")
                        
                        # Вычисляем количество портов из парсеных данных
                        tcp_ports_count = 0
                        udp_ports_count = 0
                        
                        print(f"🔍 Парсинг портов из данных:")
                        print(f"   parsed_data.keys(): {list(parsed_data.keys())}")
                        
                        # Пробуем разные способы получения портов
                        if parsed_data.get("ports"):
                            ports_data = parsed_data["ports"]
                            print(f"🔍 [DEBUG] Файл {filename}: ports_data type={type(ports_data)}, content={ports_data}")
                            
                            # Если ports - это словарь с tcp/udp ключами
                            if isinstance(ports_data, dict):
                                tcp_ports_list = ports_data.get("tcp", [])
                                udp_ports_list = ports_data.get("udp", [])
                                tcp_ports_count = len(tcp_ports_list)
                                udp_ports_count = len(udp_ports_list)
                                print(f"🔍 [DEBUG] TCP: {tcp_ports_count}, UDP: {udp_ports_count}, total_ports: {tcp_ports_count + udp_ports_count}")
                                if tcp_ports_list:
                                    print(f"🔍 [DEBUG] первый TCP порт: {tcp_ports_list[0]}")
                                if udp_ports_list:
                                    print(f"🔍 [DEBUG] первый UDP порт: {udp_ports_list[0]}")
                            
                            # Если ports - это плоский список (новый формат API)
                            elif isinstance(ports_data, list):
                                print(f"🔍 [DEBUG] список портов: {len(ports_data)} элементов")
                                for port in ports_data:
                                    if isinstance(port, dict):
                                        protocol = port.get('protocol', '').upper()
                                        if protocol == 'TCP':
                                            tcp_ports_count += 1
                                        elif protocol == 'UDP':
                                            udp_ports_count += 1
                                print(f"🔍 [DEBUG] подсчитанные порты: TCP={tcp_ports_count}, UDP={udp_ports_count}")
                        
                        # Если не нашли в "ports", ищем в других местах
                        if tcp_ports_count == 0 and udp_ports_count == 0:
                            # Ищем в tcp_ports_count и udp_ports_count напрямую
                            tcp_ports_count = parsed_data.get("tcp_ports_count", 0)
                            udp_ports_count = parsed_data.get("udp_ports_count", 0)
                            print(f"🔍 [DEBUG] fallback к прямым полям: TCP={tcp_ports_count}, UDP={udp_ports_count}")
                        
                        print(f"🚪 Итоговые порты: TCP={tcp_ports_count}, UDP={udp_ports_count}")
                        
                        # Используем дату из парсеных данных или время модификации файла
                        generated_at = None
                        if parsed_data.get("generated_at"):
                            try:
                                generated_at = datetime.fromisoformat(parsed_data["generated_at"].replace('Z', '+00:00')).isoformat()
                            except Exception:
                                pass
                        
                        if not generated_at and parsed_data.get("last_update"):
                            try:
                                if isinstance(parsed_data["last_update"], datetime):
                                    generated_at = parsed_data["last_update"].isoformat()
                                else:
                                    generated_at = parsed_data["last_update"]
                            except Exception:
                                pass
                        
                        # Если не получилось из метаданных, используем время модификации файла
                        if not generated_at:
                            generated_at = datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                        
                        # Форматируем ОС
                        os_name = parsed_data.get('os_name', '')
                        os_version = parsed_data.get('os_version', '')
                        formatted_os = f"{os_name} {os_version}".strip() if os_name and os_name.lower() not in ['unknown', 'none', 'null', ''] else "Неизвестная ОС"
                        
                        melt_summary = MeltSummary(
                            id=filename,  # Используем имя файла как ID
                            hostname=parsed_data.get("hostname", "unknown"),
                            filename=filename,
                            generated_at=generated_at,
                            os_name=formatted_os,
                            total_connections=int(parsed_data.get("total_connections", 0)),
                            file_size=file_size,
                            tcp_ports_count=int(tcp_ports_count),  # Принудительно int
                            udp_ports_count=int(udp_ports_count),  # Принудительно int
                            report_hash=parsed_data.get("report_hash"),
                            file_exists=True,
                            processing_status="processed"
                        )
                        
                        melts_list.append(melt_summary)
                        print(f"✅ [FALLBACK] Файл {filename} успешно обработан")
                        
                    except Exception as parse_error:
                        print(f"⚠️ [FALLBACK] Ошибка парсинга файла {filename}: {parse_error}")
                        print(f"⚠️ [FALLBACK] Тип ошибки: {type(parse_error)}")
                        import traceback
                        print(f"⚠️ [FALLBACK] Трейс: {traceback.format_exc()}")
                        continue
            else:
                print(f"❌ [FALLBACK] Папка {uploads_dir} не существует")
            
            print(f"📋 [FALLBACK] Возвращено {len(melts_list)} отчетов из файловой системы")
            
            return MeltsList(
                melts=melts_list,
                total=len(melts_list)
            )
            
        except Exception as fallback_error:
            print(f"❌ [FALLBACK] Ошибка fallback получения отчетов: {fallback_error}")
            import traceback
            print(f"❌ [FALLBACK] Трейс: {traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось получить список отчетов"
            )

@api_router.post("/reports/upload")
async def melt(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Загрузка нового отчета с дедупликацией на основе хеш-id из HTML метаданных"""
    
    # Проверяем тип файла
    if not file.filename.endswith('.html'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поддерживаются только HTML файлы отчетов"
        )
    
    try:
        # Импортируем необходимые модули
        from services.html_parser import parse_analyzer_html_file
        from models.report import Melt
        from sqlalchemy import select
        
        # Создаем папку uploads если её нет
        uploads_dir = "uploads"
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Сначала сохраняем файл во временное место для парсинга
        content = await file.read()
        temp_file_path = os.path.join(uploads_dir, f"temp_{uuid.uuid4()}.html")
        
        with open(temp_file_path, "wb") as f:
            f.write(content)
        
        # Парсим HTML отчет для получения метаданных включая хеш и ID
        try:
            parsed_data = await parse_analyzer_html_file(temp_file_path)
            hostname = parsed_data.get("hostname", "unknown")
            
            # Извлекаем хеш и ID отчета из HTML метаданных
            report_hash = parsed_data.get("report_hash")
            report_id = parsed_data.get("report_id")
            
            print(f"🔍 Новый отчет: hostname='{hostname}'")
            
            if report_hash:
                print(f"🔐 Хеш из HTML: {report_hash}")
            else:
                print("⚠️ Хеш отчета не найден в HTML метаданных")
                
            if report_id:
                print(f"🔑 ID из HTML: {report_id}")
            else:
                print("⚠️ ID отчета не найден в HTML метаданных")
                
        except Exception as parse_error:
            # Удаляем временный файл если парсинг не удался
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка парсинга HTML отчета: {str(parse_error)}"
            )
        
        # Если хеш не найден в HTML, генерируем его как fallback
        if not report_hash:
            try:
                from services.report_deduplication import generate_report_hash
                report_hash = generate_report_hash(temp_file_path, parsed_data)
                print(f"🔗 Сгенерирован fallback хеш: {report_hash}")
            except Exception as hash_error:
                # Удаляем временный файл при ошибке генерации хеша
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ошибка генерации хеша отчета: {str(hash_error)}"
                )
        
        # Проверяем наличие отчета с таким же хешем в базе данных
        existing_melt = None
        replaced_melt_info = None
        
        try:
            stmt = select(Melt).where(Melt.report_hash == report_hash)
            result = await db.execute(stmt)
            existing_melt = result.scalar_one_or_none()

            if existing_melt:
                print(f"🔍 Найден существующий отчёт с хешем {report_hash}: ID={existing_melt.id}")
                replaced_melt_info = {
                    'id': str(existing_melt.id),
                    'hostname': existing_melt.hostname,
                    'generated_at': existing_melt.generated_at.isoformat() if existing_melt.generated_at else None,
                    'file_path': existing_melt.html_file_path,
                    'report_hash': existing_melt.report_hash
                }
                
                # Удаляем старый файл отчета если он существует
                if existing_melt.html_file_path and os.path.exists(existing_melt.html_file_path):
                    try:
                        os.remove(existing_melt.html_file_path)
                        print(f"🗑️ Удалён старый файл отчёта: {existing_melt.html_file_path}")
                    except Exception as e:
                        print(f"⚠️ Ошибка удаления старого файла: {e}")
                
                # Удаляем запись из базы данных (каскадно удалятся связанные записи)
                await db.delete(existing_melt)
                await db.commit()
                print(f"🗑️ Удален существующий отчет из БД")
            
        except Exception as db_error:
            print(f"⚠️ Ошибка проверки дубликатов в БД: {db_error}")
            # Продолжаем выполнение, но без проверки дубликатов в БД
        
        # Дополнительно проверяем дубликаты в файловой системе по имени файла с хешем
        from services.report_deduplication import find_duplicate_reports, create_hash_based_filename
        
        file_duplicates = find_duplicate_reports(report_hash, uploads_dir)
        removed_files_count = 0
        
        for duplicate_path in file_duplicates:
            if duplicate_path != temp_file_path:  # Не удаляем временный файл
                try:
                    os.remove(duplicate_path)
                    removed_files_count += 1
                    print(f"🗑️ Удален дублирующий файл: {os.path.basename(duplicate_path)}")
                except Exception as e:
                    print(f"⚠️ Ошибка удаления файла {duplicate_path}: {e}")
        
        # Создаем имя файла на основе хеша
        hash_based_filename = create_hash_based_filename(report_hash, file.filename)
        final_file_path = os.path.join(uploads_dir, hash_based_filename)
        
        # Перемещаем временный файл в итоговое место
        os.rename(temp_file_path, final_file_path)
        
        # Сохраняем информацию об отчете в базе данных
        try:
            # Извлекаем дату генерации из метаданных HTML или из header_info
            report_generated_at = datetime.utcnow()  # По умолчанию
            
            # Пробуем получить дату из analyzer-generated-at метатега
            if parsed_data.get("generated_at"):
                try:
                    # Дата в формате ISO (2024-12-25T10:30:45.123456)
                    report_generated_at = datetime.fromisoformat(parsed_data["generated_at"].replace('Z', '+00:00'))
                except Exception as date_parse_error:
                    print(f"⚠️ Ошибка парсинга даты из метаданных: {date_parse_error}")
            
            # Если не получилось, пробуем из header_info
            if not parsed_data.get("generated_at") and parsed_data.get("last_update"):
                try:
                    report_generated_at = parsed_data["last_update"]
                except Exception:
                    pass
            
            # Если и это не сработало, пробуем из first_run
            if not parsed_data.get("generated_at") and not parsed_data.get("last_update") and parsed_data.get("first_run"):
                try:
                    report_generated_at = parsed_data["first_run"]
                except Exception:
                    pass
            
            print(f"📅 Дата отчета: {report_generated_at}")
            
            # Вычисляем количество портов из парсеных данных
            tcp_ports_count = 0
            udp_ports_count = 0
            
            print(f"🔍 Парсинг портов из данных:")
            print(f"   parsed_data.keys(): {list(parsed_data.keys())}")
            
            # Пробуем разные способы получения портов
            if parsed_data.get("ports"):
                ports_data = parsed_data["ports"]
                print(f"🔍 [DEBUG] Файл {file.filename}: ports_data type={type(ports_data)}, content={ports_data}")
                
                # Если ports - это словарь с tcp/udp ключами
                if isinstance(ports_data, dict):
                    tcp_ports_list = ports_data.get("tcp", [])
                    udp_ports_list = ports_data.get("udp", [])
                    tcp_ports_count = len(tcp_ports_list)
                    udp_ports_count = len(udp_ports_list)
                    print(f"🔍 [DEBUG] TCP: {tcp_ports_count}, UDP: {udp_ports_count}, total_ports: {tcp_ports_count + udp_ports_count}")
                    if tcp_ports_list:
                        print(f"🔍 [DEBUG] первый TCP порт: {tcp_ports_list[0]}")
                    if udp_ports_list:
                        print(f"🔍 [DEBUG] первый UDP порт: {udp_ports_list[0]}")
                
                # Если ports - это плоский список (новый формат API)
                elif isinstance(ports_data, list):
                    print(f"🔍 [DEBUG] список портов: {len(ports_data)} элементов")
                    for port in ports_data:
                        if isinstance(port, dict):
                            protocol = port.get('protocol', '').upper()
                            if protocol == 'TCP':
                                tcp_ports_count += 1
                            elif protocol == 'UDP':
                                udp_ports_count += 1
                    print(f"🔍 [DEBUG] подсчитанные порты: TCP={tcp_ports_count}, UDP={udp_ports_count}")
            
            # Если не нашли в "ports", ищем в других местах
            if tcp_ports_count == 0 and udp_ports_count == 0:
                # Ищем в tcp_ports_count и udp_ports_count напрямую
                tcp_ports_count = parsed_data.get("tcp_ports_count", 0)
                udp_ports_count = parsed_data.get("udp_ports_count", 0)
                print(f"🔍 [DEBUG] fallback к прямым полям: TCP={tcp_ports_count}, UDP={udp_ports_count}")
            
            print(f"🚪 Итоговые порты: TCP={tcp_ports_count}, UDP={udp_ports_count}")
            
            # Сериализуем parsed_data для JSON поля
            serialized_parsed_data = serialize_datetime_for_json(parsed_data)
            
            # Создаем новую запись Melt используя ID из HTML если есть
            new_melt = Melt(
                id=uuid.UUID(report_id) if report_id else None,  # Используем ID из HTML если есть
                report_hash=report_hash,
                hostname=hostname,
                report_title=f"Отчет анализатора - {hostname}",
                generated_at=report_generated_at,
                os_name=parsed_data.get("os_name", ""),
                os_version=parsed_data.get("os_version", ""),
                html_file_path=final_file_path,
                file_size=len(content),
                total_connections=parsed_data.get("total_connections", 0),
                incoming_connections=parsed_data.get("incoming_connections", 0),
                outgoing_connections=parsed_data.get("outgoing_connections", 0),
                # Соединения по протоколам (из stat-card элементов)
                tcp_connections=parsed_data.get("tcp_connections", 0),
                udp_connections=parsed_data.get("udp_connections", 0),
                icmp_connections=parsed_data.get("icmp_connections", 0),
                unique_processes=parsed_data.get("unique_processes", 0),
                unique_hosts=parsed_data.get("unique_hosts", 0),
                # Порты (отдельно от соединений)
                tcp_ports_count=tcp_ports_count,
                udp_ports_count=udp_ports_count,
                change_events_count=parsed_data.get("change_events_count", 0),
                raw_data=serialized_parsed_data,
                processing_status="processed"
            )
            
            db.add(new_melt)
            await db.flush()  # Получаем ID без коммита
            
            # Сохраняем связанные данные (соединения, порты) в той же транзакции
            melt_db_id = new_melt.id
            
            # Сохраняем соединения в БД
            connections_raw = parsed_data.get("connections", [])
            if connections_raw:
                print(f"🔗 Сохраняем {len(connections_raw)} соединений в БД...")
                for i, conn in enumerate(connections_raw[:100]):  # Ограничиваем до 100 соединений
                    try:
                        # Парсим first_seen и last_seen
                        first_seen = None
                        last_seen = None
                        
                        if conn.get('first_seen'):
                            try:
                                first_seen = datetime.fromisoformat(conn['first_seen'].replace('Z', '+00:00'))
                            except Exception:
                                pass
                        
                        if conn.get('last_seen'):
                            try:
                                last_seen = datetime.fromisoformat(conn['last_seen'].replace('Z', '+00:00'))
                            except Exception:
                                pass
                        
                        # Определяем тип соединения
                        connection_type = conn.get('connection_type', 'unknown')
                        if not connection_type or connection_type == 'unknown':
                            direction = conn.get('direction', '')
                            if '📥' in direction or 'входящее' in direction.lower():
                                connection_type = 'incoming'
                            elif '📤' in direction or 'исходящее' in direction.lower():
                                connection_type = 'outgoing'
                            else:
                                connection_type = 'unknown'
                        
                        db_connection = NetworkConnection(
                            report_id=melt_db_id,
                            connection_type=connection_type,
                            local_address=conn.get('local_address', '')[:100],  # Ограничиваем длину
                            remote_address=conn.get('remote_address', '')[:100],
                            remote_hostname=conn.get('remote_hostname', '')[:255],
                            process_name=conn.get('process_name', '')[:255],
                            protocol=conn.get('protocol', 'unknown')[:10],
                            first_seen=first_seen,
                            last_seen=last_seen,
                            packet_count=conn.get('packet_count', 0),
                            connection_status='active'
                        )
                        db.add(db_connection)
                        
                    except Exception as conn_error:
                        print(f"⚠️ Ошибка сохранения соединения {i}: {conn_error}")
                        continue
            
            # Сохраняем порты в БД
            ports_raw = parsed_data.get("ports", {})
            if ports_raw:
                print(f"🚪 Сохраняем порты в БД: TCP={len(ports_raw.get('tcp', []))}, UDP={len(ports_raw.get('udp', []))}")
                
                # TCP порты
                for port_info in ports_raw.get('tcp', [])[:50]:  # Ограничиваем до 50 портов
                    try:
                        port_number = port_info.get('port_number') if isinstance(port_info, dict) else port_info
                        if isinstance(port_number, int):
                            db_port = NetworkPort(
                                report_id=melt_db_id,
                                port_number=port_number,
                                protocol='tcp',
                                description=port_info.get('description', f'TCP порт {port_number}')[:500] if isinstance(port_info, dict) else f'TCP порт {port_number}',
                                service_name=port_info.get('service_name', '')[:100] if isinstance(port_info, dict) else '',
                                status='listening'
                            )
                            db.add(db_port)
                    except Exception as port_error:
                        print(f"⚠️ Ошибка сохранения TCP порта: {port_error}")
                        continue
                
                # UDP порты
                for port_info in ports_raw.get('udp', [])[:50]:  # Ограничиваем до 50 портов
                    try:
                        port_number = port_info.get('port_number') if isinstance(port_info, dict) else port_info
                        if isinstance(port_number, int):
                            db_port = NetworkPort(
                                report_id=melt_db_id,
                                port_number=port_number,
                                protocol='udp',
                                description=port_info.get('description', f'UDP порт {port_number}')[:500] if isinstance(port_info, dict) else f'UDP порт {port_number}',
                                service_name=port_info.get('service_name', '')[:100] if isinstance(port_info, dict) else '',
                                status='listening'
                            )
                            db.add(db_port)
                    except Exception as port_error:
                        print(f"⚠️ Ошибка сохранения UDP порта: {port_error}")
                        continue
            
            # Коммитим все данные вместе
            await db.commit()
            await db.refresh(new_melt)

            final_melt_id = str(new_melt.id)
            print(f"✅ Отчёт и связанные данные сохранены в БД с ID: {final_melt_id}")
            
        except Exception as db_save_error:
            print(f"⚠️ Ошибка сохранения в БД: {db_save_error}")
            # Если не удалось сохранить в БД, все равно возвращаем успех для файла
            final_melt_id = report_id if report_id else report_hash  # Используем ID из HTML или хеш
        
        # Формируем ответ
        response_data = {
            "message": f"Отчёт успешно загружен{' (заменён дубликат)' if existing_melt or removed_files_count > 0 else ''}",
            "report_id": final_melt_id,
            "report_hash": report_hash,
            "filename": file.filename,
            "saved_as": hash_based_filename,
            "file_size": len(content),
            "hostname": hostname,
            "connections_count": parsed_data.get("total_connections", 0),
            "is_replacement": bool(existing_melt or removed_files_count > 0),
            "deduplication_method": "html_metadata" if parsed_data.get("report_hash") else "generated_hash"
        }
        
        if existing_melt:
            response_data["replaced_melt"] = replaced_melt_info
            
        if removed_files_count > 0:
            response_data["removed_file_duplicates"] = removed_files_count
        
        # Если использовали метаданные из HTML, добавляем информацию
        if parsed_data.get("report_hash"):
            response_data["analyzer_metadata"] = {
                "report_id": report_id,
                "report_hash": report_hash,
                "analyzer_version": parsed_data.get("analyzer_version"),
                "hash_components": parsed_data.get("hash_components")
            }
        
        print(f"✅ Отчет загружен: {hash_based_filename}")
        
        return response_data
        
    except HTTPException:
        # Убираем временный файл при ошибке
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise
    except Exception as e:
        # Убираем временный файл при ошибке
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка загрузки отчета: {str(e)}"
        )

@api_router.get("/reports/{report_id}/simple")
async def get_report_details_simple(report_id: str):
    """Получение детальной информации об отчете (упрощенная версия)"""
    try:
        print(f"🔍 Getting simple report details for ID: {report_id}")
        
        # Ищем HTML файл
        uploads_dir = "uploads"
        file_path = None
        
        print(f"🔍 Ищем файл в папке: {uploads_dir}")
        print(f"🔍 Проверяем существование папки: {os.path.exists(uploads_dir)}")
        
        # Пробуем разные варианты имен файлов
        if os.path.exists(uploads_dir):
            available_files = os.listdir(uploads_dir)
            print(f"🔍 Доступные файлы: {available_files}")
            
            for filename in available_files:
                print(f"🔍 Проверяем файл: {filename}")
                # Разные варианты поиска
                if (filename.startswith(report_id[:8]) or 
                    filename.startswith(report_id) or
                    f"_{report_id[:8]}" in filename or
                    f"_{report_id}" in filename or
                    report_id[:8] in filename or
                    report_id in filename) and filename.endswith('.html'):
                    file_path = os.path.join(uploads_dir, filename)
                    print(f"✅ Найден подходящий файл: {filename}")
                    break
        else:
            print(f"❌ Папка {uploads_dir} не существует")
        
        if not file_path:
            print(f"❌ Файл для ID {report_id} не найден")
            return {"error": f"Report {report_id} not found"}
        
        print(f"✅ Found HTML file: {file_path}")
        
        # Извлекаем базовую информацию
        hostname = "unknown"
        os_name = "unknown"
        file_size = os.path.getsize(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(3000)
                import re
                
                # Ищем hostname
                hostname_match = re.search(r'<meta name="analyzer-hostname" content="([^"]+)"', content)
                if hostname_match:
                    hostname = hostname_match.group(1)
                else:
                    header_match = re.search(r'<strong>🖥️ Хост:</strong>\s*([^<]+)', content)
                    if header_match:
                        hostname = header_match.group(1).strip()
                
                # ОС
                os_match = re.search(r'<strong>💻 ОС:</strong>\s*([^<]+)', content)
                if os_match:
                    os_name = os_match.group(1).strip()
                
        except Exception as e:
            print(f"⚠️ Could not extract metadata: {e}")
        
        result = {
            "id": report_id,
            "hostname": hostname,
            "os": {"name": os_name, "version": ""},
            "file_size": file_size,
            "status": "found"
        }
        
        print(f"✅ Returning simple report details for: {hostname}")
        return result
        
    except Exception as e:
        print(f"❌ Error in simple report details: {e}")
        return {"error": str(e)}

@api_router.get("/reports/{report_id}")
async def get_report_details(report_id: str, db: AsyncSession = Depends(get_db)):
    """Получение детальной информации об отчете"""
    try:
        print(f"🔍 Getting report details for ID: {report_id}")
        
        # Импорты
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from models.report import Melt
        
        # Загружаем Melt с связанными данными
        db_melt = None
        
        # Сначала проверяем, является ли report_id валидным UUID
        try:
            import uuid
            uuid_obj = uuid.UUID(report_id)
            # Это валидный UUID - ищем в БД
            stmt = select(Melt).options(
                selectinload(Melt.connections),
                selectinload(Melt.ports),
                selectinload(Melt.remote_hosts),
                selectinload(Melt.network_interfaces)
            ).where(Melt.id == uuid_obj)
            
            result = await db.execute(stmt)
            db_melt = result.scalar_one_or_none()
            
            if db_melt:
                print(f"✅ Отчёт найден в БД по UUID: {report_id}")
            else:
                print(f"❌ Отчёт с UUID {report_id} не найден в БД")
                
        except ValueError:
            # Это не UUID - пропускаем поиск в БД
            print(f"🔍 {report_id} не является UUID, ищем как имя файла")
        
        if not db_melt:
            print(f"❌ Report not found in database: {report_id}")
            # Если не найден в БД, попробуем поискать файл напрямую
            uploads_dir = "uploads"
            file_path = None
            
            if os.path.exists(uploads_dir):
                # Если report_id выглядит как имя файла, ищем его точно
                if report_id.endswith('.html'):
                    potential_path = os.path.join(uploads_dir, report_id)
                    if os.path.exists(potential_path):
                        file_path = potential_path
                        print(f"✅ Найден файл по точному имени: {file_path}")
                
                # Если не нашли точного совпадения, ищем по префиксу
                if not file_path:
                    for filename in os.listdir(uploads_dir):
                        if (filename.startswith(report_id[:8]) or 
                            filename.startswith(report_id) or
                            report_id in filename) and filename.endswith('.html'):
                            file_path = os.path.join(uploads_dir, filename)
                            print(f"✅ Найден файл по префиксу: {file_path}")
                            break
            
            if not file_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Отчет с ID {report_id} не найден"
                )
        else:
            # Используем filename из БД
            uploads_dir = "uploads"
            if db_melt.html_file_path:
                file_path = db_melt.html_file_path
            else:
                # Пробуем построить путь из report_hash
                filename = f"report_{db_melt.report_hash}.html"
                file_path = os.path.join(uploads_dir, filename)
        
        if not os.path.exists(file_path):
            print(f"❌ HTML file not found: {file_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Файл отчета не найден: {file_path}"
            )
        
        print(f"✅ Found HTML file: {file_path}")
        
        # Используем данные из БД если есть, иначе парсим HTML
        if db_melt:
            hostname = db_melt.hostname
            os_name = db_melt.os_name or "unknown"
            os_version = db_melt.os_version or ""
            generated_at = db_melt.generated_at.isoformat() if db_melt.generated_at else datetime.now().isoformat()
            report_hash = db_melt.report_hash or ""
            file_size = db_melt.file_size or os.path.getsize(file_path)
            
            # Статистика из БД
            total_connections = db_melt.total_connections or 0
            tcp_connections = db_melt.tcp_connections or 0
            udp_connections = db_melt.udp_connections or 0
            icmp_connections = db_melt.icmp_connections or 0
            listening_ports = (db_melt.tcp_ports_count or 0) + (db_melt.udp_ports_count or 0)
            established_connections = (db_melt.incoming_connections or 0) + (db_melt.outgoing_connections or 0)
            total_ports = (db_melt.tcp_ports_count or 0) + (db_melt.udp_ports_count or 0)
            
            # Получаем связанные данные
            connections_data = []
            for conn in db_melt.connections[:50]:  # Первые 50 соединений
                connections_data.append({
                    "id": str(conn.id),
                    "type": conn.connection_type,
                    "local_address": conn.local_address,
                    "remote_address": conn.remote_address,
                    "remote_hostname": conn.remote_hostname,
                    "process": conn.process_name,
                    "protocol": conn.protocol,
                    "first_seen": conn.first_seen.isoformat() if conn.first_seen else None,
                    "last_seen": conn.last_seen.isoformat() if conn.last_seen else None,
                    "packet_count": conn.packet_count
                })
            
            ports_data = []
            for port in db_melt.ports[:100]:  # Первые 100 портов
                ports_data.append({
                    "id": str(port.id),
                    "port_number": port.port_number,
                    "protocol": port.protocol,
                    "description": port.description,
                    "service_name": port.service_name,
                    "process": port.process_name,
                    "status": port.status
                })
            
            # Если связанные данные пусты, пытаемся извлечь из raw_data
            if not connections_data and not ports_data and db_melt.raw_data:
                print("📊 Связанные таблицы пусты, извлекаем данные из raw_data...")
                raw_data = db_melt.raw_data
                
                # Извлекаем соединения из raw_data
                if raw_data.get("connections"):
                    print(f"🔗 Найдено {len(raw_data['connections'])} соединений в raw_data")
                    for i, conn in enumerate(raw_data["connections"][:50]):
                        connections_data.append({
                            "id": f"raw_{i}",
                            "type": conn.get('connection_type', 'unknown'),
                            "local_address": conn.get('local_address', ''),
                            "remote_address": conn.get('remote_address', ''),
                            "remote_hostname": conn.get('remote_hostname', ''),
                            "process": conn.get('process_name', ''),
                            "protocol": conn.get('protocol', 'unknown'),
                            "first_seen": conn.get('first_seen'),
                            "last_seen": conn.get('last_seen'),
                            "packet_count": conn.get('packet_count', 0)
                        })
                
                # Извлекаем порты из raw_data
                if raw_data.get("ports"):
                    ports_raw = raw_data["ports"]
                    
                    # TCP порты
                    tcp_ports = ports_raw.get("tcp", [])
                    print(f"🚪 Найдено {len(tcp_ports)} TCP портов в raw_data")
                    for i, port_info in enumerate(tcp_ports[:50]):
                        port_number = port_info.get('port_number') if isinstance(port_info, dict) else port_info
                        if isinstance(port_number, int):
                            ports_data.append({
                                "id": f"tcp_raw_{i}",
                                "port_number": port_number,
                                "protocol": "tcp",
                                "description": port_info.get('description', f'TCP порт {port_number}') if isinstance(port_info, dict) else f'TCP порт {port_number}',
                                "service_name": port_info.get('service_name', '') if isinstance(port_info, dict) else '',
                                "process": port_info.get('process_name', '') if isinstance(port_info, dict) else '',
                                "status": "listening"
                            })
                    
                    # UDP порты
                    udp_ports = ports_raw.get("udp", [])
                    print(f"🚪 Найдено {len(udp_ports)} UDP портов в raw_data")
                    for i, port_info in enumerate(udp_ports[:50]):
                        port_number = port_info.get('port_number') if isinstance(port_info, dict) else port_info
                        if isinstance(port_number, int):
                            ports_data.append({
                                "id": f"udp_raw_{i}",
                                "port_number": port_number,
                                "protocol": "udp",
                                "description": port_info.get('description', f'UDP порт {port_number}') if isinstance(port_info, dict) else f'UDP порт {port_number}',
                                "service_name": port_info.get('service_name', '') if isinstance(port_info, dict) else '',
                                "process": port_info.get('process_name', '') if isinstance(port_info, dict) else '',
                                "status": "listening"
                            })
                
                print(f"📊 Извлечено из raw_data: {len(connections_data)} соединений, {len(ports_data)} портов")
            
            remote_hosts_data = []
            for host in db_melt.remote_hosts[:50]:  # Первые 50 хостов
                remote_hosts_data.append({
                    "id": str(host.id),
                    "ip_address": host.ip_address,
                    "hostname": host.hostname,
                    "connection_count": host.connection_count,
                    "first_seen": host.first_seen.isoformat() if host.first_seen else None,
                    "last_seen": host.last_seen.isoformat() if host.last_seen else None,
                    "country": host.country,
                    "organization": host.organization
                })
            
            network_interfaces_data = []
            for interface in db_melt.network_interfaces[:20]:  # Первые 20 интерфейсов
                network_interfaces_data.append({
                    "id": str(interface.id),
                    "name": interface.interface_name,
                    "packets_in": interface.packets_in,
                    "packets_out": interface.packets_out,
                    "bytes_in": interface.bytes_in,
                    "bytes_out": interface.bytes_out,
                    "mtu": interface.mtu,
                    "status": interface.status
                })
                
        else:
            # Fallback: парсим метаданные из HTML
            hostname = "unknown"
            os_name = "unknown"
            os_version = ""
            generated_at = datetime.now().isoformat()
            report_hash = ""
            file_size = os.path.getsize(file_path)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read(5000)
                    import re
                    
                    # Ищем метаданные
                    hostname_match = re.search(r'<meta name="analyzer-hostname" content="([^"]+)"', content)
                    if hostname_match:
                        hostname = hostname_match.group(1)
                    
                    # ОС
                    os_match = re.search(r'<strong>💻 ОС:</strong>\s*([^<]+)', content)
                    if os_match:
                        os_full = os_match.group(1).strip()
                        parts = os_full.split(' ', 1)
                        os_name = parts[0]
                        os_version = parts[1] if len(parts) > 1 else ""
                    
                    # Хеш отчета
                    hash_match = re.search(r'<meta name="analyzer-report-hash" content="([^"]+)"', content)
                    if hash_match:
                        report_hash = hash_match.group(1)
                    
            except Exception as e:
                print(f"⚠️ Could not extract metadata from HTML: {e}")
            
            # Пустые данные для fallback
            connections_data = []
            ports_data = []
            remote_hosts_data = []
            network_interfaces_data = []
            total_connections = 0
            tcp_connections = 0
            udp_connections = 0
            icmp_connections = 0
            listening_ports = 0
            established_connections = 0
            total_ports = 0
        
        result = {
            "id": report_id,
            "hostname": hostname,
            "generated_at": generated_at,
            "os": {
                "name": os_name,
                "version": os_version
            },
            "connections": connections_data,
            "ports": ports_data,
            "remote_hosts": remote_hosts_data,
            "network_info": {
                "interfaces": network_interfaces_data,
                "bytes_sent": sum(i.get('bytes_out', 0) for i in network_interfaces_data),
                "bytes_received": sum(i.get('bytes_in', 0) for i in network_interfaces_data),
                "countries": list(set(h.get('country') for h in remote_hosts_data if h.get('country')))
            },
            # Статистика для фронтенда
            "total_connections": total_connections,
            "tcp_connections": tcp_connections,
            "udp_connections": udp_connections,
            "icmp_connections": icmp_connections,
            "listening_ports": listening_ports,
            "established_connections": established_connections,
            "total_ports": total_ports,
            # Информация о файле
            "file_size": file_size,
            "created_at": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
            "report_hash": report_hash
        }
        
        print(f"✅ Returning detailed report for: {hostname} ({len(connections_data)} connections, {len(ports_data)} ports)")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения отчета: {str(e)}"
        )

@api_router.get("/reports/{report_id}/download")
async def download_report(report_id: str, db: AsyncSession = Depends(get_db)):
    """Скачивание HTML файла отчета"""
    try:
        print(f"🔍 Download request for report ID: {report_id}")
        
        # Сначала ищем отчет в базе данных
        from sqlalchemy import select
        from models.report import Melt
        
        result = await db.execute(select(Melt).where(Melt.id == report_id))
        db_melt = result.scalar_one_or_none()
        
        file_path = None
        original_filename = None
        
        if db_melt:
            # Используем путь из базы данных
            if db_melt.html_file_path and os.path.exists(db_melt.html_file_path):
                file_path = db_melt.html_file_path
                original_filename = os.path.basename(file_path)
                print(f"✅ Файл найден через БД: {file_path}")
            else:
                # Пытаемся найти файл по хешу
                report_hash = db_melt.report_hash
                uploads_dir = "uploads"
                
                for filename in os.listdir(uploads_dir):
                    if filename.startswith(report_hash) and filename.endswith('.html'):
                        file_path = os.path.join(uploads_dir, filename)
                        original_filename = filename
                        print(f"✅ Файл найден по хешу: {file_path}")
                        break
        
        if not file_path:
            # Fallback: поиск файла напрямую в uploads
            uploads_dir = "uploads"
            
            file_found = False
            
            # Если report_id выглядит как имя файла, ищем его точно
            if report_id.endswith('.html'):
                file_path = os.path.join(uploads_dir, report_id)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        file_found = True
                        print(f"🗑️ Удален файл по точному имени: {report_id}")
                    except Exception as e:
                        print(f"⚠️ Ошибка удаления файла {report_id}: {e}")
            
            # Если не нашли точного совпадения, пробуем другие варианты
            if not file_found:
                possible_files = [
                    f"{report_id}.html",
                    f"report_{report_id}.html"
                ]
                
                for filename in possible_files:
                    file_path = os.path.join(uploads_dir, filename)
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            file_found = True
                            print(f"🗑️ Удален файл (без записи в БД): {filename}")
                            break
                        except Exception as e:
                            print(f"⚠️ Ошибка удаления файла {filename}: {e}")
            
            # Ищем по частичному совпадению имени файла
            if not file_found and os.path.exists(uploads_dir):
                for filename in os.listdir(uploads_dir):
                    if report_id in filename and filename.endswith('.html'):
                        file_path = os.path.join(uploads_dir, filename)
                        try:
                            os.remove(file_path)
                            file_found = True
                            print(f"🗑️ Удален файл (частичное совпадение): {filename}")
                            break
                        except Exception as e:
                            print(f"⚠️ Ошибка удаления файла {filename}: {e}")
        
        if not file_path:
            print(f"❌ Файл не найден для ID: {report_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Файл отчета не найден для ID: {report_id}"
            )
        
        # Пытаемся получить hostname из отчета для красивого имени
        try:
            # Простое извлечение hostname из метаданных HTML без полного парсинга
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(2000)  # Читаем только начало файла
                import re
                # Ищем hostname в метатегах
                hostname_match = re.search(r'<meta name="analyzer-hostname" content="([^"]+)"', content)
                if hostname_match:
                    hostname = hostname_match.group(1)
                else:
                    # Ищем в заголовке
                    title_match = re.search(r'<title>.*?([A-Za-z0-9\-_]+).*?</title>', content)
                    hostname = title_match.group(1) if title_match else "unknown"
                
                # Пытаемся найти ОС
                os_match = re.search(r'<strong>💻 ОС:</strong>\s*([^<]+)', content)
                os_name = os_match.group(1).strip() if os_match else ""
            
            # Очищаем имя от недопустимых символов
            safe_hostname = "".join(c for c in hostname if c.isalnum() or c in "._-")
            safe_os = "".join(c for c in os_name.split()[0] if c.isalnum() or c in "._-") if os_name else ""
            
            if safe_os:
                clean_filename = f"analyzer_report_{safe_hostname}_{safe_os}_{report_id[:8]}.html"
            else:
                clean_filename = f"analyzer_report_{safe_hostname}_{report_id[:8]}.html"
        except Exception:
            # Если не удалось распарсить, используем стандартное имя
            clean_filename = f"analyzer_report_{report_id}.html"
        
        print(f"📁 Отправляем файл: {clean_filename}")
        
        # Создаем ответ с правильными заголовками
        response = FileResponse(
            path=file_path,
            filename=clean_filename,
            media_type="text/html"
        )
        
        # Добавляем Content-Disposition заголовок для правильного имени файла
        response.headers["Content-Disposition"] = f'attachment; filename="{clean_filename}"'
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка download: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка скачивания отчета: {str(e)}"
        )

@api_router.delete("/reports/{report_id}")
async def delete_report(report_id: str, db: AsyncSession = Depends(get_db)):
    """Удаление отчета по ID или хешу"""
    try:
        from sqlalchemy import select, or_
        from models.report import Melt
        import uuid
        
        # Пытаемся найти отчет по ID или по хешу
        stmt = None
        
        # Проверяем, является ли report_id UUID
        try:
            uuid_obj = uuid.UUID(report_id)
            # Это UUID - ищем по ID
            stmt = select(Melt).where(Melt.id == uuid_obj)
        except ValueError:
            # Это не UUID - ищем по хешу или имени файла
            stmt = select(Melt).where(
                or_(
                    Melt.report_hash == report_id,
                    Melt.html_file_path.contains(report_id)
                )
            )
        
        if stmt is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат ID отчета"
            )
        
        result = await db.execute(stmt)
        report = result.scalar_one_or_none()
        
        if not report:
            # Fallback: пытаемся найти файл в файловой системе
            uploads_dir = "uploads"
            
            file_found = False
            
            # Если report_id выглядит как имя файла, ищем его точно
            if report_id.endswith('.html'):
                file_path = os.path.join(uploads_dir, report_id)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        file_found = True
                        print(f"🗑️ Удален файл по точному имени: {report_id}")
                    except Exception as e:
                        print(f"⚠️ Ошибка удаления файла {report_id}: {e}")
            
            # Если не нашли точного совпадения, пробуем другие варианты
            if not file_found:
                possible_files = [
                    f"{report_id}.html",
                    f"report_{report_id}.html"
                ]
                
                for filename in possible_files:
                    file_path = os.path.join(uploads_dir, filename)
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            file_found = True
                            print(f"🗑️ Удален файл (без записи в БД): {filename}")
                            break
                        except Exception as e:
                            print(f"⚠️ Ошибка удаления файла {filename}: {e}")
            
            # Ищем по частичному совпадению имени файла
            if not file_found and os.path.exists(uploads_dir):
                for filename in os.listdir(uploads_dir):
                    if report_id in filename and filename.endswith('.html'):
                        file_path = os.path.join(uploads_dir, filename)
                        try:
                            os.remove(file_path)
                            file_found = True
                            print(f"🗑️ Удален файл (частичное совпадение): {filename}")
                            break
                        except Exception as e:
                            print(f"⚠️ Ошибка удаления файла {filename}: {e}")
            
            if file_found:
                return {
                    "message": "Файл отчета удален",
                    "report_id": report_id,
                    "note": "Запись в базе данных не найдена"
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Отчет не найден"
                )
        
        # Сохраняем информацию об удаляемом отчете
        deleted_report_info = {
            "id": str(report.id),
            "hostname": report.hostname,
            "filename": os.path.basename(report.html_file_path) if report.html_file_path else "unknown",
            "report_hash": report.report_hash,
            "file_size": report.file_size or 0
        }
        
        # Удаляем файл отчета, если он существует
        file_deleted = False
        if report.html_file_path and os.path.exists(report.html_file_path):
            try:
                os.remove(report.html_file_path)
                file_deleted = True
                print(f"🗑️ Удален файл отчета: {report.html_file_path}")
            except Exception as e:
                print(f"⚠️ Ошибка удаления файла: {e}")
        
        # Удаляем запись из базы данных (каскадно удалятся связанные записи)
        await db.delete(report)
        await db.commit()
        
        print(f"✅ Отчет удален: ID={report.id}, hostname={report.hostname}")
        
        return {
            "message": "Отчет успешно удален",
            "deleted_report": deleted_report_info,
            "file_deleted": file_deleted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка удаления отчета: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления отчета: {str(e)}"
        )

@api_router.get("/health")
async def api_health():
    """Проверка здоровья API"""
    return {"status": "healthy", "api_version": "v1"}

@api_router.get("/reports/stats/summary")
async def get_melts_summary(db: AsyncSession = Depends(get_db)):
    """Получение общей статистики по отчетам"""
    try:
        print(f"🔍 [DEBUG] Начинаем подсчет статистики...")
        
        # Сначала пытаемся получить данные из базы данных
        try:
            from sqlalchemy import select, func
            from models.report import Melt
            
            print(f"🔍 [DEBUG] Пытаемся получить статистику из БД...")
            
            # Получаем агрегированную статистику из БД
            stmt = select(
                func.count(Melt.id).label('total_reports'),
                func.sum(Melt.total_connections).label('total_connections'),
                func.sum(Melt.tcp_ports_count).label('tcp_ports'),
                func.sum(Melt.udp_ports_count).label('udp_ports'),
                func.sum(Melt.unique_hosts).label('unique_hosts')
            )
            
            result = await db.execute(stmt)
            stats_row = result.first()
            
            if stats_row and stats_row.total_reports and stats_row.total_reports > 0:
                # Есть данные в БД
                total_melts = int(stats_row.total_reports or 0)
                total_connections = int(stats_row.total_connections or 0)
                tcp_ports = int(stats_row.tcp_ports or 0)
                udp_ports = int(stats_row.udp_ports or 0)
                total_ports = tcp_ports + udp_ports
                unique_hosts = int(stats_row.unique_hosts or 0)
                
                print(f"✅ [DEBUG] Статистика из БД:")
                print(f"   📊 Отчетов: {total_reports}")
                print(f"   🔗 Соединений: {total_connections}")
                print(f"   🚪 TCP портов: {tcp_ports}")
                print(f"   🚪 UDP портов: {udp_ports}")
                print(f"   🚪 Всего портов: {total_ports}")
                print(f"   🌐 Уникальных хостов: {unique_hosts}")
                
                return {
                    "total_reports": total_reports,
                    "total_connections": total_connections,
                    "total_ports": total_ports,
                    "unique_hosts": unique_hosts
                }
            else:
                print(f"⚠️ [DEBUG] БД пуста или нет валидных данных, переходим к файлам...")
                raise Exception("БД пуста, используем fallback")
                
        except Exception as db_error:
            print(f"⚠️ [DEBUG] Ошибка получения статистики из БД: {db_error}")
            print(f"🔄 [FALLBACK] Переходим к подсчету из файлов...")
        
        # Fallback: считаем статистику из файлов
        uploads_dir = "uploads"
        if not os.path.exists(uploads_dir):
            print(f"🔍 [DEBUG] Папка uploads не существует")
            return {
                "total_reports": 0,
                "total_connections": 0,
                "total_ports": 0,
                "unique_hosts": 0
            }
        
        total_melts = 0
        total_connections = 0
        total_ports = 0
        unique_hosts_set = set()  # Используем set для уникальных хостов
        
        html_files = [f for f in os.listdir(uploads_dir) if f.endswith('.html')]
        print(f"🔍 [FALLBACK] Найдено HTML файлов: {len(html_files)}")
        
        for filename in html_files:
            total_reports += 1
            try:
                file_path = os.path.join(uploads_dir, filename)
                parsed_data = await parse_analyzer_html_file(file_path)
                
                # Соединения
                connections_count = parsed_data.get("total_connections", 0)
                total_connections += connections_count
                
                # Правильно считаем порты из структуры {tcp: [...], udp: [...]}
                ports_data = parsed_data.get("ports", {})
                file_tcp_ports = 0
                file_udp_ports = 0
                
                if isinstance(ports_data, dict):
                    file_tcp_ports = len(ports_data.get("tcp", []))
                    file_udp_ports = len(ports_data.get("udp", []))
                elif isinstance(ports_data, list):
                    # Fallback для старого формата
                    for port in ports_data:
                        if isinstance(port, dict):
                            protocol = port.get('protocol', '').upper()
                            if protocol == 'TCP':
                                file_tcp_ports += 1
                            elif protocol == 'UDP':
                                file_udp_ports += 1
                else:
                    # Ищем в прямых полях
                    file_tcp_ports = parsed_data.get("tcp_ports_count", 0)
                    file_udp_ports = parsed_data.get("udp_ports_count", 0)
                
                file_total_ports = file_tcp_ports + file_udp_ports
                total_ports += file_total_ports
                
                # Уникальные хосты из соединений
                connections_data = parsed_data.get("connections", [])
                for conn in connections_data:
                    remote_addr = conn.get("remote_address", "")
                    if remote_addr and remote_addr != "*:*" and ":" in remote_addr:
                        # Извлекаем IP из адреса вида "192.168.1.1:80"
                        remote_ip = remote_addr.split(":")[0]
                        if remote_ip and remote_ip not in ["*", "0.0.0.0", "127.0.0.1"]:
                            unique_hosts_set.add(remote_ip)
                
                # Также добавляем удаленные хосты из отдельной секции
                remote_hosts_data = parsed_data.get("remote_hosts", [])
                for host in remote_hosts_data:
                    ip = host.get("ip_address", "") if isinstance(host, dict) else str(host)
                    if ip and ip not in ["*", "0.0.0.0", "127.0.0.1"]:
                        unique_hosts_set.add(ip)
                
                print(f"🔍 [FALLBACK] {filename}: connections={connections_count}, TCP={file_tcp_ports}, UDP={file_udp_ports}, total_ports={file_total_ports}")
                
            except Exception as e:
                # Игнорируем ошибки парсинга для статистики
                print(f"⚠️ Ошибка парсинга {filename} для статистики: {e}")
                continue
        
        unique_hosts_count = len(unique_hosts_set)
        
        print(f"📊 [FALLBACK] Итоговая статистика:")
        print(f"   📊 Отчетов: {total_reports}")
        print(f"   🔗 Соединений: {total_connections}")
        print(f"   🚪 Всего портов: {total_ports}")
        print(f"   🌐 Уникальных хостов: {unique_hosts_count}")
        
        return {
            "total_reports": total_reports,
            "total_connections": total_connections,
            "total_ports": total_ports,
            "unique_hosts": unique_hosts_count
        }
        
    except Exception as e:
        print(f"❌ [ERROR] Ошибка получения статистики: {e}")
        import traceback
        print(f"❌ [ERROR] Трейс: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        ) 