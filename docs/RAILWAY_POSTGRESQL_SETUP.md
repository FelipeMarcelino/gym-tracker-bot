# 🚂 Railway PostgreSQL Setup Guide

Este guia mostra como configurar PostgreSQL no Railway para o Gym Tracker Bot.

## 📋 Pré-requisitos

- Conta no [Railway](https://railway.app)
- Python com as dependências instaladas (`pip install -r requirements.txt`)

## 🚀 Passo a Passo

### 1. Criar PostgreSQL no Railway

1. Acesse [Railway.app](https://railway.app) e faça login
2. Clique em **"New Project"**
3. Selecione **"Deploy PostgreSQL"**
4. O Railway criará automaticamente um banco PostgreSQL

### 2. Obter Credenciais

1. Clique no serviço PostgreSQL criado
2. Vá em **"Variables"** ou **"Connect"**
3. Copie a variável `DATABASE_URL` (será algo como: `postgresql://postgres:senha@host.railway.app:5432/railway`)

### 3. Configurar Variáveis no Railway

No seu projeto Railway, adicione as seguintes variáveis de ambiente:

```bash
# Banco de Dados (copiada do PostgreSQL)
DATABASE_URL=postgresql://postgres:senha@host.railway.app:5432/railway

# Bot do Telegram
TELEGRAM_BOT_TOKEN=seu_token_do_bot

# Usuários Autorizados (IDs separados por vírgula)
AUTHORIZED_USER_IDS=123456789,987654321

# API Groq para LLM
GROQ_API_KEY=sua_chave_groq

# Modelo LLM (opcional)
LLM_MODEL=llama-3.2-90b-text-preview
```

### 4. Testar Conexão Localmente

Para testar a conexão com o PostgreSQL do Railway localmente:

```bash
# Exportar a DATABASE_URL
export DATABASE_URL="postgresql://postgres:senha@host.railway.app:5432/railway"

# Testar conexão
python scripts/test_postgresql_connection.py
```

Você deve ver:
```
✅ Connected to PostgreSQL!
✅ Tables created successfully!
```

### 5. Migrar Dados (Opcional)

Se você já tem dados no SQLite:

```bash
# Exportar DATABASE_URL do PostgreSQL
export DATABASE_URL="postgresql://postgres:senha@host.railway.app:5432/railway"

# Executar migração
python scripts/migrate_to_postgresql.py --sqlite-path gym_tracker.db
```

### 6. Deploy no Railway

#### Opção A: Deploy via GitHub

1. Conecte seu repositório GitHub ao Railway
2. O Railway detectará automaticamente as mudanças
3. O deploy será feito automaticamente

#### Opção B: Deploy via CLI

```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link ao projeto
railway link

# Deploy
railway up
```

## 🔧 Configurações Importantes

### Pool de Conexões

O código já está configurado para usar pool de conexões otimizado para PostgreSQL:

```python
# Em async_connection.py
pool_size=10,          # 10 conexões no pool
max_overflow=20,       # Até 20 conexões adicionais
pool_recycle=3600,     # Recicla conexões após 1 hora
pool_timeout=30,       # Timeout de 30s para obter conexão
```

### Tipos de Dados

Os modelos já estão compatíveis com PostgreSQL:
- ✅ JSON columns para arrays (`reps`, `weights_kg`)
- ✅ ENUMs para tipos (`ExerciseType`, `SessionStatus`)
- ✅ Timestamps com timezone
- ✅ Foreign keys com CASCADE

## 🐛 Troubleshooting

### Erro: "asyncpg not found"

```bash
pip install asyncpg
```

### Erro: "Authentication failed"

- Verifique se copiou corretamente a `DATABASE_URL`
- No Railway, vá em PostgreSQL > Variables > DATABASE_URL

### Erro: "Connection timeout"

- Verifique se o serviço PostgreSQL está ativo no Railway
- Tente aumentar o `pool_timeout` em `async_connection.py`

### Performance Lenta

1. No Railway, vá em PostgreSQL > Settings
2. Aumente os recursos (RAM/CPU) se necessário
3. Considere adicionar índices:

```sql
-- Índices recomendados
CREATE INDEX idx_workout_sessions_user_id ON workout_sessions(user_id);
CREATE INDEX idx_workout_sessions_date ON workout_sessions(date);
CREATE INDEX idx_workout_sessions_status ON workout_sessions(status);
CREATE INDEX idx_exercises_name ON exercises(name);
```

## 📊 Monitoramento

### Ver Logs no Railway

```bash
railway logs
```

### Queries Úteis

```sql
-- Contar sessões por usuário
SELECT user_id, COUNT(*) as total_sessions 
FROM workout_sessions 
GROUP BY user_id;

-- Exercícios mais populares
SELECT e.name, COUNT(*) as count 
FROM workout_exercises we 
JOIN exercises e ON we.exercise_id = e.exercise_id 
GROUP BY e.name 
ORDER BY count DESC 
LIMIT 10;

-- Sessões ativas
SELECT * FROM workout_sessions 
WHERE status = 'ativa' 
ORDER BY last_update DESC;
```

## 💾 Backup e Restauração

### Backup Manual

#### Opção 1: pg_dump (Recomendado)
```bash
# Instalar PostgreSQL client tools
# Ubuntu/Debian: sudo apt install postgresql-client
# macOS: brew install postgresql

# Fazer backup completo
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Restaurar
psql $DATABASE_URL < backup_20241026_150000.sql
```

#### Opção 2: Backup JSON (Interno)
```python
# Usar o novo serviço de backup
from services.postgres_backup_service import postgres_backup_service

# Backup em formato JSON
backup_path = await postgres_backup_service.create_backup_json()

# Listar backups
backups = await postgres_backup_service.list_backups()
```

### Backup Automatizado no Railway

1. **Railway CLI** (Desenvolvimento):
```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login
railway login

# Criar backup
railway db backup create

# Listar backups
railway db backup list
```

2. **GitHub Actions** (Produção):
```yaml
# .github/workflows/backup.yml
name: Database Backup
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install PostgreSQL client
        run: sudo apt-get install postgresql-client
      - name: Create backup
        run: |
          pg_dump ${{ secrets.DATABASE_URL }} > backup_$(date +%Y%m%d).sql
      - name: Upload to storage
        # Use your preferred storage (S3, Google Cloud, etc.)
```

## 🔒 Segurança

1. **Nunca commite** a `DATABASE_URL` no código
2. Use sempre variáveis de ambiente
3. No Railway, as variáveis são criptografadas
4. Configure backup automático no Railway (Premium)
5. **Backups locais**: Mantenha backups em local seguro

## 💡 Dicas

- PostgreSQL no Railway tem limite de 1GB no plano free
- Monitore o uso em Railway Dashboard > PostgreSQL > Metrics
- Configure alertas para uso de recursos
- Faça backups regulares dos dados importantes

## 🆘 Suporte

- [Railway Discord](https://discord.gg/railway)
- [Railway Docs](https://docs.railway.app)
- Issues no GitHub do projeto