# Dropshipping landing-page generator

MVP com FastAPI, PostgreSQL, n8n e OpenDesign em containers. O OpenDesign usa uma imagem derivada que instala a CLI do OpenCode e o modelo gratuito `opencode/mimo-v2.6-flash-free`. O fluxo recebe um produto, gera HTML no OpenDesign/OpenCode, salva a versão na API e entrega a versão publicada por slug.

## Executar

```bash
cp .env.example .env
docker compose -f docker-compose.yml config
docker compose -f docker-compose.yml up --build
```

A API fica em `http://localhost:8000`. O n8n é interno no Compose; importe `n8n/workflows/landing-page-generation.json` depois de iniciar o stack. A imagem `backend/Dockerfile.open-design` instala a CLI do OpenCode e registra automaticamente o MCP do OpenDesign com `od mcp install opencode`. O modelo padrão fica em `OPENCODE_MODEL` e usa o catálogo gratuito do OpenCode; confirme a disponibilidade no momento da execução, pois os modelos gratuitos podem mudar.

## Segurança

`INTERNAL_API_TOKEN`, `OD_API_TOKEN` e `N8N_ENCRYPTION_KEY` devem ser valores fortes no `.env`. PostgreSQL e OpenDesign não são publicados. HTML gerado é entrada não confiável; mantenha o endpoint interno protegido pelo token.

## Contrato rápido

- `POST /api/v1/generations` com `product_name`, `product_description`, `target_audience` e `tone` retorna `202` e `job_id`.
- `GET /api/v1/generations/{job_id}` consulta o status.
- n8n envia `POST /api/v1/internal/generations/{job_id}/result` com `html` e `slug`.
- `GET /api/v1/pages/{slug}` entrega somente HTML publicado.
