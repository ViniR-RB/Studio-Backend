# Frontend agent guide

## Scope

`ui/` is a standalone Angular 20 application. Keep the frontend minimal and aligned to the FastAPI contract in `../app/schemas.py` and `../app/main.py`.

## Layer rules

- `core/schemas`: API DTOs and domain-facing types; no Angular imports.
- `core/http`: one thin `ApiHttp` wrapper around Angular `HttpClient`; preserve Angular options instead of replacing the transport.
- `core/repositories`: endpoint consumption and API-to-domain mapping only.
- `features`: feature forms and orchestration; use typed Reactive Forms.
- `pages`: route-level composition only.
- `ui/atoms`: small reusable controls (button, chip, modal).
- `ui/molecules`: composed controls (sidebar, form sections).

## Authentication

Use server sessions in `HttpOnly`, `Secure`, `SameSite` cookies. The browser owns the cookie; the UI must never read, store, or attach access tokens. Keep `withCredentials: true` in the HTTP boundary. Add a CSRF cookie/header contract before enabling cross-site deployments. Do not expose internal API token endpoints to the browser.

## Commands

From `ui/`: `npm start`, `npm run build`, `npm test`.

## Design constraints

Prefer Angular standalone components, signals for local UI state, native HTML controls, Tailwind utilities, and the smallest working diff. Do not add a state-management library unless a real cross-route state need appears.
