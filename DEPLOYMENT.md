# Gym Tracker Bot - Guia de Deploy e CI/CD

Este guia explica como configurar CI/CD e fazer deploy do Gym Tracker Bot em diferentes plataformas.

## Índice

1. [Visão Geral](#visão-geral)
2. [Pré-requisitos](#pré-requisitos)
3. [CI/CD com GitHub Actions](#cicd-com-github-actions)
4. [Opções de Deploy](#opções-de-deploy)
5. [Deploy Local com Docker](#deploy-local-com-docker)
6. [Deploy em Produção](#deploy-em-produção)

---

## Visão Geral

O pipeline de CI/CD está configurado para:

- ✅ **Testes automáticos** em múltiplas versões do Python
- 🐳 **Build de imagem Docker** automático
- 📦 **Push para GitHub Container Registry**
- 🚀 **Deploy automático** em produção (após configuração)
- 📊 **Cobertura de código** e relatórios
- 📱 **Notificações** via Telegram (opcional)

---

## Pré-requisitos

### Obrigatórios

1. **Token do Bot do Telegram**
   - Crie um bot com [@BotFather](https://t.me/botfather)
   - Copie o token fornecido

2. **Conta GitHub**
   - O código deve estar em um repositório GitHub
   - GitHub Actions habilitado (gratuito para repos públicos)

3. **Docker** (para deploy com containers)
   - [Instalar Docker](https://docs.docker.com/get-docker/)
   - [Instalar Docker Compose](https://docs.docker.com/compose/install/)

### Opcionais

- Conta em plataforma de hosting (Railway, Render, Fly.io, etc.)
- VPS (DigitalOcean, AWS, Linode, etc.)

---

## CI/CD com GitHub Actions

### O Pipeline Atual

O arquivo `.github/workflows/ci-cd.yml` define 4 jobs principais:

#### 1. **Test** - Testes Automáticos
```yaml
- Roda em Python 3.11 e 3.12
- Executa testes unitários e de integração
- Gera relatório de cobertura
- Faz linting do código (opcional)
```

#### 2. **Build** - Construção da Imagem Docker
```yaml
- Só executa se os testes passarem
- Só em branches main/develop
- Cria imagem Docker multi-arquitetura (amd64/arm64)
- Push para GitHub Container Registry
```

#### 3. **Deploy** - Deploy Automático
```yaml
- Só executa na branch main
- Suporta múltiplas plataformas (Railway, Render, VPS, Fly.io)
- Configurável via GitHub Variables
```

#### 4. **Notify** - Notificações
```yaml
- Envia status do pipeline via Telegram
- Configurável e opcional
```

### Configurar GitHub Actions

#### Passo 1: Habilitar GitHub Container Registry

1. Vá em **Settings** → **Actions** → **General**
2. Em "Workflow permissions", selecione:
   - ✅ Read and write permissions
3. Salve as alterações

#### Passo 2: Configurar Secrets

Vá em **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

**Secrets obrigatórios:**
- `TELEGRAM_BOT_TOKEN`: Token do seu bot

**Secrets para deploy (escolha um):**

**Railway:**
```
RAILWAY_TOKEN: Token da API do Railway
```

**Render:**
```
RENDER_API_KEY: API key do Render
```

**VPS (SSH):**
```
VPS_HOST: IP ou domínio do servidor
VPS_USERNAME: usuário SSH
VPS_SSH_KEY: chave privada SSH
```

**Fly.io:**
```
FLY_API_TOKEN: Token da API do Fly.io
```

**Notificações (opcional):**
```
TELEGRAM_NOTIFY_TOKEN: Token de outro bot para notificações
TELEGRAM_NOTIFY_CHAT_ID: ID do chat para receber notificações
```

#### Passo 3: Configurar Variables

Vá em **Settings** → **Secrets and variables** → **Actions** → **Variables**

```
DEPLOY_PLATFORM: railway | render | vps | flyio
ENABLE_TELEGRAM_NOTIFICATIONS: true | false
```

### Testando o Pipeline

1. Faça um commit em uma branch:
```bash
git add .
git commit -m "test: configurar CI/CD"
git push origin sua-branch
```

2. Vá em **Actions** no GitHub para ver o pipeline rodando

3. Se tudo passar, crie um Pull Request para `main`

---

## Opções de Deploy

### Comparação de Plataformas

| Plataforma | Custo Inicial | Complexidade | Uptime | Recursos |
|------------|---------------|--------------|--------|----------|
| **Railway** | Gratuito → $5/mês | 🟢 Fácil | 99.9% | Bom para começar |
| **Render** | Gratuito (limitado) | 🟢 Fácil | 99.5% | Limites no free tier |
| **Fly.io** | $0-5/mês | 🟡 Médio | 99.9% | Bom para produção |
| **VPS** | $5-10/mês | 🔴 Complexo | 99.9%+ | Controle total |

---

## Deploy Local com Docker

### Desenvolvimento Local

1. **Copie o arquivo de exemplo de ambiente:**
```bash
cp .env.example .env
```

2. **Edite o `.env` com suas credenciais:**
```bash
nano .env
# Adicione seu TELEGRAM_BOT_TOKEN
```

3. **Execute com Docker Compose:**
```bash
docker-compose up -d
```

4. **Veja os logs:**
```bash
docker-compose logs -f
```

5. **Parar o bot:**
```bash
docker-compose down
```

### Build Manual da Imagem

```bash
# Build
docker build -t gym-tracker-bot .

# Run
docker run -d \
  --name gym-tracker-bot \
  -e TELEGRAM_BOT_TOKEN=seu_token \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/backups:/app/backups \
  --restart unless-stopped \
  gym-tracker-bot
```

---

## Deploy em Produção

### Opção 1: Railway (Recomendado para Iniciantes)

Railway é a opção mais simples e oferece um plano gratuito generoso.

#### Passos:

1. **Crie uma conta no [Railway](https://railway.app/)**

2. **Instale o CLI do Railway:**
```bash
npm install -g @railway/cli
# ou
brew install railway
```

3. **Faça login:**
```bash
railway login
```

4. **Inicialize o projeto:**
```bash
railway init
```

5. **Configure as variáveis de ambiente:**
```bash
railway variables set TELEGRAM_BOT_TOKEN=seu_token
```

6. **Deploy:**
```bash
railway up
```

#### Deploy Automático via GitHub:

1. No Railway dashboard, clique em **"New Project"**
2. Escolha **"Deploy from GitHub repo"**
3. Selecione seu repositório
4. Adicione as variáveis de ambiente
5. Railway detectará o Dockerfile automaticamente
6. Cada push em `main` fará deploy automaticamente!

---

### Opção 2: Render

Render oferece hosting gratuito com algumas limitações.

#### Passos:

1. **Crie uma conta no [Render](https://render.com/)**

2. **Crie um novo Web Service:**
   - Clique em **"New +"** → **"Web Service"**
   - Conecte seu repositório GitHub
   - Configure:
     - **Name**: gym-tracker-bot
     - **Environment**: Docker
     - **Instance Type**: Free (ou pago)

3. **Adicione variáveis de ambiente:**
   - `TELEGRAM_BOT_TOKEN`: seu token

4. **Deploy:**
   - Render fará deploy automaticamente a cada push em `main`

#### Limitações do Free Tier:
- ⏰ Desliga após 15 minutos de inatividade
- 🔄 Precisa "acordar" quando recebe requisição (pode demorar)
- 💾 750 horas/mês de uso

**Solução:** Use um serviço de ping (como [UptimeRobot](https://uptimerobot.com/)) para manter o bot acordado.

---

### Opção 3: Fly.io

Fly.io é excelente para produção, com preços competitivos.

#### Passos:

1. **Instale o Fly CLI:**
```bash
curl -L https://fly.io/install.sh | sh
```

2. **Faça login:**
```bash
flyctl auth login
```

3. **Crie o arquivo `fly.toml`:**
```bash
flyctl launch --no-deploy
```

Exemplo de `fly.toml`:
```toml
app = "gym-tracker-bot"
primary_region = "gru"  # São Paulo

[build]
  dockerfile = "Dockerfile"

[env]
  PYTHONUNBUFFERED = "1"

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    port = 8080

[mounts]
  source = "data"
  destination = "/app/data"
```

4. **Configure secrets:**
```bash
flyctl secrets set TELEGRAM_BOT_TOKEN=seu_token
```

5. **Deploy:**
```bash
flyctl deploy
```

6. **Para deploy automático via GitHub Actions:**
   - Adicione `FLY_API_TOKEN` nos secrets do GitHub
   - O pipeline já está configurado!

---

### Opção 4: VPS (Digital Ocean, AWS, etc.)

Para controle total, use um VPS.

#### Passos:

1. **Crie um VPS** (recomendado: Ubuntu 22.04)

2. **Configure SSH** e conecte-se:
```bash
ssh root@seu_ip
```

3. **Instale Docker e Docker Compose:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

4. **Clone o repositório:**
```bash
git clone https://github.com/seu-usuario/gym-tracker-bot.git
cd gym-tracker-bot
```

5. **Configure o ambiente:**
```bash
cp .env.example .env
nano .env  # Adicione suas credenciais
```

6. **Inicie o bot:**
```bash
docker-compose up -d
```

#### Deploy Automático via GitHub Actions:

O pipeline já está configurado! Basta:

1. **No servidor, gere uma chave SSH:**
```bash
ssh-keygen -t ed25519 -C "github-actions"
cat ~/.ssh/id_ed25519  # Copie a chave privada
```

2. **No GitHub, adicione os secrets:**
   - `VPS_HOST`: IP do servidor
   - `VPS_USERNAME`: usuário SSH
   - `VPS_SSH_KEY`: chave privada

3. **Configure a variável:**
   - `DEPLOY_PLATFORM`: vps

4. **A cada push em `main`, o deploy será automático!**

---

## Monitoramento e Manutenção

### Ver Logs

**Docker Compose:**
```bash
docker-compose logs -f
```

**Docker:**
```bash
docker logs -f gym-tracker-bot
```

**Railway:**
```bash
railway logs
```

**Fly.io:**
```bash
flyctl logs
```

### Health Checks

O bot tem health checks configurados:

**Docker:**
```bash
docker inspect --format='{{.State.Health.Status}}' gym-tracker-bot
```

**HTTP Endpoint** (se configurado):
```bash
curl http://localhost:8080/health
```

### Backups Automáticos

O bot já tem sistema de backup integrado. Para garantir:

1. **Monte o volume de backups:**
   - Já configurado em `docker-compose.yml`

2. **Configure backup remoto** (recomendado):
```bash
# Cron job para upload dos backups
0 3 * * * rsync -avz /caminho/backups/ user@backup-server:/backups/
```

### Atualizações

**Manualmente:**
```bash
git pull origin main
docker-compose build
docker-compose up -d
```

**Automaticamente:**
- O CI/CD já faz isso a cada push em `main`!

---

## Troubleshooting

### Bot não inicia

1. **Verifique o token:**
```bash
docker-compose logs | grep -i "token\|auth\|error"
```

2. **Verifique permissões:**
```bash
ls -la data/ backups/
```

3. **Recrie os containers:**
```bash
docker-compose down
docker-compose up -d --force-recreate
```

### Testes falhando no CI

1. **Execute localmente:**
```bash
python run_tests.py
```

2. **Verifique dependências:**
```bash
pip install -r requirements.txt
```

### Deploy falha

1. **Verifique secrets no GitHub**
2. **Veja os logs do workflow em Actions**
3. **Teste o build local:**
```bash
docker build -t test .
```

---

## Próximos Passos

Após configurar o CI/CD e deploy:

1. ✅ Teste o bot no Telegram
2. ✅ Configure monitoramento (UptimeRobot, etc.)
3. ✅ Configure alertas via Telegram
4. ✅ Faça backup manual para testar
5. ✅ Documente suas configurações específicas

---

## Recursos Adicionais

- [Documentação do GitHub Actions](https://docs.github.com/en/actions)
- [Documentação do Docker](https://docs.docker.com/)
- [Railway Docs](https://docs.railway.app/)
- [Render Docs](https://render.com/docs)
- [Fly.io Docs](https://fly.io/docs/)

---

## Suporte

Se tiver problemas:

1. Veja os logs do bot
2. Verifique o status do GitHub Actions
3. Teste localmente com Docker
4. Abra uma issue no repositório

**Happy Deploying! 🚀**
