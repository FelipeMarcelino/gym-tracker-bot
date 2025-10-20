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
    print("=" * 60)
    print("👤 BASIC USER COMMANDS (Shown to all users)")
    print("=" * 60)
    print("   /start - Initialize bot")
    print("   /help - Show help message (role-based)")
    print("   /myid - View your Telegram ID")
    print("   /status - Check current workout session")
    print("   /finish - Finish current workout session")
    print("   /stats [days] - View workout statistics")
    print("   /progress <exercise> - View exercise progress")
    print("   /exercises - List all exercises")
    print("   /export [json|csv] - Export your workout data")
    print()
    print("=" * 60)
    print("👑 ADMIN COMMANDS (Only visible to admins in /help)")
    print("=" * 60)
    print()
    print("🔐 User Management:")
    print("   /adduser <user_id> [admin] - Add user")
    print("   /removeuser <user_id> - Remove user")
    print("   /listusers - List all users")
    print()
    print("⚡ Rate Limiting:")
    print("   /ratelimit_cleanup - Clean up inactive rate limiters")
    print("   /ratelimit_stats - Show rate limit statistics")
    print()
    print("🔧 Health & Monitoring:")
    print("   /health - Basic system health")
    print("   /healthfull - Comprehensive health check")
    print("   /metrics - Performance metrics")
    print("   /performance - Performance analysis")
    print()
    print("💾 Backup & Restore:")
    print("   /backup_create - Create manual backup")
    print("   /backup_list - List available backups")
    print("   /backup_stats - Show backup statistics")
    print("   /backup_cleanup - Clean old backups")
    print("   /backup_auto_start - Start automated backups")
    print("   /backup_auto_stop - Stop automated backups")
    print("   /backup_restore <file> confirm - Restore from backup")
    print()
    print("=" * 60)
    print("⚠️  IMPORTANT NOTES")
    print("=" * 60)
    print("   • Regular users only see basic commands in /help")
    print("   • Admins see ALL commands in /help")
    print("   • Admin commands are protected and require admin privileges")
    print("   • Use /backup_restore with EXTREME caution!")
    print("   • Automated backups run every 24 hours by default")
    print()
    print("🎯 Quick Start:")
    print("   1. Send /start in Telegram to initialize")
    print("   2. Send /help to see commands (based on your role)")
    print("   3. Start recording workouts via audio or text!")
    print()
    print("-" * 60)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting bot: {e}")
        sys.exit(1)