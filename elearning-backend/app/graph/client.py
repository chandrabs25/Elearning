"""Neo4j async client for E-Learning Platform."""
import asyncio
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired
from app.config import settings


class Neo4jClient:
    """Async Neo4j client with connection pooling and retry logic."""
    
    def __init__(self):
        self._driver = None
    
    @property
    def driver(self):
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                # Serverless-friendly settings
                max_connection_lifetime=300,  # 5 minutes
                max_connection_pool_size=10,
                connection_acquisition_timeout=30,
            )
        return self._driver
    
    async def verify_connectivity(self, max_retries: int = 3):
        """Verify Neo4j connection on startup with retry."""
        for attempt in range(max_retries):
            try:
                await self.driver.verify_connectivity()
                print(f"✓ Connected to Neo4j at {settings.neo4j_uri}")
                return
            except (ServiceUnavailable, SessionExpired) as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"⚠ Neo4j connection attempt {attempt + 1} failed, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    # Reset driver to force new connection
                    if self._driver:
                        await self._driver.close()
                        self._driver = None
                else:
                    print(f"✗ Neo4j connection failed after {max_retries} attempts")
                    raise
    
    async def close(self):
        """Close the driver on shutdown."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            print("✓ Neo4j connection closed")
    
    async def _execute_with_retry(self, operation, max_retries: int = 2):
        """Execute operation with retry on connection errors."""
        for attempt in range(max_retries):
            try:
                return await operation()
            except (ServiceUnavailable, SessionExpired) as e:
                if attempt < max_retries - 1:
                    print(f"⚠ Neo4j query failed, retrying... ({e})")
                    # Reset driver
                    if self._driver:
                        await self._driver.close()
                        self._driver = None
                    await asyncio.sleep(1)
                else:
                    raise
    
    async def execute_read(self, query: str, **params):
        """Execute a read query with retry."""
        async def operation():
            async with self.driver.session() as session:
                result = await session.run(query, **params)
                return [record.data() async for record in result]
        return await self._execute_with_retry(operation)
    
    async def execute_read_single(self, query: str, **params):
        """Execute a read query and return single result with retry."""
        async def operation():
            async with self.driver.session() as session:
                result = await session.run(query, **params)
                record = await result.single()
                return record.data() if record else None
        return await self._execute_with_retry(operation)


# Singleton instance
neo4j_client = Neo4jClient()
