#!/usr/bin/env python3
"""
Simple script to run the Gym Tracker Bot

Usage:
    python run_bot.py

Make sure you have:
1. Set up your .env file with TELEGRAM_BOT_TOKEN
2. Run the migration: python src/migrate_admin.py
3. Install dependencies: pip install -r requirements.txt
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main import main

if __name__ == "__main__":
    print("🚀 Starting Gym Tracker Bot...")
    print("📝 Available commands after starting:")
    print()
    print("👤 **User Commands:**")
    print("   /start - Initialize bot")
    print("   /help - Show help message")
    print("   /status - Check workout status")
    print("   /stats - View workout statistics")
    print("   /exercises - List all exercises")
    print()
    print("🔧 **Health & Metrics Commands (Admin only):**")
    print("   /health - Basic system health")
    print("   /healthfull - Comprehensive health check")
    print("   /metrics - Performance metrics")
    print("   /performance - Performance analysis")
    print()
    print("💾 **Backup Commands (Admin only):**")
    print("   /backup_create - Create manual backup")
    print("   /backup_list - List available backups")
    print("   /backup_stats - Show backup statistics")
    print("   /backup_cleanup - Clean old backups")
    print("   /backup_auto_start - Start automated backups")
    print("   /backup_auto_stop - Stop automated backups")
    print("   /backup_restore <filename> confirm - Restore from backup")
    print()
    print("👑 **Admin Commands:**")
    print("   /adduser <user_id> [admin] - Add user")
    print("   /removeuser <user_id> - Remove user")
    print("   /listusers - List all users")
    print("   /ratelimit_cleanup - Clean up inactive rate limiters")
    print("   /ratelimit_stats - Show rate limit statistics")
    print()
    print("⚠️  **Important Notes:**")
    print("   • Health and backup commands require admin privileges")
    print("   • Use /backup_restore with EXTREME caution - it replaces the database")
    print("   • Backup commands are safe for daily use")
    print("   • Health commands help monitor system performance")
    print()
    print("🎯 **To test the commands:**")
    print("   1. Start the bot by running this script")
    print("   2. Open Telegram and find your bot")
    print("   3. Send /health to check system status")
    print("   4. Send /backup_create to create a backup")
    print("   5. Send /metrics to see performance data")
    print()
    print("-" * 60)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting bot: {e}")
        sys.exit(1)