# Guia de Deploy no Fly.io

## Backend (flc-bank-api)

```bash
cd c:\Users\User\Documents\flc\bk

# Deploy
fly deploy
```

## Frontend (grafeno-portal)

```bash
cd c:\Users\User\Documents\flc\grafeno-portal

# Atualizar URL da API no código (se necessário)
# Editar src/services/api.ts e configurar baseURL para https://flc-bank-api.fly.dev

# Deploy
fly deploy
```

## Verificar Status

```bash
# Listar apps
fly apps list

# Ver logs do backend
fly logs -a flc-bank-api

# Ver logs do frontend
fly logs -a grafeno-portal

# Abrir app no navegador
fly open -a grafeno-portal
```

## URLs dos Apps

- **Backend**: https://flc-bank-api.fly.dev
- **Frontend**: https://grafeno-portal.fly.dev

## Configurar Variáveis de Ambiente

Se precisar adicionar/atualizar variáveis:

```bash
# Backend
fly secrets set GRAFENO_API_TOKEN=seu-token-aqui -a flc-bank-api

# Listar secrets
fly secrets list -a flc-bank-api
```

## Troubleshooting

### App suspended
```bash
fly scale count 1 -a flc-bank-api
fly scale count 1 -a grafeno-portal
```

### Erro de build
```bash
# Ver logs detalhados
fly logs -a flc-bank-api

# Fazer deploy com mais verbose
fly deploy --verbose
```

### Atualizar configuração
```bash
# Editar fly.toml e fazer deploy novamente
fly deploy
```
