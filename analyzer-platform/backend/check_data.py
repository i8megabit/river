#!/usr/bin/env python3
import asyncio
from core.database import get_db_session
from models.report import Melt
from sqlalchemy import select

async def check_data():
    async for db in get_db_session():
        stmt = select(Melt).where(Melt.id == '3d2f1000-09bb-45c7-9637-38ed2d962281')
        result = await db.execute(stmt)
        melt = result.scalar_one_or_none()
        if melt:
            print(f'hostname: {melt.hostname}')
            print(f'tcp_connections: {melt.tcp_connections}')
            print(f'udp_connections: {melt.udp_connections}')
            print(f'icmp_connections: {melt.icmp_connections}')
            print(f'tcp_ports_count: {melt.tcp_ports_count}')
            print(f'udp_ports_count: {melt.udp_ports_count}')
        else:
            print('No melt found')
        break

if __name__ == "__main__":
    asyncio.run(check_data()) 