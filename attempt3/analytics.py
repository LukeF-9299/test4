"""
Analytics and reporting system for Lite LLM API Service
"""

import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.sql import text
import structlog

from database import (
    APICall, DailyUsage, HourlyMetrics, ModelServer,
    get_usage_logs_db, get_analytics_db, db_manager
)
from config import settings

logger = structlog.get_logger()


class AnalyticsEngine:
    """Handles analytics calculations and reporting"""
    
    def __init__(self):
        self.hourly_aggregation_task = None
        self.daily_aggregation_task = None
    
    async def start_background_tasks(self):
        """Start background aggregation tasks"""
        # Hourly aggregation (runs every hour)
        self.hourly_aggregation_task = asyncio.create_task(
            self._hourly_aggregation_loop()
        )
        
        # Daily aggregation (runs once per day at midnight)
        self.daily_aggregation_task = asyncio.create_task(
            self._daily_aggregation_loop()
        )
        
        logger.info("Analytics background tasks started")
    
    async def stop_background_tasks(self):
        """Stop background aggregation tasks"""
        if self.hourly_aggregation_task:
            self.hourly_aggregation_task.cancel()
        if self.daily_aggregation_task:
            self.daily_aggregation_task.cancel()
        
        logger.info("Analytics background tasks stopped")
    
    async def _hourly_aggregation_loop(self):
        """Background task that runs hourly aggregation"""
        
        while True:
            try:
                # Wait until next hour
                now = datetime.utcnow()
                next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                sleep_seconds = (next_hour - now).total_seconds()
                
                if sleep_seconds > 0:
                    await asyncio.sleep(sleep_seconds)
                
                # Run hourly aggregation
                await self.aggregate_hourly_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Hourly aggregation failed", error=str(e))
                # Continue running even if aggregation fails
    
    async def _daily_aggregation_loop(self):
        """Background task that runs daily aggregation"""
        
        while True:
            try:
                # Wait until next midnight UTC
                now = datetime.utcnow()
                next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                sleep_seconds = (next_midnight - now).total_seconds()
                
                if sleep_seconds > 0:
                    await asyncio.sleep(sleep_seconds)
                
                # Run daily aggregation
                await self.aggregate_daily_usage()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Daily aggregation failed", error=str(e))
                # Continue running even if aggregation fails
    
    async def aggregate_hourly_metrics(self):
        """Aggregate API call data into hourly metrics"""
        
        try:
            # Get the previous hour
            now = datetime.utcnow()
            previous_hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
            previous_hour_end = previous_hour_start + timedelta(hours=1)
            
            logger.info("Starting hourly aggregation", 
                       hour_start=previous_hour_start.isoformat(),
                       hour_end=previous_hour_end.isoformat())
            
            async with db_manager.get_usage_logs_session() as usage_db:
                async with db_manager.get_analytics_session() as analytics_db:
                    
                    # Get all active servers
                    servers_result = await analytics_db.execute(select(ModelServer).where(ModelServer.is_active == True))
                    servers = servers_result.scalars().all()
                    
                    for server in servers:
                        for model in server.models:
                            # Aggregate metrics for this server and model
                            query = select(
                                func.count(APICall.id).label('request_count'),
                                func.sum(APICall.total_tokens).label('total_tokens'),
                                func.avg(APICall.response_time_ms).label('avg_response_time'),
                                func.count(func.nullif(APICall.status_code, 200)).label('error_count')
                            ).where(
                                and_(
                                    APICall.timestamp >= previous_hour_start,
                                    APICall.timestamp < previous_hour_end,
                                    APICall.model == model,
                                    or_(
                                        APICall.server_endpoint == server.endpoint,
                                        APICall.server_endpoint == "litellm-router"  # Handle LiteLLM routing
                                    )
                                )
                            )
                            
                            result = await usage_db.execute(query)
                            metrics = result.first()
                            
                            if metrics and metrics.request_count > 0:
                                # Create or update hourly metrics
                                hourly_metric = HourlyMetrics(
                                    hour_timestamp=previous_hour_start,
                                    server_id=str(server.id),
                                    model=model,
                                    request_count=metrics.request_count,
                                    total_tokens=metrics.total_tokens or 0,
                                    avg_response_time=metrics.avg_response_time,
                                    error_count=metrics.error_count
                                )
                                
                                analytics_db.add(hourly_metric)
                    
                    await analytics_db.commit()
            
            logger.info("Hourly aggregation completed", 
                       hour=previous_hour_start.isoformat())
            
        except Exception as e:
            logger.error("Hourly aggregation failed", error=str(e))
            raise
    
    async def aggregate_daily_usage(self):
        """Aggregate hourly metrics into daily usage"""
        
        try:
            # Get yesterday's date
            yesterday = (datetime.utcnow() - timedelta(days=1)).date()
            
            logger.info("Starting daily aggregation", date=yesterday.isoformat())
            
            async with db_manager.get_analytics_session() as db:
                
                # Get all API keys
                api_keys_result = await db.execute(text("SELECT DISTINCT api_key_id FROM api_calls WHERE api_key_id IS NOT NULL"))
                api_key_ids = [row[0] for row in api_keys_result]
                
                # Get all models
                models_result = await db.execute(text("SELECT DISTINCT model FROM hourly_metrics"))
                models = [row[0] for row in models_result]
                
                for api_key_id in api_key_ids:
                    for model in models:
                        # Aggregate hourly metrics for this API key and model
                        query = select(
                            func.sum(HourlyMetrics.request_count).label('total_requests'),
                            func.sum(HourlyMetrics.total_tokens).label('total_tokens'),
                            func.avg(HourlyMetrics.avg_response_time).label('avg_response_time'),
                            func.sum(HourlyMetrics.error_count).label('total_errors')
                        ).where(
                            and_(
                                func.date(HourlyMetrics.hour_timestamp) == yesterday,
                                HourlyMetrics.model == model
                            )
                        )
                        
                        result = await db.execute(query)
                        daily_metrics = result.first()
                        
                        if daily_metrics and daily_metrics.total_requests > 0:
                            # Calculate error rate
                            error_rate = (daily_metrics.total_errors / daily_metrics.total_requests) if daily_metrics.total_requests > 0 else 0
                            
                            # Create or update daily usage
                            daily_usage = DailyUsage(
                                date=yesterday,
                                api_key_id=api_key_id,
                                model=model,
                                total_requests=daily_metrics.total_requests,
                                total_tokens=daily_metrics.total_tokens,
                                avg_response_time=daily_metrics.avg_response_time,
                                error_rate=error_rate
                            )
                            
                            db.add(daily_usage)
                
                await db.commit()
            
            logger.info("Daily aggregation completed", date=yesterday.isoformat())
            
        except Exception as e:
            logger.error("Daily aggregation failed", error=str(e))
            raise
    
    async def get_usage_report(
        self,
        start_date: date,
        end_date: date,
        api_key_id: Optional[str] = None,
        model: Optional[str] = None,
        group_by: str = "day"  # "day", "week", "month"
    ) -> Dict[str, Any]:
        """Generate usage report for a date range"""
        
        try:
            async with db_manager.get_analytics_session() as db:
                
                # Build base query
                query = select(
                    DailyUsage.date,
                    DailyUsage.model,
                    func.sum(DailyUsage.total_requests).label('total_requests'),
                    func.sum(DailyUsage.total_tokens).label('total_tokens'),
                    func.avg(DailyUsage.avg_response_time).label('avg_response_time'),
                    func.avg(DailyUsage.error_rate).label('avg_error_rate')
                ).where(
                    and_(
                        DailyUsage.date >= start_date,
                        DailyUsage.date <= end_date
                    )
                )
                
                # Add filters
                if api_key_id:
                    query = query.where(DailyUsage.api_key_id == api_key_id)
                if model:
                    query = query.where(DailyUsage.model == model)
                
                # Group by
                if group_by == "day":
                    query = query.group_by(DailyUsage.date, DailyUsage.model)
                elif group_by == "week":
                    # Group by ISO week
                    query = query.group_by(
                        func.date_trunc('week', DailyUsage.date),
                        DailyUsage.model
                    )
                elif group_by == "month":
                    # Group by month
                    query = query.group_by(
                        func.date_trunc('month', DailyUsage.date),
                        DailyUsage.model
                    )
                
                # Execute query
                result = await db.execute(query)
                rows = result.fetchall()
                
                # Format results
                report_data = []
                for row in rows:
                    report_data.append({
                        "date": row.date.isoformat(),
                        "model": row.model,
                        "total_requests": row.total_requests,
                        "total_tokens": row.total_tokens,
                        "avg_response_time": float(row.avg_response_time or 0),
                        "error_rate": float(row.avg_error_rate or 0)
                    })
                
                # Calculate totals
                total_requests = sum(row["total_requests"] for row in report_data)
                total_tokens = sum(row["total_tokens"] for row in report_data)
                
                report = {
                    "period": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "group_by": group_by
                    },
                    "filters": {
                        "api_key_id": api_key_id,
                        "model": model
                    },
                    "summary": {
                        "total_requests": total_requests,
                        "total_tokens": total_tokens,
                        "data_points": len(report_data)
                    },
                    "data": report_data
                }
                
                logger.info("Usage report generated", 
                           start_date=start_date.isoformat(),
                           end_date=end_date.isoformat(),
                           total_requests=total_requests)
                
                return report
                
        except Exception as e:
            logger.error("Failed to generate usage report", error=str(e))
            raise
    
    async def get_model_performance_report(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Generate model performance report"""
        
        try:
            async with db_manager.get_analytics_session() as db:
                
                # Get model performance metrics
                query = select(
                    DailyUsage.model,
                    func.sum(DailyUsage.total_requests).label('total_requests'),
                    func.sum(DailyUsage.total_tokens).label('total_tokens'),
                    func.avg(DailyUsage.avg_response_time).label('avg_response_time'),
                    func.avg(DailyUsage.error_rate).label('avg_error_rate'),
                    func.count(DailyUsage.date).label('active_days')
                ).where(
                    and_(
                        DailyUsage.date >= start_date,
                        DailyUsage.date <= end_date
                    )
                ).group_by(DailyUsage.model).order_by(
                    func.sum(DailyUsage.total_requests).desc()
                )
                
                result = await db.execute(query)
                rows = result.fetchall()
                
                # Format results
                model_data = []
                for row in rows:
                    model_data.append({
                        "model": row.model,
                        "total_requests": row.total_requests,
                        "total_tokens": row.total_tokens,
                        "avg_response_time": float(row.avg_response_time or 0),
                        "error_rate": float(row.avg_error_rate or 0),
                        "active_days": row.active_days,
                        "avg_requests_per_day": row.total_requests / row.active_days if row.active_days > 0 else 0
                    })
                
                report = {
                    "period": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    },
                    "models": model_data,
                    "summary": {
                        "total_models": len(model_data),
                        "total_requests": sum(row["total_requests"] for row in model_data),
                        "total_tokens": sum(row["total_tokens"] for row in model_data)
                    }
                }
                
                logger.info("Model performance report generated", 
                           start_date=start_date.isoformat(),
                           end_date=end_date.isoformat(),
                           total_models=len(model_data))
                
                return report
                
        except Exception as e:
            logger.error("Failed to generate model performance report", error=str(e))
            raise
    
    async def get_hourly_metrics(
        self,
        date: date,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get detailed hourly metrics for a specific date"""
        
        try:
            start_datetime = datetime.combine(date, datetime.min.time())
            end_datetime = start_datetime + timedelta(days=1)
            
            async with db_manager.get_analytics_session() as db:
                
                query = select(
                    HourlyMetrics.hour_timestamp,
                    HourlyMetrics.model,
                    HourlyMetrics.request_count,
                    HourlyMetrics.total_tokens,
                    HourlyMetrics.avg_response_time,
                    HourlyMetrics.error_count
                ).where(
                    and_(
                        HourlyMetrics.hour_timestamp >= start_datetime,
                        HourlyMetrics.hour_timestamp < end_datetime
                    )
                )
                
                if model:
                    query = query.where(HourlyMetrics.model == model)
                
                query = query.order_by(HourlyMetrics.hour_timestamp)
                
                result = await db.execute(query)
                rows = result.fetchall()
                
                # Format results
                hourly_data = []
                for row in rows:
                    hourly_data.append({
                        "hour": row.hour_timestamp.isoformat(),
                        "model": row.model,
                        "request_count": row.request_count,
                        "total_tokens": row.total_tokens,
                        "avg_response_time": float(row.avg_response_time or 0),
                        "error_count": row.error_count,
                        "error_rate": row.error_count / row.request_count if row.request_count > 0 else 0
                    })
                
                return {
                    "date": date.isoformat(),
                    "model": model,
                    "hourly_data": hourly_data,
                    "summary": {
                        "total_requests": sum(row["request_count"] for row in hourly_data),
                        "total_tokens": sum(row["total_tokens"] for row in hourly_data),
                        "total_errors": sum(row["error_count"] for row in hourly_data)
                    }
                }
                
        except Exception as e:
            logger.error("Failed to get hourly metrics", date=date.isoformat(), error=str(e))
            raise


# Global analytics engine instance
analytics_engine = AnalyticsEngine()
