"""Neo4j async client for E-Learning Platform."""
from neo4j import AsyncGraphDatabase
from app.config import settings


class Neo4jClient:
    """Async Neo4j client with connection pooling."""
    
    def __init__(self):
        self._driver = None
    
    @property
    def driver(self):
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
        return self._driver
    
    async def verify_connectivity(self):
        """Verify Neo4j connection on startup."""
        await self.driver.verify_connectivity()
        print(f"✓ Connected to Neo4j at {settings.neo4j_uri}")
    
    async def close(self):
        """Close the driver on shutdown."""
        if self._driver:
            await self._driver.close()
            print("✓ Neo4j connection closed")
    
    async def execute_read(self, query: str, **params):
        """Execute a read query."""
        async with self.driver.session() as session:
            result = await session.run(query, **params)
            return [record.data() async for record in result]
    
    async def execute_read_single(self, query: str, **params):
        """Execute a read query and return single result."""
        async with self.driver.session() as session:
            result = await session.run(query, **params)
            record = await result.single()
            return record.data() if record else None


# Singleton instance
neo4j_client = Neo4jClient()
