"""
Tests unitaires pour storage/database.py
Coverage cible : 70%
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from storage.database import Database


@pytest.fixture
def db():
    """Database instance for testing"""
    return Database()


class TestDatabaseInit:
    """Tests pour l'initialisation"""
    
    def test_init_creates_none_pool(self):
        """L'init crée une instance avec pool=None"""
        db = Database()
        assert db.pool is None


class TestDatabaseConnect:
    """Tests pour la connexion"""
    
    @pytest.mark.asyncio
    async def test_connect_creates_pool(self, db):
        """Connect crée un pool SSL avec les bons paramètres"""
        with patch('asyncpg.create_pool', new_callable=AsyncMock) as mock_create:
            mock_pool = AsyncMock()
            mock_create.return_value = mock_pool
            
            await db.connect(
                host='localhost',
                port=5432,
                database='test_db',
                user='test_user',
                password='test_pass',
                pool_min=2,
                pool_max=10
            )
            
            # Vérifier que create_pool a été appelé
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            
            assert call_kwargs['host'] == 'localhost'
            assert call_kwargs['port'] == 5432
            assert call_kwargs['database'] == 'test_db'
            assert call_kwargs['user'] == 'test_user'
            assert call_kwargs['min_size'] == 2
            assert call_kwargs['max_size'] == 10
            assert call_kwargs['command_timeout'] == 60
            assert call_kwargs['ssl'] is not None
            
            assert db.pool == mock_pool
    
    @pytest.mark.asyncio
    async def test_connect_with_ssl_context(self, db):
        """Connect crée un contexte SSL correct"""
        with patch('asyncpg.create_pool', new_callable=AsyncMock) as mock_create:
            await db.connect('localhost', 5432, 'db', 'user', 'pass')
            
            ssl_context = mock_create.call_args.kwargs['ssl']
            assert ssl_context.check_hostname is False
            assert ssl_context.verify_mode == 0  # CERT_NONE


class TestDatabaseClose:
    """Tests pour la fermeture"""
    
    @pytest.mark.asyncio
    async def test_close_with_pool(self, db):
        """Close ferme le pool si présent"""
        mock_pool = AsyncMock()
        db.pool = mock_pool
        
        await db.close()
        
        mock_pool.close.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_close_without_pool(self, db):
        """Close ne crash pas si pool=None"""
        db.pool = None
        await db.close()  # Should not crash


class TestDatabaseExecute:
    """Tests pour execute()"""
    
    @pytest.mark.asyncio
    async def test_execute_runs_query(self, db):
        """Execute exécute une requête"""
        # Create mock connection
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value='UPDATE 1')
        
        # Create mock pool with proper context manager
        mock_acquire = MagicMock()
        mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire.__aexit__ = AsyncMock(return_value=None)
        
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_acquire)
        
        db.pool = mock_pool
        
        result = await db.execute('UPDATE test SET x = ', 42)
        
        mock_conn.execute.assert_awaited_once_with('UPDATE test SET x = ', 42)
        assert result == 'UPDATE 1'


class TestDatabaseFetchOne:
    """Tests pour fetch_one()"""
    
    @pytest.mark.asyncio
    async def test_fetch_one_returns_row(self, db):
        """fetch_one retourne une ligne"""
        mock_row = {'id': 1, 'name': 'test'}
        
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        
        mock_acquire = MagicMock()
        mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire.__aexit__ = AsyncMock(return_value=None)
        
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_acquire)
        
        db.pool = mock_pool
        
        result = await db.fetch_one('SELECT * FROM test WHERE id = ', 1)
        
        mock_conn.fetchrow.assert_awaited_once()
        assert result == mock_row
    
    @pytest.mark.asyncio
    async def test_fetch_one_returns_none(self, db):
        """fetch_one retourne None si pas de résultat"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        
        mock_acquire = MagicMock()
        mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire.__aexit__ = AsyncMock(return_value=None)
        
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_acquire)
        
        db.pool = mock_pool
        
        result = await db.fetch_one('SELECT * FROM test WHERE id = ', 999)
        
        assert result is None


class TestDatabaseFetchAll:
    """Tests pour fetch_all()"""
    
    @pytest.mark.asyncio
    async def test_fetch_all_returns_rows(self, db):
        """fetch_all retourne plusieurs lignes"""
        mock_rows = [
            {'id': 1, 'name': 'test1'},
            {'id': 2, 'name': 'test2'}
        ]
        
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        
        mock_acquire = MagicMock()
        mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire.__aexit__ = AsyncMock(return_value=None)
        
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_acquire)
        
        db.pool = mock_pool
        
        result = await db.fetch_all('SELECT * FROM test')
        
        mock_conn.fetch.assert_awaited_once()
        assert result == mock_rows
        assert len(result) == 2


class TestDatabaseInsertReturningId:
    """Tests pour insert_returning_id()"""
    
    @pytest.mark.asyncio
    async def test_insert_returns_id(self, db):
        """insert_returning_id retourne l'ID"""
        mock_row = {'id': 42}
        
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        
        mock_acquire = MagicMock()
        mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire.__aexit__ = AsyncMock(return_value=None)
        
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_acquire)
        
        db.pool = mock_pool
        
        result = await db.insert_returning_id(
            'INSERT INTO test (name) VALUES () RETURNING id',
            'test_name'
        )
        
        assert result == 42
    
    @pytest.mark.asyncio
    async def test_insert_returns_none_on_no_row(self, db):
        """insert_returning_id retourne None si pas de row"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        
        mock_acquire = MagicMock()
        mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire.__aexit__ = AsyncMock(return_value=None)
        
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_acquire)
        
        db.pool = mock_pool
        
        result = await db.insert_returning_id('INSERT INTO test VALUES (1)')
        
        assert result is None
