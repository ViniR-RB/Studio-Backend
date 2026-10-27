# Arquitetura do frontend

## Fluxo

`Página → Feature → Repository → ApiHttp → HttpClient → API`

A página compõe a tela. A feature possui o formulário e o estado de carregamento/erro. O repository conhece endpoints e transforma respostas em schemas usados pela aplicação. `ApiHttp` centraliza base URL e opções comuns, mas mantém o `HttpClient` oficial do Angular para fetch, interceptors, XSRF e tipagem.

## Sessão sem access token

A sessão deve ser criada pelo backend em cookie `HttpOnly`; o frontend não persiste credenciais nem manipula token. O interceptor envia `withCredentials: true`. Para frontend e API em origens diferentes, o backend precisa permitir credenciais via CORS e configurar `SameSite`/`Secure` adequadamente. Operações mutáveis também devem usar proteção CSRF: Angular suporta o fluxo cookie→header, mas o backend atual ainda não expõe login, sessão ou cookie XSRF.

## Contrato atual

- `POST /api/v1/generations`: recebe `product_name`, `product_description`, `target_audience`, `tone`; retorna `202` com `job_id` e `status`.
- `GET /api/v1/generations/{job_id}`: retorna `job_id`, `status`, `error` e `slug`.
- `GET /api/v1/pages/{slug}`: retorna HTML publicado, não JSON.
- Rotas `/api/v1/internal/*` exigem `INTERNAL_API_TOKEN` e nunca devem ser chamadas pelo browser.

## Limite consciente

O backend atual não possui endpoints de login, logout, sessão ou usuário. Portanto a integração de sessão está preparada no cliente, mas não é funcional até esses endpoints existirem. Não foi criado um auth store fictício.
