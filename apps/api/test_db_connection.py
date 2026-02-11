"""Test database connection with asyncpg."""
import asyncio
import asyncpg


async def test_connection():
    """Test async database connection."""
    try:
        conn = await asyncpg.connect(
            host="localhost",
            port=5433,
            user="nonsuperuser",
            password="test",
            database="c2pro_test",
        )
        result = await conn.fetchval("SELECT 1")
        print(f"✅ Connection successful! Result: {result}")
        await conn.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(test_connection())
