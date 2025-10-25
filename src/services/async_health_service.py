"""Health check and monitoring service"""

import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional

import psutil
from pydantic import BaseModel, Field, ConfigDict

from config.logging_config import get_logger
from config.settings import settings

logger = get_logger(__name__)


class HealthStatus(BaseModel):
    """Health status data model"""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}, validate_assignment=True
    )

    status: str = Field(
        ...,
        pattern="^(healthy|degraded|unhealthy)$",
        description="Overall health status",
    )
    timestamp: datetime = Field(..., description="Timestamp of health check")
    uptime_seconds: int = Field(..., ge=0, description="System uptime in seconds")
    checks: Dict[str, Any] = Field(
        default_factory=dict, description="Individual health check results"
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict, description="System and application metrics"
    )


class SystemMetrics(BaseModel):
    """System performance metrics"""

    model_config = ConfigDict(validate_assignment=True)

    cpu_percent: float = Field(..., ge=0, le=100, description="CPU usage percentage")
    memory_percent: float = Field(
        ..., ge=0, le=100, description="Memory usage percentage"
    )
    memory_used_mb: float = Field(..., ge=0, description="Memory used in MB")
    memory_total_mb: float = Field(..., ge=0, description="Total memory in MB")
    disk_percent: float = Field(..., ge=0, le=100, description="Disk usage percentage")
    disk_used_gb: float = Field(..., ge=0, description="Disk used in GB")
    disk_total_gb: float = Field(..., ge=0, description="Total disk space in GB")


class DatabaseMetrics(BaseModel):
    """Database performance metrics"""

    model_config = ConfigDict(validate_assignment=True)

    connection_status: str = Field(
        ...,
        pattern="^(connected|disconnected|error)$",
        description="Database connection status",
    )
    response_time_ms: float = Field(
        ..., ge=0, description="Database response time in milliseconds"
    )
    active_connections: int = Field(
        ..., ge=0, description="Number of active database connections"
    )
    total_users: int = Field(..., ge=0, description="Total number of users in database")
    total_sessions: int = Field(
        ..., ge=0, description="Total number of workout sessions"
    )
    sessions_today: int = Field(
        ..., ge=0, description="Number of sessions created today"
    )


class BotMetrics(BaseModel):
    """Bot-specific metrics"""

    model_config = ConfigDict(validate_assignment=True)

    total_commands_processed: int = Field(
        ..., ge=0, description="Total commands processed by bot"
    )
    total_audio_processed: int = Field(
        ..., ge=0, description="Total audio files processed"
    )
    average_response_time_ms: float = Field(
        ..., ge=0, description="Average response time in milliseconds"
    )
    percentile_response_time_ms: float = Field(
        ..., ge=0, description="95th percentile response time in milliseconds"
    )
    error_rate_percent: float = Field(
        ..., ge=0, le=100, description="Error rate percentage"
    )
    active_sessions: int = Field(
        ..., ge=0, description="Number of active workout sessions"
    )


class HealthService:
    """Service for health checks and metrics collection"""

    def __init__(self):
        self.start_time = time.time()
        self.command_count = 0
        self.audio_count = 0
        self.error_count = 0
        self.response_times = []
        self.max_response_times = 1000  # Keep last 1000 response times
        self.response_times = deque(maxlen=self.max_response_times)
        self._metrics_lock = threading.RLock()
        self._response_time_sum = 0.0
        self._response_time_count = 0

    def record_command(self, response_time_ms: float, is_error: bool = False):
        with self._metrics_lock:
            self.command_count += 1

            # Sanitize response time to ensure it's non-negative
            sanitized_time = max(0.0, response_time_ms)

            old_value = None
            if len(self.response_times) == self.max_response_times:
                old_value = self.response_times[0]

            self.response_times.append(sanitized_time)

            self._response_time_sum += sanitized_time
            if old_value is not None:
                self._response_time_sum -= old_value
            self._response_time_count = len(self.response_times)

            if is_error:
                self.error_count += 1

    def get_average_response_time(self) -> float:
        """Get average with O(1) complexity"""
        with self._metrics_lock:
            if self._response_time_count == 0:
                return 0.0
            # O(1) em vez de O(n) como era antes
            return self._response_time_sum / self._response_time_count

    def get_percentile_response_time(self, percentile: float = 0.95) -> float:
        """Get percentile with optimized sorting"""
        with self._metrics_lock:
            if not self.response_times:
                return 0.0

            # Cópia shallow apenas quando necessário
            sorted_times = sorted(self.response_times)
            index = int(len(sorted_times) * percentile)
            return sorted_times[min(index, len(sorted_times) - 1)]

    def record_audio_processing(self, response_time_ms: float, is_error: bool = False):
        """Record audio processing"""
        with self._metrics_lock:
            self.audio_count += 1

            # Sanitize response time to ensure it's non-negative
            sanitized_time = max(0.0, response_time_ms)

            old_value = None
            if len(self.response_times) == self.max_response_times:
                old_value = self.response_times[0]

            self.response_times.append(sanitized_time)

            self._response_time_sum += sanitized_time
            if old_value is not None:
                self._response_time_sum -= old_value
            self._response_time_count = len(self.response_times)

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
                metrics=metrics,
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
                metrics={},
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
            from sqlalchemy import text

            from database.async_connection import get_async_session_context

            async with get_async_session_context() as session:
                # Simple query to test connectivity
                result = await session.execute(text("SELECT 1"))
                value = result.scalar()

                response_time = (time.time() - start_time) * 1000

            return {
                "status": "healthy" if value else "unhealthy",
                "response_time_ms": round(response_time, 2),
                "message": "Database connection successful",
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.exception("Database health check failed")
            return {
                "status": "unhealthy",
                "response_time_ms": round(response_time, 2),
                "message": f"Database connection failed: {e!s}",
            }

    async def _check_async_database(self) -> Dict[str, Any]:
        """Check async database connectivity"""
        try:
            start_time = time.time()

            # Test async database connection
            from sqlalchemy import text

            from database.async_connection import get_async_session_context

            async with get_async_session_context() as session:
                result = await session.execute(text("SELECT 1"))
                value = result.scalar()

                response_time = (time.time() - start_time) * 1000

                return {
                    "status": "healthy" if value == 1 else "unhealthy",
                    "response_time_ms": round(response_time, 2),
                    "message": "Async database connection successful",
                }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.exception("Async database health check failed")
            return {
                "status": "unhealthy",
                "response_time_ms": round(response_time, 2),
                "message": f"Async database connection failed: {e!s}",
            }

    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()

            # Disk usage
            disk = psutil.disk_usage("/")

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
                "message": "System resources checked",
            }

        except Exception as e:
            logger.exception("System resources check failed")
            return {
                "status": "unhealthy",
                "message": f"System resources check failed: {e!s}",
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
                "message": "Configuration checked",
            }

        except Exception as e:
            logger.exception("Configuration check failed")
            return {
                "status": "unhealthy",
                "message": f"Configuration check failed: {e!s}",
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
                "python-telegram-bot": telegram.__version__,
            }

            return {
                "status": "healthy",
                "versions": versions,
                "message": "Dependencies checked",
            }

        except ImportError as e:
            return {
                "status": "unhealthy",
                "message": f"Missing dependency: {e!s}",
            }
        except Exception as e:
            logger.exception("Dependencies check failed")
            return {
                "status": "unhealthy",
                "message": f"Dependencies check failed: {e!s}",
            }

    async def _collect_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive metrics"""
        try:
            metrics = {}

            # System metrics
            metrics["system"] = self._get_system_metrics().model_dump()

            # Database metrics
            metrics["database"] = (await self._get_database_metrics()).model_dump()

            # Bot metrics (async version to get active sessions)
            metrics["bot"] = (await self._get_bot_metrics_async()).model_dump()

            return metrics

        except Exception as e:
            logger.exception("Error collecting metrics")
            return {"error": f"Metrics collection failed: {e!s}"}

    def _get_system_metrics(self) -> SystemMetrics:
        """Get system performance metrics"""
        # CPU
        cpu_percent = psutil.cpu_percent()

        # Memory
        memory = psutil.virtual_memory()
        memory_used_mb = memory.used / (1024 * 1024)
        memory_total_mb = memory.total / (1024 * 1024)

        # Disk
        disk = psutil.disk_usage("/")
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_total_gb = disk.total / (1024 * 1024 * 1024)

        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=round(memory_used_mb),
            memory_total_mb=round(memory_total_mb),
            disk_percent=disk.percent,
            disk_used_gb=round(disk_used_gb, 2),
            disk_total_gb=round(disk_total_gb, 2),
        )

    async def _get_database_metrics(self) -> DatabaseMetrics:
        """Get database performance metrics"""
        try:
            start_time = time.time()

            # Test database response time
            from sqlalchemy import func, select

            from database.async_connection import get_async_session_context
            from database.models import User, WorkoutSession

            async with get_async_session_context() as session:
                # Query some basic stats
                user_count_stmt = select(func.count(User.user_id)).where(
                    User.is_active == True
                )
                user_result = await session.execute(user_count_stmt)
                user_count = user_result.scalar()

                session_count_stmt = select(func.count(WorkoutSession.session_id))
                session_result = await session.execute(session_count_stmt)
                total_sessions = session_result.scalar()

                # Sessions today
                today = datetime.now().date()
                sessions_today_stmt = select(
                    func.count(WorkoutSession.session_id)
                ).where(
                    WorkoutSession.date == today,
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
                sessions_today=sessions_today,
            )

        except Exception:
            logger.exception("Error getting database metrics")
            return DatabaseMetrics(
                connection_status="error",
                response_time_ms=0,
                active_connections=0,
                total_users=0,
                total_sessions=0,
                sessions_today=0,
            )

    async def _get_bot_metrics_async(self) -> BotMetrics:
        """Get bot-specific metrics with async database queries"""
        # Calculate average response time
        avg_response_time = self.get_average_response_time()

        # Calculate error rate
        total_operations = self.command_count + self.audio_count
        error_rate = (
            (self.error_count / total_operations * 100) if total_operations > 0 else 0
        )

        # Get active sessions count from database
        active_sessions_count = await self._get_active_sessions_count()

        return BotMetrics(
            total_commands_processed=self.command_count,
            total_audio_processed=self.audio_count,
            average_response_time_ms=round(avg_response_time, 2),
            percentile_response_time_ms=self.get_percentile_response_time(),
            error_rate_percent=round(error_rate, 2),
            active_sessions=active_sessions_count,
        )

    async def _get_active_sessions_count(self) -> int:
        """Get count of active workout sessions"""
        try:
            from sqlalchemy import func, select

            from database.async_connection import get_async_session_context
            from database.models import SessionStatus, WorkoutSession

            async with get_async_session_context() as session:
                # Count sessions with status 'ativa' (active)
                active_sessions_stmt = select(
                    func.count(WorkoutSession.session_id)
                ).where(
                    WorkoutSession.status == SessionStatus.ATIVA,
                )
                result = await session.execute(active_sessions_stmt)
                count = result.scalar()
                return count or 0

        except Exception:
            logger.exception("Error getting active sessions count")
            return 0

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
                from sqlalchemy import text

                from database.async_connection import get_async_session_context

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
                    "memory_ok": memory.percent < 80,
                },
            }

        except Exception as e:
            logger.exception("Simple health check failed")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }


# Global health service instance
health_service = HealthService()
