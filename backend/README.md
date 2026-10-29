# Dropshipping landing-page generator

MVP com FastAPI, PostgreSQL, n8n e OpenDesign em containers. O fluxo recebe um produto, gera HTML no OpenDesign/OpenCode, salva a versão na API e entrega a versão publicada por slug.

## Executar

```bash
cp ../.env.example ../.env
docker compose config
docker compose up --build -d
```

Serviços locais:

- API: `http://localhost:8000`
- OpenDesign: `http://localhost:7456`
- n8n: `http://localhost:5678`
- Frontend em desenvolvimento: `http://localhost:4200`

Para acessar o OpenDesign, use autenticação básica:

- Usuário: `open-design`
- Senha: valor de `OD_API_TOKEN`

## Variáveis de ambiente

As variáveis ficam no arquivo `.env` na raiz do repositório. Comece copiando `.env.example` para `.env` e substitua os valores de exemplo.

| Variável | Obrigatória | Descrição | Exemplo local |
| --- | --- | --- | --- |
| `POSTGRES_DB` | Sim | Nome do banco PostgreSQL usado pelos serviços. | `dropshipping` |
| `POSTGRES_USER` | Sim | Usuário do PostgreSQL. | `dropshipping` |
| `POSTGRES_PASSWORD` | Sim | Senha do PostgreSQL. | `change-me` |
| `DATABASE_URL` | Sim | URL assíncrona usada pela API para conectar ao banco. | `postgresql+asyncpg://dropshipping:change-me@postgres:5432/dropshipping` |
| `INTERNAL_API_TOKEN` | Sim | Token Bearer usado para proteger os endpoints internos da API. | `change-me` |
| `N8N_WEBHOOK_URL` | Sim | Webhook do n8n chamado pela API para iniciar uma geração. | `http://n8n:5678/webhook/landing-page-generation` |
| `OPENCODE_MODEL` | Não | Modelo usado pelo OpenCode. O Compose fornece um padrão gratuito. | `opencode/nemotron-v3.5-lightning-free` |
| `OPEN_DESIGN_IMAGE` | Não | Imagem Docker do OpenDesign. | `ghcr.io/nexu-io/od:latest` |
| `OD_API_TOKEN` | Sim | Senha da autenticação básica do OpenDesign e token de integração com o n8n. | `change-me` |
| `N8N_ENCRYPTION_KEY` | Sim | Chave usada pelo n8n para criptografar credenciais e dados sensíveis. | `change-me` |
| `SESSION_COOKIE_NAME` | Não | Nome do cookie de sessão da API. | `session` |
| `SESSION_TTL_SECONDS` | Não | Tempo de vida da sessão em segundos. | `604800` |
| `FRONTEND_ORIGINS` | Não | Origens permitidas pelo CORS da API, separadas por vírgula. | `http://localhost:4200` |
| `COOKIE_SECURE` | Não | Envia o cookie apenas por HTTPS quando `true`. Use `false` no desenvolvimento local. | `false` |
| `COOKIE_SAMESITE` | Não | Política `SameSite` do cookie de sessão. | `lax` |

Gere valores fortes para tokens e chaves antes de qualquer ambiente compartilhado ou público:

```bash
openssl rand -hex 32
```

Não versione `.env` nem reutilize os valores `change-me` fora do desenvolvimento local.

## Workflows do n8n

Depois de iniciar os serviços, importe o workflow em `../n8n/workflows/landing-page-generation.json` no n8n. Os arquivos `v2` e `v3` são versões alternativas mantidas para referência.

## Contrato rápido

- `POST /api/v1/auth/login` autentica um usuário e cria uma sessão HTTP-only.
- `GET /api/v1/auth/me` retorna o usuário da sessão atual.
- `POST /api/v1/generations` inicia uma geração e retorna `202` com `job_id`.
- `GET /api/v1/generations/{job_id}` consulta o status.
- n8n envia `POST /api/v1/internal/generations/{job_id}/result` com `html` e `slug`.
- `GET /api/v1/pages/{slug}` entrega somente HTML publicado.

## Testes

```bash
python -m pytest -q
```
