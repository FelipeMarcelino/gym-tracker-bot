# Git Workflow e CI/CD

## 🔄 Fluxo de Trabalho Recomendado (Git Flow)

### Branches Principais

```
main     → Produção (ambiente de produção)
develop  → Staging (ambiente de desenvolvimento)
feature/* → Features em desenvolvimento
hotfix/*  → Correções urgentes
```

---

## 📊 Fluxo Completo

### 1. Desenvolvimento de Features

```bash
# Criar nova feature a partir da develop
git checkout develop
git pull origin develop
git checkout -b feature/nome-da-feature

# Desenvolver...
git add .
git commit -m "feat: adiciona nova funcionalidade"
git push origin feature/nome-da-feature
```

**No GitHub:**
- Criar PR de `feature/nome-da-feature` → `develop`
- **CI/CD roda:**
  - ✅ Testes (Python 3.11 e 3.12)
  - ✅ Linting
  - ✅ Build validation (sem push)

**Após aprovação:**
- Merge para `develop`
- **CI/CD roda:**
  - ✅ Testes
  - ✅ Build e push para GHCR com tag `staging`
  - ❌ Deploy NÃO roda (só em main)

---

### 2. Release para Produção

```bash
# Quando develop estiver pronto para produção
git checkout develop
git pull origin develop
```

**No GitHub:**
- Criar PR de `develop` → `main`
- **CI/CD roda:**
  - ✅ Testes
  - ✅ Build validation

**Após aprovação e merge:**
- Push em `main`
- **CI/CD roda:**
  - ✅ Testes
  - ✅ Build e push com tag `latest`
  - ✅ **DEPLOY em produção** 🚀

---

### 3. Hotfixes (Correções Urgentes)

```bash
# Criar hotfix a partir da main
git checkout main
git pull origin main
git checkout -b hotfix/correcao-critica

# Corrigir...
git add .
git commit -m "fix: corrige bug crítico"
git push origin hotfix/correcao-critica
```

**No GitHub:**
- Criar PR de `hotfix/correcao-critica` → `main`
- Após merge: deploy automático

**Importante:** Após hotfix em main, fazer merge em develop também:
```bash
git checkout develop
git merge main
git push origin develop
```

---

## 🎯 Resumo do CI/CD

### Pull Requests (qualquer branch → main/develop)
```
✅ Testes (unit + integration)
✅ Linting
✅ Build validation (não faz push)
❌ Deploy
```

### Push em `develop`
```
✅ Testes
✅ Build e push (tag: staging, develop)
❌ Deploy
```

### Push em `main`
```
✅ Testes
✅ Build e push (tag: latest, main, SHA)
✅ Deploy para produção 🚀
```

### Push em `claude/**` ou feature branches
```
✅ Testes apenas
❌ Build
❌ Deploy
```

---

## ❓ Perguntas Frequentes

### "Preciso reabrir develop toda vez que quero mergear em main?"

**Não!** O fluxo é:

```
Feature → PR → develop → (testes + build staging)
                 ↓
         (quando pronto)
                 ↓
           develop → PR → main → (testes + build + deploy)
```

Você **mantém develop sempre ativa** e vai acumulando features nela. Quando quiser fazer release, cria um PR de develop → main.

---

### "Como testar antes de ir para produção?"

**Opção 1: Use a imagem staging**

Após merge em develop, uma imagem é criada com tag `staging`:
```bash
docker pull ghcr.io/felipemarcelino/gym-tracker-bot:staging
docker run -d --env-file .env ghcr.io/felipemarcelino/gym-tracker-bot:staging
```

**Opção 2: Deploy manual de develop em ambiente de staging**

Configure um ambiente de staging separado que aponta para a branch develop.

---

### "E se eu quiser testar uma feature específica antes de mergear?"

```bash
# Na sua feature branch
docker build -t gym-tracker-bot:minha-feature .
docker run -d --env-file .env gym-tracker-bot:minha-feature
```

Ou use o PR - o CI/CD valida o build automaticamente!

---

### "Como reverter um deploy com problema?"

**Opção 1: Revert do commit**
```bash
git revert <commit-sha>
git push origin main
# CI/CD faz deploy automático da versão anterior
```

**Opção 2: Deploy de versão anterior**
```bash
# Usar imagem anterior do registry
docker pull ghcr.io/felipemarcelino/gym-tracker-bot:main-<sha-anterior>
```

---

## 🏷️ Tags de Imagens Docker

O CI/CD cria as seguintes tags automaticamente:

### Em `develop`:
- `staging` - Sempre aponta para o último push em develop
- `develop` - Mesmo que staging
- `develop-abc123` - Tag com SHA do commit

### Em `main`:
- `latest` - Sempre aponta para o último push em main
- `main` - Mesmo que latest
- `main-abc123` - Tag com SHA do commit

### Exemplo de uso:
```bash
# Produção (última versão estável)
docker pull ghcr.io/felipemarcelino/gym-tracker-bot:latest

# Staging (última versão em desenvolvimento)
docker pull ghcr.io/felipemarcelino/gym-tracker-bot:staging

# Versão específica
docker pull ghcr.io/felipemarcelino/gym-tracker-bot:main-a02a059
```

---

## 🚀 Exemplo Prático Completo

### Cenário: Adicionar nova funcionalidade de estatísticas

**1. Criar feature branch:**
```bash
git checkout develop
git pull origin develop
git checkout -b feature/advanced-stats
```

**2. Desenvolver e commitar:**
```bash
# Fazer alterações...
git add .
git commit -m "feat: add advanced statistics endpoint"
git push origin feature/advanced-stats
```

**3. Criar PR no GitHub:**
- `feature/advanced-stats` → `develop`
- CI/CD roda testes e valida build
- Code review
- Merge!

**4. CI/CD em develop:**
- ✅ Testes passam
- ✅ Build cria imagem `staging`
- Imagem disponível para testes

**5. Testar staging (opcional):**
```bash
docker pull ghcr.io/felipemarcelino/gym-tracker-bot:staging
docker run -d --env-file .env ghcr.io/felipemarcelino/gym-tracker-bot:staging
# Testar a nova funcionalidade
```

**6. Release para produção:**
- Criar PR: `develop` → `main`
- CI/CD valida novamente
- Merge!

**7. CI/CD em main:**
- ✅ Testes
- ✅ Build imagem `latest`
- ✅ **Deploy automático** 🎉

---

## 📋 Checklist de Release

Antes de fazer merge de develop → main:

- [ ] Todos os testes passando
- [ ] Code review aprovado
- [ ] Funcionalidades testadas em staging
- [ ] Documentação atualizada
- [ ] CHANGELOG.md atualizado (opcional)
- [ ] Sem bugs críticos conhecidos
- [ ] Performance verificada

---

## 🔧 Configuração Necessária

### GitHub Secrets (Settings → Secrets):
- `TELEGRAM_BOT_TOKEN` - Token do bot (obrigatório)
- `RAILWAY_TOKEN` - Se usar Railway
- `RENDER_API_KEY` - Se usar Render
- `FLY_API_TOKEN` - Se usar Fly.io
- `VPS_HOST`, `VPS_USERNAME`, `VPS_SSH_KEY` - Se usar VPS

### GitHub Variables (Settings → Variables):
- `DEPLOY_PLATFORM`: railway | render | flyio | vps
- `ENABLE_TELEGRAM_NOTIFICATIONS`: true | false (opcional)

---

## 📞 Suporte

Se tiver dúvidas sobre o workflow:
1. Veja a documentação em `DEPLOYMENT.md`
2. Verifique os logs do CI/CD em Actions
3. Consulte este guia

**Regra de ouro:** Sempre faça PR para develop primeiro, teste, e só então faça PR para main!
