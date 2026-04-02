"""
Database setup script for Lite LLM API Service
Run this script to initialize the databases and create tables
"""

import asyncio
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine
from database import Base, APIKey, APIKeyRotation, APICall, DailyUsage, ModelServer, HourlyMetrics
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_databases():
    """Create the three databases if they don't exist"""
    
    # Extract connection details from the database URLs
    api_keys_url = settings.database_url
    usage_logs_url = settings.usage_logs_db_url  
    analytics_db_url = settings.analytics_db_url
    
    # Parse the URLs to get connection details
    def parse_url(url):
        # Remove the +asyncpg driver for connection
        clean_url = url.replace("+asyncpg", "")
        # Extract database name from the end
        db_name = clean_url.split("/")[-1]
        # Get the base URL (without database name)
        base_url = "/".join(clean_url.split("/")[:-1])
        return base_url, db_name
    
    api_keys_base, api_keys_db = parse_url(api_keys_url)
    usage_logs_base, usage_logs_db = parse_url(usage_logs_url)
    analytics_base, analytics_db = parse_url(analytics_db_url)
    
    # Connect to postgres database to create new databases
    conn = await asyncpg.connect("postgresql://username:password@localhost/postgres")
    
    try:
        # Create databases
        logger.info(f"Creating database: {api_keys_db}")
        await conn.execute(f"CREATE DATABASE {api_keys_db} IF NOT EXISTS")
        
        logger.info(f"Creating database: {usage_logs_db}")
        await conn.execute(f"CREATE DATABASE {usage_logs_db} IF NOT EXISTS")
        
        logger.info(f"Creating database: {analytics_db}")
        await conn.execute(f"CREATE DATABASE {analytics_db} IF NOT EXISTS")
        
        logger.info("All databases created successfully")
        
    except Exception as e:
        logger.error(f"Error creating databases: {e}")
        raise
    finally:
        await conn.close()


async def create_tables():
    """Create all tables in the databases"""
    
    logger.info("Creating tables...")
    
    # API Keys Database
    api_keys_engine = create_async_engine(settings.database_url, echo=True)
    async with api_keys_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[APIKey.__table__, APIKeyRotation.__table__])
    await api_keys_engine.dispose()
    
    # Usage Logs Database
    usage_logs_engine = create_async_engine(settings.usage_logs_db_url, echo=True)
    async with usage_logs_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[APICall.__table__])
    await usage_logs_engine.dispose()
    
    # Analytics Database
    analytics_engine = create_async_engine(settings.analytics_db_url, echo=True)
    async with analytics_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[DailyUsage.__table__, ModelServer.__table__, HourlyMetrics.__table__])
    await analytics_engine.dispose()
    
    logger.info("All tables created successfully")


async def create_sample_data():
    """Create sample data for testing"""
    
    from database import db_manager
    from datetime import datetime, timedelta
    import uuid
    import bcrypt
    
    # Initialize database manager
    await db_manager.initialize(
        settings.database_url,
        settings.usage_logs_db_url,
        settings.analytics_db_url
    )
    
    # Create sample API key
    async with db_manager.get_api_keys_session() as session:
        sample_key = "sk-sample-key-for-testing"
        key_hash = bcrypt.hashpw(sample_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        api_key = APIKey(
            key_hash=key_hash,
            name="Sample API Key",
            expires_at=datetime.utcnow() + timedelta(days=365)
        )
        session.add(api_key)
        await session.commit()
        logger.info(f"Created sample API key: {sample_key}")
    
    # Create sample model server
    async with db_manager.get_analytics_session() as session:
        server = ModelServer(
            name="Sample Server",
            endpoint="https://api.openai.com",
            models=["gpt-3.5-turbo", "gpt-4"],
            weight=1
        )
        session.add(server)
        await session.commit()
        logger.info("Created sample model server")
    
    await db_manager.close()


async def main():
    """Main setup function"""
    try:
        # Create databases
        await create_databases()
        
        # Create tables
        await create_tables()
        
        # Create sample data (optional)
        await create_sample_data()
        
        logger.info("Database setup completed successfully!")
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
