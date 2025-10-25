"""Health check and metrics endpoints for the bot"""

from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from bot.middleware import admin_only
from bot.rate_limiter import rate_limit_commands
from bot.validation_middleware import CommonSchemas, validate_input
from config.logging_config import get_logger
from services.async_health_service import health_service
from services.error_handler import error_handler

logger = get_logger(__name__)


@admin_only
@rate_limit_commands
@error_handler("health check command")
@validate_input(CommonSchemas.admin_command())
async def health_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, validated_data: dict = None
) -> None:
    """Comando /health - Health check básico (ADMIN ONLY)"""
    try:
        # Get simple health status
        health_status = await health_service.get_simple_health()

        status_emoji = {
            "healthy": "✅",
            "degraded": "⚠️",
            "unhealthy": "❌",
        }.get(health_status["status"], "❓")

        uptime_hours = health_status["uptime_seconds"] // 3600
        uptime_minutes = (health_status["uptime_seconds"] % 3600) // 60

        response = f"""🏥 **Health Check**

{status_emoji} **Status:** {health_status["status"].title()}
⏱️ **Uptime:** {uptime_hours}h {uptime_minutes}m
🕒 **Check Time:** {datetime.now().strftime("%H:%M:%S")}

**Quick Checks:**
💾 Database: {"✅" if health_status["checks"]["database"] == "healthy" else "❌"}
🖥️ CPU: {"✅" if health_status["checks"]["cpu_ok"] else "❌"}
💻 Memory: {"✅" if health_status["checks"]["memory_ok"] else "❌"}

Use /healthfull for detailed report."""

        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception:
        logger.exception("Error in health command")
        await update.message.reply_text(
            "❌ **Health Check Failed**\n\nUnable to perform health check.",
            parse_mode="Markdown",
        )


@admin_only
@rate_limit_commands
@error_handler("full health check command")
@validate_input(CommonSchemas.admin_command())
async def health_full_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, validated_data: dict = None
) -> None:
    """Comando /healthfull - Health check completo (ADMIN ONLY)"""
    try:
        # Show loading message
        status_msg = await update.message.reply_text(
            "🔍 **Running comprehensive health check...**",
            parse_mode="Markdown",
        )

        # Get comprehensive health status
        health_status = await health_service.get_health_status()

        # Format the response
        status_emoji = {
            "healthy": "✅",
            "degraded": "⚠️",
            "unhealthy": "❌",
        }.get(health_status.status, "❓")

        uptime_hours = health_status.uptime_seconds // 3600
        uptime_minutes = (health_status.uptime_seconds % 3600) // 60

        response = f"""🏥 **Comprehensive Health Report**

{status_emoji} **Overall Status:** {health_status.status.title()}
⏱️ **Uptime:** {uptime_hours}h {uptime_minutes}m
🕒 **Report Time:** {health_status.timestamp.strftime("%H:%M:%S")}

**🔍 System Checks:**"""

        # Add individual check results
        for check_name, check_result in health_status.checks.items():
            if isinstance(check_result, dict) and "status" in check_result:
                check_emoji = {
                    "healthy": "✅",
                    "degraded": "⚠️",
                    "unhealthy": "❌",
                }.get(check_result["status"], "❓")

                check_title = check_name.replace("_", " ").title()
                response += (
                    f"\n{check_emoji} **{check_title}:** {check_result['status']}"
                )

                if "response_time_ms" in check_result:
                    response += f" ({check_result['response_time_ms']}ms)"

                # Add warnings if any
                if check_result.get("warnings"):
                    for warning in check_result["warnings"]:
                        response += f"\n   ⚠️ {warning}"

        # Add metrics summary
        if "system" in health_status.metrics:
            system = health_status.metrics["system"]
            response += f"""

**📊 System Metrics:**
🖥️ CPU: {system['cpu_percent']:.1f}%
💻 Memory: {system['memory_percent']:.1f}% ({system['memory_used_mb']}MB/{system['memory_total_mb']}MB)
💾 Disk: {system['disk_percent']:.1f}% ({system['disk_used_gb']:.1f}GB/{system['disk_total_gb']:.1f}GB)"""

        if "database" in health_status.metrics:
            db = health_status.metrics["database"]
            response += f"""

**🗄️ Database Metrics:**
👥 Active Users: {db['total_users']}
📊 Total Sessions: {db['total_sessions']}
📅 Sessions Today: {db['sessions_today']}
⚡ Response Time: {db['response_time_ms']}ms"""

        if "bot" in health_status.metrics:
            bot = health_status.metrics["bot"]
            response += f"""

**🤖 Bot Metrics:**
🎯 Commands Processed: {bot['total_commands_processed']}
🎵 Audio Processed: {bot['total_audio_processed']}
⚡ Avg Response Time: {bot['average_response_time_ms']}ms
❌ Error Rate: {bot['error_rate_percent']}%"""

        # Update the status message
        await status_msg.edit_text(response, parse_mode="Markdown")

    except Exception:
        logger.exception("Error in full health command")
        await update.message.reply_text(
            "❌ **Health Check Failed**\n\nUnable to perform comprehensive health check.",
            parse_mode="Markdown",
        )


@admin_only
@rate_limit_commands
@error_handler("metrics command")
@validate_input(CommonSchemas.admin_command())
async def metrics_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, validated_data: dict = None
) -> None:
    """Comando /metrics - Métricas do sistema (ADMIN ONLY)"""
    try:
        # Get comprehensive health status for metrics
        health_status = await health_service.get_health_status()

        response = f"""📊 **System Metrics Report**

🕒 **Generated:** {health_status.timestamp.strftime("%H:%M:%S")}
⏱️ **Uptime:** {health_status.uptime_seconds // 3600}h {(health_status.uptime_seconds % 3600) // 60}m"""

        # System metrics
        if "system" in health_status.metrics:
            system = health_status.metrics["system"]
            response += f"""

**🖥️ System Performance:**
• CPU Usage: {system['cpu_percent']:.1f}%
• Memory Usage: {system['memory_percent']:.1f}%
• Memory: {system['memory_used_mb']:,}MB / {system['memory_total_mb']:,}MB
• Disk Usage: {system['disk_percent']:.1f}%
• Disk: {system['disk_used_gb']:.1f}GB / {system['disk_total_gb']:.1f}GB"""

        # Database metrics
        if "database" in health_status.metrics:
            db = health_status.metrics["database"]
            response += f"""

**🗄️ Database Stats:**
• Status: {db['connection_status']}
• Response Time: {db['response_time_ms']}ms
• Total Users: {db['total_users']:,}
• Total Sessions: {db['total_sessions']:,}
• Sessions Today: {db['sessions_today']:,}"""

        # Bot metrics
        if "bot" in health_status.metrics:
            bot = health_status.metrics["bot"]
            response += f"""

**🤖 Bot Performance:**
• Commands Processed: {bot['total_commands_processed']:,}
• Audio Files Processed: {bot['total_audio_processed']:,}
• Average Response Time: {bot['average_response_time_ms']:.1f}ms
• Error Rate: {bot['error_rate_percent']:.2f}%
• Active Sessions: {bot['active_sessions']:,}"""

        # Performance indicators
        response += """

**🎯 Performance Indicators:**"""

        # CPU status
        if "system" in health_status.metrics:
            cpu = health_status.metrics["system"]["cpu_percent"]
            cpu_status = (
                "🟢 Good" if cpu < 50 else "🟡 Moderate" if cpu < 80 else "🔴 High"
            )
            response += f"\n• CPU Load: {cpu_status}"

            # Memory status
            mem = health_status.metrics["system"]["memory_percent"]
            mem_status = (
                "🟢 Good" if mem < 50 else "🟡 Moderate" if mem < 80 else "🔴 High"
            )
            response += f"\n• Memory Usage: {mem_status}"

        # Database performance
        if "database" in health_status.metrics:
            db_time = health_status.metrics["database"]["response_time_ms"]
            db_status = (
                "🟢 Fast"
                if db_time < 50
                else "🟡 Moderate" if db_time < 200 else "🔴 Slow"
            )
            response += f"\n• Database Speed: {db_status}"

        # Bot performance
        if "bot" in health_status.metrics:
            error_rate = health_status.metrics["bot"]["error_rate_percent"]
            error_status = (
                "🟢 Low"
                if error_rate < 1
                else "🟡 Moderate" if error_rate < 5 else "🔴 High"
            )
            response += f"\n• Error Rate: {error_status}"

        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception:
        logger.exception("Error in metrics command")
        await update.message.reply_text(
            "❌ **Metrics Failed**\n\nUnable to collect system metrics.",
            parse_mode="Markdown",
        )


@admin_only
@rate_limit_commands
@error_handler("performance command")
@validate_input(CommonSchemas.admin_command())
async def performance_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, validated_data: dict = None
) -> None:
    """Comando /performance - Performance monitoring (ADMIN ONLY)"""
    try:
        # Get bot metrics
        bot_metrics = await health_service._get_bot_metrics_async()
        system_metrics = health_service._get_system_metrics()

        # Performance recommendations
        recommendations = []

        if system_metrics.cpu_percent > 80:
            recommendations.append("🔴 High CPU usage detected - consider optimization")
        elif system_metrics.cpu_percent > 60:
            recommendations.append("🟡 Moderate CPU usage - monitor closely")

        if system_metrics.memory_percent > 80:
            recommendations.append("🔴 High memory usage - consider cleanup")
        elif system_metrics.memory_percent > 60:
            recommendations.append("🟡 Moderate memory usage - monitor closely")

        if bot_metrics.error_rate_percent > 5:
            recommendations.append("🔴 High error rate - investigate issues")
        elif bot_metrics.error_rate_percent > 1:
            recommendations.append("🟡 Elevated error rate - monitor closely")

        if bot_metrics.average_response_time_ms > 2000:
            recommendations.append("🔴 Slow response times - optimize handlers")
        elif bot_metrics.average_response_time_ms > 1000:
            recommendations.append("🟡 Moderate response times - consider optimization")

        if not recommendations:
            recommendations.append(
                "🟢 All performance metrics are within normal ranges"
            )

        response = f"""⚡ **Performance Report**

**📈 Current Performance:**
• Average Response Time: {bot_metrics.average_response_time_ms:.1f}ms
• Error Rate: {bot_metrics.error_rate_percent:.2f}%
• CPU Usage: {system_metrics.cpu_percent:.1f}%
• Memory Usage: {system_metrics.memory_percent:.1f}%

**📊 Processing Stats:**
• Total Commands: {bot_metrics.total_commands_processed:,}
• Total Audio: {bot_metrics.total_audio_processed:,}

**💡 Recommendations:**
{chr(10).join(f"• {rec}" for rec in recommendations)}

**🎯 Performance Targets:**
• Response Time: < 1000ms (Current: {bot_metrics.average_response_time_ms:.1f}ms)
• Error Rate: < 1% (Current: {bot_metrics.error_rate_percent:.2f}%)
• CPU Usage: < 60% (Current: {system_metrics.cpu_percent:.1f}%)
• Memory Usage: < 60% (Current: {system_metrics.memory_percent:.1f}%)"""

        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception:
        logger.exception("Error in performance command")
        await update.message.reply_text(
            "❌ **Performance Report Failed**\n\nUnable to generate performance report.",
            parse_mode="Markdown",
        )
