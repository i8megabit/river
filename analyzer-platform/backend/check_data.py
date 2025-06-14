#!/usr/bin/env python3
import asyncio
from core.database import get_db_session
from models.report import SystemReport
from sqlalchemy import select

async def check_data():
    async for db in get_db_session():
        stmt = select(SystemReport).where(SystemReport.id == '3d2f1000-09bb-45c7-9637-38ed2d962281')
        result = await db.execute(stmt)
        report = result.scalar_one_or_none()
        if report:
            print(f'hostname: {report.hostname}')
            print(f'tcp_connections: {report.tcp_connections}')
            print(f'udp_connections: {report.udp_connections}')
            print(f'icmp_connections: {report.icmp_connections}')
            print(f'tcp_ports_count: {report.tcp_ports_count}')
            print(f'udp_ports_count: {report.udp_ports_count}')
        else:
            print('No report found')
        break

if __name__ == "__main__":
    asyncio.run(check_data()) 