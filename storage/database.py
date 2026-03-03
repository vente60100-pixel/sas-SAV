"""
OKTAGON SAV v11.0 — Connexion base de données avec SSL/TLS
Pool asyncpg + helper queries + transactions + monitoring
"""
import os
import time
import asyncpg
import ssl
from contextlib import asynccontextmanager
from typing import Optional, Any

from logger import logger

# Seuil de requête lente (en secondes)
SLOW_QUERY_THRESHOLD = 1.0


class Database:
    """Gestionnaire de base de données avec pool de connexions"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self, host: str, port: int, database: str,
                      user: str, password: str,
                      pool_min: int = 2, pool_max: int = 10) -> None:
        """Établir la connexion au pool PostgreSQL avec SSL/TLS"""
        ssl_mode = os.getenv('POSTGRES_SSL_MODE', 'prefer')

        if ssl_mode == 'disable':
            ssl_param = False
        elif ssl_mode == 'require':
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            ssl_param = ssl_context
        elif ssl_mode == 'verify-full':
            ssl_param = ssl.create_default_context()
        else:
            # 'prefer': essayer avec SSL, fallback sans
            ssl_param = 'prefer'

        self.pool = await asyncpg.create_pool(
            host=host, port=port, database=database,
            user=user, password=password,
            min_size=pool_min, max_size=pool_max,
            command_timeout=60,
            ssl=ssl_param
        )
        logger.info('Pool DB créé avec SSL/TLS', extra={'action': 'db_connect'})

    async def close(self) -> None:
        """Fermer le pool de connexions"""
        if self.pool:
            await self.pool.close()
            logger.info('Pool DB fermé', extra={'action': 'db_close'})

    def _log_slow_query(self, query: str, duration: float) -> None:
        """Log les requêtes lentes."""
        if duration > SLOW_QUERY_THRESHOLD:
            logger.warning(
                f"Requête lente ({duration:.2f}s): {query[:120]}",
                extra={'action': 'slow_query', 'duration_ms': int(duration * 1000)}
            )

    async def execute(self, query: str, *args) -> str:
        """Exécuter une requête sans retour"""
        start = time.monotonic()
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, *args)
        self._log_slow_query(query, time.monotonic() - start)
        return result

    async def fetch_one(self, query: str, *args) -> Optional[Any]:
        """Fetch une seule ligne"""
        start = time.monotonic()
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(query, *args)
        self._log_slow_query(query, time.monotonic() - start)
        return result

    async def fetch_all(self, query: str, *args) -> list:
        """Fetch toutes les lignes"""
        start = time.monotonic()
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, *args)
        self._log_slow_query(query, time.monotonic() - start)
        return result

    async def insert_returning_id(self, query: str, *args) -> int:
        """Insert et retourne l'ID"""
        start = time.monotonic()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
        self._log_slow_query(query, time.monotonic() - start)
        return row['id'] if row else None

    @asynccontextmanager
    async def transaction(self):
        """Context manager pour transactions atomiques.

        Usage:
            async with db.transaction() as conn:
                await conn.execute("INSERT ...", ...)
                await conn.execute("UPDATE ...", ...)
                # Commit automatique, rollback si exception
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn


# Instance globale
db = Database()
