"""
Database setup and connection management for Lite LLM API Service
Supports both PostgreSQL (production) and SQLite (development)
"""

import asyncio
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, BigInteger, DECIMAL, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import sqlalchemy as sa
from datetime import datetime, timedelta
from typing import Optional, Dict
import uuid

# Base class for all models
Base = declarative_base()

# Database Models (same for both PostgreSQL and SQLite)
class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    last_used = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(BigInteger, default=0)

class APIKeyRotation(Base):
    __tablename__ = "api_key_rotations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False)
    old_key_hash = Column(String(255), nullable=False)
    new_key_hash = Column(String(255), nullable=False)
    rotated_at = Column(DateTime(timezone=True), server_default=func.now())

class APICall(Base):
    __tablename__ = "api_calls"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=True, index=True)
    model = Column(String(255), nullable=False, index=True)
    server_endpoint = Column(String(255), nullable=False)
    request_tokens = Column(Integer, nullable=True)
    response_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    request_id = Column(String(255), unique=True)

class DailyUsage(Base):
    __tablename__ = "daily_usage"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    date = Column(Date, nullable=False, index=True)
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=True, index=True)
    model = Column(String(255), nullable=False, index=True)
    total_requests = Column(BigInteger, default=0)
    total_tokens = Column(BigInteger, default=0)
    avg_response_time = Column(DECIMAL(10,2), nullable=True)
    error_rate = Column(DECIMAL(5,4), default=0.0000)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Unique constraint to prevent duplicate daily records
    __table_args__ = (
        sa.UniqueConstraint('date', 'api_key_id', 'model', name='unique_daily_usage'),
    )

class HourlyMetrics(Base):
    __tablename__ = "hourly_metrics"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hour_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    server_id = Column(String(36), nullable=False, index=True)
    model = Column(String(255), nullable=False, index=True)
    request_count = Column(BigInteger, default=0)
    total_tokens = Column(BigInteger, default=0)
    avg_response_time = Column(DECIMAL(10,2), nullable=True)
    error_count = Column(BigInteger, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Unique constraint to prevent duplicate hourly records
    __table_args__ = (
        sa.UniqueConstraint('hour_timestamp', 'server_id', 'model', name='unique_hourly_metrics'),
    )


# Database connection managers
class DatabaseManager:
    def __init__(self):
        self.api_keys_engine = None
        self.usage_logs_engine = None
        self.analytics_engine = None
        self.api_keys_session_factory = None
        self.usage_logs_session_factory = None
        self.analytics_session_factory = None
        self.db_type = "sqlite"  # Default to SQLite
    
    async def initialize(self, db_urls: Dict[str, str]):
        """Initialize database connections with appropriate URLs"""
        
        # Determine database type from URLs
        first_url = list(db_urls.values())[0]
        self.db_type = "postgresql" if "postgresql" in first_url else "sqlite"
        
        # Ensure data directory exists for SQLite
        if self.db_type == "sqlite":
            data_dir = Path(first_url.replace("sqlite+aiosqlite:///", "").replace("/", "").split(".db")[0])
            data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create engines
        self.api_keys_engine = create_async_engine(
            db_urls["api_keys"],
            echo=False,
            pool_size=20 if self.db_type == "postgresql" else 5,
            max_overflow=30 if self.db_type == "postgresql" else 10,
            pool_pre_ping=True,
            pool_recycle=3600 if self.db_type == "postgresql" else None
        )
        
        self.usage_logs_engine = create_async_engine(
            db_urls["usage_logs"],
            echo=False,
            pool_size=20 if self.db_type == "postgresql" else 5,
            max_overflow=30 if self.db_type == "postgresql" else 10,
            pool_pre_ping=True,
            pool_recycle=3600 if self.db_type == "postgresql" else None
        )
        
        self.analytics_engine = create_async_engine(
            db_urls["analytics"],
            echo=False,
            pool_size=10 if self.db_type == "postgresql" else 3,
            max_overflow=20 if self.db_type == "postgresql" else 5,
            pool_pre_ping=True,
            pool_recycle=3600 if self.db_type == "postgresql" else None
        )
        
        # Create session factories
        self.api_keys_session_factory = async_sessionmaker(
            self.api_keys_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        self.usage_logs_session_factory = async_sessionmaker(
            self.usage_logs_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        self.analytics_session_factory = async_sessionmaker(
            self.analytics_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create all tables
        await self.create_tables()
    
    async def create_tables(self):
        """Create all database tables"""
        async with self.api_keys_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[APIKey.__table__, APIKeyRotation.__table__])
        
        async with self.usage_logs_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[APICall.__table__])
        
        async with self.analytics_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=[DailyUsage.__table__, HourlyMetrics.__table__])
    
    async def close(self):
        """Close all database connections"""
        if self.api_keys_engine:
            await self.api_keys_engine.dispose()
        if self.usage_logs_engine:
            await self.usage_logs_engine.dispose()
        if self.analytics_engine:
            await self.analytics_engine.dispose()
    
    def get_api_keys_session(self) -> AsyncSession:
        """Get API keys database session"""
        return self.api_keys_session_factory()
    
    def get_usage_logs_session(self) -> AsyncSession:
        """Get usage logs database session"""
        return self.usage_logs_session_factory()
    
    def get_analytics_session(self) -> AsyncSession:
        """Get analytics database session"""
        return self.analytics_session_factory()
    
    async def get_database_info(self) -> Dict[str, Any]:
        """Get information about current database setup"""
        return {
            "db_type": self.db_type,
            "engines": {
                "api_keys": str(self.api_keys_engine.url) if self.api_keys_engine else None,
                "usage_logs": str(self.usage_logs_engine.url) if self.usage_logs_engine else None,
                "analytics": str(self.analytics_engine.url) if self.analytics_engine else None
            }
        }


# Global database manager instance
db_manager = DatabaseManager()


# Dependency functions for FastAPI
async def get_api_keys_db():
    async with db_manager.get_api_keys_session() as session:
        yield session


async def get_usage_logs_db():
    async with db_manager.get_usage_logs_session() as session:
        yield session


async def get_analytics_db():
    async with db_manager.get_analytics_session() as session:
        yield session


# Database utility functions
async def cleanup_old_data(retention_days: int = 180):
    """Clean up old data based on retention policy"""
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    async with db_manager.get_usage_logs_session() as session:
        # Delete old API calls
        await session.execute(
            sa.delete(APICall).where(APICall.timestamp < cutoff_date)
        )
        await session.commit()
    
    async with db_manager.get_analytics_session() as session:
        # Delete old hourly metrics
        await session.execute(
            sa.delete(HourlyMetrics).where(HourlyMetrics.hour_timestamp < cutoff_date)
        )
        await session.commit()
        
        # Delete old daily usage (keep longer if needed)
        daily_cutoff = datetime.utcnow() - timedelta(days=retention_days * 2)  # Keep daily stats longer
        await session.execute(
            sa.delete(DailyUsage).where(DailyUsage.date < daily_cutoff.date())
        )
        await session.commit()


async def create_indexes():
    """Create performance indexes"""
    async with db_manager.usage_logs_engine.begin() as conn:
        # API calls indexes
        if db_manager.db_type == "postgresql":
            await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_api_calls_timestamp_key ON api_calls(timestamp, api_key_id)"))
            await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_api_calls_model_timestamp ON api_calls(model, timestamp)"))
            await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_api_calls_status_timestamp ON api_calls(status_code, timestamp)"))
        else:
            # SQLite indexes are created automatically with index=True in columns
    
    async with db_manager.analytics_engine.begin() as conn:
        # Analytics indexes
        if db_manager.db_type == "postgresql":
            await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_daily_usage_date_model ON daily_usage(date, model)"))
            await conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_hourly_metrics_hour_model ON hourly_metrics(hour_timestamp, model)"))
