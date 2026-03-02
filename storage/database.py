"""
OKTAGON SAV v10.0 — Connexion base de données avec SSL/TLS
Pool asyncpg + helper queries
"""
import asyncpg
import ssl
from typing import Optional, Any

from logger import logger


class Database:
    """Gestionnaire de base de données avec pool de connexions"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self, host: str, port: int, database: str,
                      user: str, password: str,
                      pool_min: int = 2, pool_max: int = 10) -> None:
        """Établir la connexion au pool PostgreSQL avec SSL/TLS"""
        # v10.0 — Force SSL connection for security
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE  # Accept self-signed cert
        
        self.pool = await asyncpg.create_pool(
            host=host, port=port, database=database,
            user=user, password=password,
            min_size=pool_min, max_size=pool_max,
            command_timeout=60,
            ssl=ssl_context  # FORCE SSL/TLS
        )
        logger.info('Pool DB créé avec SSL/TLS', extra={'action': 'db_connect'})

    async def close(self) -> None:
        """Fermer le pool de connexions"""
        if self.pool:
            await self.pool.close()
            logger.info('Pool DB fermé', extra={'action': 'db_close'})

    async def execute(self, query: str, *args) -> str:
        """Exécuter une requête sans retour"""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch_one(self, query: str, *args) -> Optional[Any]:
        """Fetch une seule ligne"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetch_all(self, query: str, *args) -> list:
        """Fetch toutes les lignes"""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def insert_returning_id(self, query: str, *args) -> int:
        """Insert et retourne l'ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return row['id'] if row else None


# Instance globale
db = Database()
