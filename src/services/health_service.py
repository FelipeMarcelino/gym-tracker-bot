"""Health check and monitoring service"""

import time
import psutil
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from config.logging_config import get_logger
from config.settings import settings
# Removed: from database.connection import db - now using async connections
from database.async_connection import async_db
from services.exceptions import DatabaseError, ErrorCode

logger = get_logger(__name__)


@dataclass
class HealthStatus:
    """Health status data class"""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    uptime_seconds: int
    checks: Dict[str, Any]
    metrics: Dict[str, Any]


@dataclass
class SystemMetrics:
    """System performance metrics"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float


@dataclass
class DatabaseMetrics:
    """Database performance metrics"""
    connection_status: str
    response_time_ms: float
    active_connections: int
    total_users: int
    total_sessions: int
    sessions_today: int


@dataclass
class BotMetrics:
    """Bot-specific metrics"""
    total_commands_processed: int
    total_audio_processed: int
    average_response_time_ms: float
    error_rate_percent: float
    active_sessions: int


class HealthService:
    """Service for health checks and metrics collection"""
    
    def __init__(self):
        self.start_time = time.time()
        self.command_count = 0
        self.audio_count = 0
        self.error_count = 0
        self.response_times = []
        self.max_response_times = 1000  # Keep last 1000 response times
    
    def record_command(self, response_time_ms: float, is_error: bool = False):
        """Record a command execution"""
        self.command_count += 1
        self.response_times.append(response_time_ms)
        
        # Keep only recent response times
        if len(self.response_times) > self.max_response_times:
            self.response_times = self.response_times[-self.max_response_times:]
        
        if is_error:
            self.error_count += 1
    
    def record_audio_processing(self, response_time_ms: float, is_error: bool = False):
        """Record audio processing"""
        self.audio_count += 1
        self.response_times.append(response_time_ms)
        
        # Keep only recent response times
        if len(self.response_times) > self.max_response_times:
            self.response_times = self.response_times[-self.max_response_times:]
        
        if is_error:
            self.error_count += 1
    
    async def get_health_status(self) -> HealthStatus:
        """Get comprehensive health status"""
        try:
            start_time = time.time()
            
            # Run all health checks
            checks = await self._run_health_checks()
            
            # Collect metrics
            metrics = await self._collect_metrics()
            
            # Determine overall status
            overall_status = self._determine_overall_status(checks)
            
            # Calculate uptime
            uptime = int(time.time() - self.start_time)
            
            health_status = HealthStatus(
                status=overall_status,
                timestamp=datetime.now(),
                uptime_seconds=uptime,
                checks=checks,
                metrics=metrics
            )
            
            check_time = (time.time() - start_time) * 1000
            logger.debug(f"Health check completed in {check_time:.2f}ms")
            
            return health_status
            
        except Exception as e:
            logger.exception("Error during health check")
            return HealthStatus(
                status="unhealthy",
                timestamp=datetime.now(),
                uptime_seconds=int(time.time() - self.start_time),
                checks={"health_check_error": str(e)},
                metrics={}
            )
    
    async def _run_health_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        checks = {}
        
        # Database connectivity check
        checks["database"] = await self._check_database()
        
        # Async database check
        checks["async_database"] = await self._check_async_database()
        
        # System resources check
        checks["system_resources"] = self._check_system_resources()
        
        # Configuration check
        checks["configuration"] = self._check_configuration()
        
        # Dependencies check
        checks["dependencies"] = self._check_dependencies()
        
        return checks
    
    async def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = time.time()
            
            # Test database connection
            from database.async_connection import get_async_session_context
            from sqlalchemy import text
            
            async with get_async_session_context() as session:
                # Simple query to test connectivity
                result = await session.execute(text("SELECT 1"))
                value = result.scalar()
                
                response_time = (time.time() - start_time) * 1000
                
            return {
                "status": "healthy" if value else "unhealthy",
                "response_time_ms": round(response_time, 2),
                "message": "Database connection successful"
            }
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.exception("Database health check failed")
            return {
                "status": "unhealthy",
                "response_time_ms": round(response_time, 2),
                "message": f"Database connection failed: {str(e)}"
            }
    
    async def _check_async_database(self) -> Dict[str, Any]:
        """Check async database connectivity"""
        try:
            start_time = time.time()
            
            # Test async database connection
            from database.async_connection import get_async_session_context
            from sqlalchemy import text
            
            async with get_async_session_context() as session:
                result = await session.execute(text("SELECT 1"))
                value = result.scalar()
                
                response_time = (time.time() - start_time) * 1000
                
                return {
                    "status": "healthy" if value == 1 else "unhealthy",
                    "response_time_ms": round(response_time, 2),
                    "message": "Async database connection successful"
                }
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.exception("Async database health check failed")
            return {
                "status": "unhealthy",
                "response_time_ms": round(response_time, 2),
                "message": f"Async database connection failed: {str(e)}"
            }
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Determine status based on thresholds
            status = "healthy"
            warnings = []
            
            if cpu_percent > 80:
                status = "degraded"
                warnings.append(f"High CPU usage: {cpu_percent}%")
            
            if memory.percent > 80:
                status = "degraded"
                warnings.append(f"High memory usage: {memory.percent}%")
            
            if disk.percent > 90:
                status = "degraded"
                warnings.append(f"High disk usage: {disk.percent}%")
            
            return {
                "status": status,
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "warnings": warnings,
                "message": "System resources checked"
            }
            
        except Exception as e:
            logger.exception("System resources check failed")
            return {
                "status": "unhealthy",
                "message": f"System resources check failed: {str(e)}"
            }
    
    def _check_configuration(self) -> Dict[str, Any]:
        """Check critical configuration"""
        try:
            issues = []
            
            # Check critical settings
            if not settings.TELEGRAM_BOT_TOKEN:
                issues.append("TELEGRAM_BOT_TOKEN not configured")
            
            if not settings.DATABASE_URL:
                issues.append("DATABASE_URL not configured")
            
            # Check optional but important settings
            warnings = []
            if not settings.GROQ_API_KEY:
                warnings.append("GROQ_API_KEY not configured")
            
            status = "unhealthy" if issues else ("degraded" if warnings else "healthy")
            
            return {
                "status": status,
                "issues": issues,
                "warnings": warnings,
                "message": "Configuration checked"
            }
            
        except Exception as e:
            logger.exception("Configuration check failed")
            return {
                "status": "unhealthy",
                "message": f"Configuration check failed: {str(e)}"
            }
    
    def _check_dependencies(self) -> Dict[str, Any]:
        """Check external dependencies"""
        try:
            import aiosqlite
            import sqlalchemy
            import telegram
            
            # Check versions if needed
            versions = {
                "aiosqlite": getattr(aiosqlite, "__version__", "unknown"),
                "sqlalchemy": sqlalchemy.__version__,
                "python-telegram-bot": telegram.__version__
            }
            
            return {
                "status": "healthy",
                "versions": versions,
                "message": "Dependencies checked"
            }
            
        except ImportError as e:
            return {
                "status": "unhealthy",
                "message": f"Missing dependency: {str(e)}"
            }
        except Exception as e:
            logger.exception("Dependencies check failed")
            return {
                "status": "unhealthy",
                "message": f"Dependencies check failed: {str(e)}"
            }
    
    async def _collect_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive metrics"""
        try:
            metrics = {}
            
            # System metrics
            metrics["system"] = asdict(self._get_system_metrics())
            
            # Database metrics
            metrics["database"] = asdict(await self._get_database_metrics())
            
            # Bot metrics
            metrics["bot"] = asdict(self._get_bot_metrics())
            
            return metrics
            
        except Exception as e:
            logger.exception("Error collecting metrics")
            return {"error": f"Metrics collection failed: {str(e)}"}
    
    def _get_system_metrics(self) -> SystemMetrics:
        """Get system performance metrics"""
        # CPU
        cpu_percent = psutil.cpu_percent()
        
        # Memory
        memory = psutil.virtual_memory()
        memory_used_mb = memory.used / (1024 * 1024)
        memory_total_mb = memory.total / (1024 * 1024)
        
        # Disk
        disk = psutil.disk_usage('/')
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_total_gb = disk.total / (1024 * 1024 * 1024)
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=round(memory_used_mb),
            memory_total_mb=round(memory_total_mb),
            disk_percent=disk.percent,
            disk_used_gb=round(disk_used_gb, 2),
            disk_total_gb=round(disk_total_gb, 2)
        )
    
    async def _get_database_metrics(self) -> DatabaseMetrics:
        """Get database performance metrics"""
        try:
            start_time = time.time()
            
            # Test database response time
            from database.async_connection import get_async_session_context
            from database.models import User, WorkoutSession
            from sqlalchemy import select, func
            
            async with get_async_session_context() as session:
                # Query some basic stats
                user_count_stmt = select(func.count(User.user_id)).where(User.is_active == True)
                user_result = await session.execute(user_count_stmt)
                user_count = user_result.scalar()
                
                session_count_stmt = select(func.count(WorkoutSession.session_id))
                session_result = await session.execute(session_count_stmt)
                total_sessions = session_result.scalar()
                
                # Sessions today
                today = datetime.now().date()
                sessions_today_stmt = select(func.count(WorkoutSession.session_id)).where(
                    WorkoutSession.date == today
                )
                today_result = await session.execute(sessions_today_stmt)
                sessions_today = today_result.scalar()
                
                response_time = (time.time() - start_time) * 1000
                
            return DatabaseMetrics(
                connection_status="connected",
                response_time_ms=round(response_time, 2),
                active_connections=1,  # SQLite doesn't have connection pooling
                total_users=user_count,
                total_sessions=total_sessions,
                sessions_today=sessions_today
            )
                
        except Exception as e:
            logger.exception("Error getting database metrics")
            return DatabaseMetrics(
                connection_status="error",
                response_time_ms=0,
                active_connections=0,
                total_users=0,
                total_sessions=0,
                sessions_today=0
            )
    
    def _get_bot_metrics(self) -> BotMetrics:
        """Get bot-specific metrics"""
        # Calculate average response time
        avg_response_time = (
            sum(self.response_times) / len(self.response_times)
            if self.response_times else 0
        )
        
        # Calculate error rate
        total_operations = self.command_count + self.audio_count
        error_rate = (
            (self.error_count / total_operations * 100)
            if total_operations > 0 else 0
        )
        
        return BotMetrics(
            total_commands_processed=self.command_count,
            total_audio_processed=self.audio_count,
            average_response_time_ms=round(avg_response_time, 2),
            error_rate_percent=round(error_rate, 2),
            active_sessions=0  # Would need to implement session tracking
        )
    
    def _determine_overall_status(self, checks: Dict[str, Any]) -> str:
        """Determine overall health status from individual checks"""
        statuses = []
        
        for check_name, check_result in checks.items():
            if isinstance(check_result, dict) and "status" in check_result:
                statuses.append(check_result["status"])
        
        # If any check is unhealthy, overall is unhealthy
        if "unhealthy" in statuses:
            return "unhealthy"
        
        # If any check is degraded, overall is degraded
        if "degraded" in statuses:
            return "degraded"
        
        # Otherwise, healthy
        return "healthy"
    
    async def get_simple_health(self) -> Dict[str, Any]:
        """Get simple health status for quick checks"""
        try:
            # Quick system check
            cpu = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            # Quick database check
            try:
                from database.async_connection import get_async_session_context
                from sqlalchemy import text
                async with get_async_session_context() as session:
                    await session.execute(text("SELECT 1"))
                db_status = "healthy"
            except:
                db_status = "unhealthy"
            
            uptime = int(time.time() - self.start_time)
            
            status = "healthy"
            if cpu > 90 or memory.percent > 90 or db_status == "unhealthy":
                status = "unhealthy"
            elif cpu > 80 or memory.percent > 80:
                status = "degraded"
            
            return {
                "status": status,
                "uptime_seconds": uptime,
                "timestamp": datetime.now().isoformat(),
                "checks": {
                    "database": db_status,
                    "cpu_ok": cpu < 80,
                    "memory_ok": memory.percent < 80
                }
            }
            
        except Exception as e:
            logger.exception("Simple health check failed")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Global health service instance
health_service = HealthService()