# Docker Deployment Guide

This guide explains how to deploy the Gym Tracker Bot using Docker.

## Prerequisites

- Docker Engine 20.10+ ([Install Docker](https://docs.docker.com/engine/install/))
- Docker Compose v2.0+ ([Install Docker Compose](https://docs.docker.com/compose/install/))
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Your Telegram User ID from [@userinfobot](https://t.me/userinfobot)
- (Optional) Groq API key for AI features ([Get key](https://console.groq.com/keys))

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/gym-tracker-bot.git
cd gym-tracker-bot
```

### 2. Configure environment variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your values
nano .env
```

**Minimum required configuration:**

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
AUTHORIZED_USER_IDS=your_telegram_id_here
GROQ_API_KEY=your_groq_api_key_here
```

### 3. Create required directories

```bash
mkdir -p data backups logs
```

### 4. Build and run

```bash
# Build and start the bot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

## Configuration

### Environment Variables

See `.env.example` for all available configuration options. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | **Required** |
| `AUTHORIZED_USER_IDS` | Comma-separated user IDs | **Required** |
| `GROQ_API_KEY` | Groq API key for AI features | **Required** |
| `DATABASE_URL` | Database connection string | `sqlite:///data/gym_tracker.db` |
| `WHISPER_MODEL` | Whisper model for transcription | `whisper-large-v3` |
| `SESSION_TIMEOUT_HOURS` | Session timeout | `3` |

### Volume Mounts

The following directories are persisted outside the container:

- `./data` - Database files
- `./backups` - Automated backups
- `./logs` - Application logs

## Docker Commands

### Build and Start

```bash
# Build and start in detached mode
docker-compose up -d

# Build from scratch (no cache)
docker-compose build --no-cache

# Start without building
docker-compose start
```

### Logs and Monitoring

```bash
# View logs (follow mode)
docker-compose logs -f

# View last 100 lines
docker-compose logs --tail=100

# Check container status
docker-compose ps

# Check resource usage
docker stats gym-tracker-bot
```

### Stop and Restart

```bash
# Stop the bot
docker-compose stop

# Restart the bot
docker-compose restart

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes
docker-compose down -v
```

### Updates

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build
```

## Advanced Configuration

### Using PostgreSQL instead of SQLite

1. Add a PostgreSQL service to `docker-compose.yml`:

```yaml
services:
  gym-bot:
    # ... existing configuration
    environment:
      - DATABASE_URL=postgresql://gymbot:password@postgres:5432/gymtracker
    depends_on:
      - postgres

  postgres:
    image: postgres:15-alpine
    container_name: gym-tracker-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: gymbot
      POSTGRES_PASSWORD: password
      POSTGRES_DB: gymtracker
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

2. Update `.env`:

```bash
DATABASE_URL=postgresql://gymbot:password@postgres:5432/gymtracker
```

### Using Ollama (Local LLM)

If you want to use Ollama instead of Groq:

1. Install and run Ollama on your host machine
2. Update `.env`:

```bash
LLM_MODEL=llama3.1:8b
OLLAMA_HOST=http://host.docker.internal:11434
```

### Custom Port Mapping

To expose health check endpoints:

```yaml
services:
  gym-bot:
    ports:
      - "8080:8080"  # If you add HTTP health endpoints
```

## Troubleshooting

### Bot doesn't start

```bash
# Check logs for errors
docker-compose logs

# Common issues:
# 1. Missing TELEGRAM_BOT_TOKEN
# 2. Invalid AUTHORIZED_USER_IDS format
# 3. Missing GROQ_API_KEY
```

### Permission errors

```bash
# Fix directory permissions
sudo chown -R 1000:1000 data backups logs
```

### Database locked errors

```bash
# Stop the bot
docker-compose down

# Backup database
cp data/gym_tracker.db data/gym_tracker.db.backup

# Restart
docker-compose up -d
```

### Out of disk space

```bash
# Check disk usage
docker system df

# Clean up unused images and containers
docker system prune -a

# Clean up volumes (WARNING: deletes all data)
docker system prune --volumes
```

### Container keeps restarting

```bash
# Check recent logs
docker-compose logs --tail=50

# Stop auto-restart
docker-compose stop

# Start in foreground to see errors
docker-compose up
```

## Production Deployment

### Security Best Practices

1. **Use secrets management** instead of `.env` file:

```yaml
services:
  gym-bot:
    secrets:
      - telegram_token
      - groq_api_key

secrets:
  telegram_token:
    file: ./secrets/telegram_token.txt
  groq_api_key:
    file: ./secrets/groq_api_key.txt
```

2. **Enable resource limits**:

```yaml
services:
  gym-bot:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

3. **Use read-only filesystem** where possible:

```yaml
services:
  gym-bot:
    read_only: true
    tmpfs:
      - /tmp
```

### Monitoring

Add health checks and monitoring:

```yaml
services:
  gym-bot:
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Backup Strategy

```bash
# Manual backup
docker-compose exec gym-bot python -c "from src.services.backup_service import BackupService; import asyncio; asyncio.run(BackupService().create_backup())"

# Automated backups (cron job on host)
0 2 * * * cd /path/to/gym-tracker-bot && docker-compose exec -T gym-bot python -c "from src.services.backup_service import BackupService; import asyncio; asyncio.run(BackupService().create_backup())"
```

## Scaling Considerations

Current single-container setup is suitable for:
- Personal use (1-10 users)
- Low to medium traffic (< 1000 requests/day)
- SQLite database

**When to migrate to multi-container:**
- Multiple bots or services
- High traffic (> 10,000 requests/day)
- Need for separate API/web interface
- Geographic distribution

## Getting Help

- Check logs: `docker-compose logs -f`
- Verify configuration: `docker-compose config`
- Test bot token: `curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe`
- Report issues: [GitHub Issues](https://github.com/yourusername/gym-tracker-bot/issues)

## License

See [LICENSE](LICENSE) file for details.
