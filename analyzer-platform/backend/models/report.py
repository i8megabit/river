#!/usr/bin/env python3
"""
Модели данных для отчетов анализатора
Структура точно соответствует HTML отчетам, генерируемым анализатором
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid

from core.database import Base


class Melt(Base):
    """
    Основная модель отчета системы - соответствует структуре HTML отчета
    """
    __tablename__ = "system_reports"
    
    # Основные поля
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Уникальный хеш отчета для предотвращения дублирования
    report_hash = Column(String(64), unique=True, index=True, nullable=False)
    
    # Метаданные отчета (из header HTML)
    hostname = Column(String(255), nullable=False, index=True)
    report_title = Column(String(500), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Информация о системе (из header-info HTML)
    os_name = Column(String(255))
    os_version = Column(String(255))
    first_run = Column(DateTime)
    last_update = Column(DateTime)
    total_measurements = Column(Integer, default=1)
    
    # Файлы отчетов
    html_file_path = Column(String(1000))  # Путь к HTML файлу
    yaml_file_path = Column(String(1000))  # Путь к YAML файлу
    json_file_path = Column(String(1000))  # Путь к JSON файлу
    
    # Статистика системы (из stats секции HTML)
    total_connections = Column(Integer, default=0)
    incoming_connections = Column(Integer, default=0)
    outgoing_connections = Column(Integer, default=0)
    
    # Соединения по протоколам (отдельно от портов!)
    tcp_connections = Column(Integer, default=0)
    udp_connections = Column(Integer, default=0) 
    icmp_connections = Column(Integer, default=0)
    
    unique_processes = Column(Integer, default=0)
    unique_hosts = Column(Integer, default=0)
    tcp_ports_count = Column(Integer, default=0)
    udp_ports_count = Column(Integer, default=0)
    change_events_count = Column(Integer, default=0)
    
    # JSON поля для сложных данных
    raw_data = Column(JSON)  # Полные сырые данные из анализатора
    changes_summary = Column(JSON)  # Суммарная информация об изменениях
    
    # Технические поля
    file_size = Column(Integer)  # Размер HTML файла
    processing_status = Column(String(50), default="pending")  # pending, processed, error
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи с другими таблицами
    connections = relationship("NetworkConnection", back_populates="report", cascade="all, delete-orphan")
    ports = relationship("NetworkPort", back_populates="report", cascade="all, delete-orphan")
    remote_hosts = relationship("RemoteHost", back_populates="report", cascade="all, delete-orphan")
    change_history = relationship("ChangeHistory", back_populates="report", cascade="all, delete-orphan")
    network_interfaces = relationship("NetworkInterface", back_populates="report", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Melt(hostname='{self.hostname}', generated_at='{self.generated_at}')>"


class NetworkConnection(Base):
    """
    Сетевые соединения - соответствует connections секции HTML
    """
    __tablename__ = "network_connections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("system_reports.id"), nullable=False)
    
    # Данные соединения (из connections-table HTML)
    connection_type = Column(String(20))  # incoming, outgoing
    local_address = Column(String(100))
    remote_address = Column(String(100))
    remote_hostname = Column(String(255))
    process_name = Column(String(255))
    protocol = Column(String(10))  # tcp, udp, icmp
    
    # Временные метки (из HTML отчета)
    first_seen = Column(DateTime)
    last_seen = Column(DateTime)
    packet_count = Column(Integer, default=0)
    
    # Дополнительные данные
    connection_status = Column(String(50))  # active, established, listening
    bytes_sent = Column(Integer, default=0)
    bytes_received = Column(Integer, default=0)
    
    # Связь с отчетом
    report = relationship("Melt", back_populates="connections")
    
    def __repr__(self):
        return f"<NetworkConnection(local='{self.local_address}', remote='{self.remote_address}')>"


class NetworkPort(Base):
    """
    Сетевые порты - соответствует ports секции HTML
    """
    __tablename__ = "network_ports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("system_reports.id"), nullable=False)
    
    # Данные порта (из ports-grid HTML)
    port_number = Column(Integer, nullable=False)
    protocol = Column(String(10), nullable=False)  # tcp, udp
    description = Column(Text)  # Описание порта из get_port_description
    service_name = Column(String(100))  # Имя сервиса
    
    # Статус порта
    status = Column(String(20), default="listening")  # listening, closed, filtered
    process_name = Column(String(255))
    
    # Связь с отчетом
    report = relationship("Melt", back_populates="ports")
    
    def __repr__(self):
        return f"<NetworkPort(port={self.port_number}, protocol='{self.protocol}')>"


class RemoteHost(Base):
    """
    Удаленные хосты - соответствует remote hosts данным из HTML
    """
    __tablename__ = "remote_hosts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("system_reports.id"), nullable=False)
    
    # Данные хоста
    ip_address = Column(String(45), nullable=False)  # IPv4/IPv6
    hostname = Column(String(255))
    
    # Статистика взаимодействия
    connection_count = Column(Integer, default=0)
    first_seen = Column(DateTime)
    last_seen = Column(DateTime)
    
    # Дополнительная информация
    country = Column(String(100))
    organization = Column(String(255))
    is_local = Column(Boolean, default=False)
    
    # Связь с отчетом
    report = relationship("Melt", back_populates="remote_hosts")
    
    def __repr__(self):
        return f"<RemoteHost(ip='{self.ip_address}', hostname='{self.hostname}')>"


class ChangeHistory(Base):
    """
    История изменений - соответствует changes секции HTML
    """
    __tablename__ = "change_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("system_reports.id"), nullable=False)
    
    # Данные изменения (из changes-timeline HTML)
    measurement_id = Column(Integer)
    change_timestamp = Column(DateTime, nullable=False)
    is_first_run = Column(Boolean, default=False)
    
    # Категории изменений
    changed_categories = Column(ARRAY(String))  # Список изменившихся категорий
    change_details = Column(JSON)  # Детали изменений
    
    # Связь с отчетом
    report = relationship("Melt", back_populates="change_history")
    
    def __repr__(self):
        return f"<ChangeHistory(measurement_id={self.measurement_id}, timestamp='{self.change_timestamp}')>"


class NetworkInterface(Base):
    """
    Сетевые интерфейсы - соответствует network stats секции HTML
    """
    __tablename__ = "network_interfaces"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("system_reports.id"), nullable=False)
    
    # Данные интерфейса (из interface-card HTML)
    interface_name = Column(String(100), nullable=False)
    
    # Статистика пакетов (из interface-stats HTML)
    packets_in = Column(Integer, default=0)
    packets_out = Column(Integer, default=0)
    bytes_in = Column(Integer, default=0)
    bytes_out = Column(Integer, default=0)
    
    # Дополнительная информация
    mtu = Column(Integer)
    status = Column(String(20))  # up, down
    mac_address = Column(String(17))
    ip_addresses = Column(ARRAY(String))  # Список IP адресов
    
    # Связь с отчетом
    report = relationship("Melt", back_populates="network_interfaces")
    
    def __repr__(self):
        return f"<NetworkInterface(name='{self.interface_name}', packets_in={self.packets_in})>"


class ReportFile(Base):
    """
    Файлы отчетов - для управления загруженными файлами
    """
    __tablename__ = "report_files"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("system_reports.id"), nullable=False)
    
    # Информация о файле
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_type = Column(String(10), nullable=False)  # html, yaml, json
    file_size = Column(Integer)
    content_hash = Column(String(64))  # SHA-256 хеш содержимого
    
    # Временные метки
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    
    # Связь с отчетом
    report = relationship("Melt", foreign_keys=[report_id])
    
    def __repr__(self):
        return f"<ReportFile(filename='{self.filename}', type='{self.file_type}')>"


# Индексы для оптимизации запросов
from sqlalchemy import Index

# Индексы для частых поисковых запросов
Index('idx_reports_hostname_date', Melt.hostname, Melt.generated_at)
Index('idx_reports_created_at', Melt.created_at)
Index('idx_connections_report_protocol', NetworkConnection.report_id, NetworkConnection.protocol)
Index('idx_ports_report_port', NetworkPort.report_id, NetworkPort.port_number)
Index('idx_hosts_report_ip', RemoteHost.report_id, RemoteHost.ip_address)
Index('idx_changes_report_timestamp', ChangeHistory.report_id, ChangeHistory.change_timestamp) 