# CLAUDE.md — Status Empresarial por CUIT

## Qué es este proyecto

Plataforma que genera un **informe de status empresarial a partir de un CUIT**.
Trabaja **únicamente con personas jurídicas** (empresas); las personas físicas
quedan fuera del dominio. A partir del CUIT se recopila y estructura información de
status de la empresa y se entrega un informe.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11 + FastAPI |
| Base de datos | Supabase (PostgreSQL + Storage + Auth) |
| Motor de IA | Anthropic API — Claude |
| Config | pydantic-settings |

## Estructura de carpetas

```
backend/
├── main.py                 ← entrada FastAPI: solo configuración de la app
├── config/
│   └── settings.py         ← única fuente de variables de entorno
├── routers/                ← endpoints, sin lógica de negocio (máx 80 líneas)
├── controllers/            ← orquestación router ↔ services (máx 100 líneas)
├── services/               ← lógica de negocio (máx 150 líneas)
├── repositories/           ← único acceso a la base de datos (máx 100 líneas)
├── integrations/           ← wrappers de servicios externos (Supabase, Anthropic)
├── schemas/                ← modelos Pydantic de entrada y salida
├── middleware/
│   └── error_handler.py    ← handler global de errores
├── utils/
│   ├── errors.py           ← AppError(message, code, status_code)
│   └── logger.py           ← logger JSON estructurado
├── migrations/             ← SQL versionado (fase posterior)
├── tests/
├── requirements.txt
└── .env.example
```

## Convenciones

Este proyecto sigue de forma estricta los cuatro documentos base de la agencia:

- `docs/ORDEN-Y-LEGIBILIDAD.md` — capas, límites de líneas, naming, errores.
- `docs/SEGURIDAD-PENTEST.md` — secretos, auth, validación, RLS, headers, logging.

Reglas no negociables:

- Arquitectura por capas estricta: `router → controller → service → repository`.
- Errores: siempre `AppError(message, code, status_code)`; nunca excepciones
  genéricas. Formato de respuesta único: `{"error": True, "message": ..., "code": ...}`.
- `config/settings.py` es el único módulo que toca `os.environ`.
- Sin `print()` — usar el logger de `utils/logger.py`.
- Límites de líneas: routers 80, controllers 100, services 150, repositories 100.
- Docstring obligatorio en funciones de `services/` e `integrations/`.

## Estado actual

**Entrega 1 — en curso. Scaffold hecho:**

- Esqueleto del backend por capas, sin lógica de negocio.
- `main.py` con handler de errores, security headers, CORS y `GET /health`.
- `settings.py`, `errors.py`, `logger.py`, `error_handler.py`.
- `services/cuit_service.py`: guardrail de CUIT (limpieza, dígito verificador
  módulo 11, tipo de persona, `validar_cuit_juridica`) + tests (6/6 pasando).
- Maquinaria async/job (esqueleto, sin fuentes de datos): `schemas/job.py`,
  `repositories/job_repo.py` (interfaz `JobRepository` + `InMemoryJobRepository`),
  `services/job_service.py` (pipeline de fuentes como STUB), `controllers/job_controller.py`,
  `routers/job_router.py` (`POST /consultas`, `GET /consultas/{job_id}`) + tests
  (4/4). Las fuentes reales (BCRA/ARCA) se enchufan en `_ejecutar_pipeline`.
- Maquinaria de caché con TTL (esqueleto, sin fuentes ni Supabase):
  `repositories/cache_repo.py` (interfaz `CacheRepository` + `InMemoryCacheRepository`,
  expiración lazy con `time.monotonic()`), `services/cache_service.py`
  (`construir_key` `"{fuente}:{cuit}"`, `obtener_cacheado`, `guardar_en_cache` y
  TTLs `TTL_BCRA`/`TTL_ARCA`=24h, `TTL_BORA`=7d) + tests (5/5). Todavía sin cablear
  en `job_service`; se integra al enchufar BCRA.
- Capa de autenticación (seguridad pura, sin endpoints todavía): `schemas/auth.py`
  (`RegisterRequest`/`LoginRequest`/`TokenResponse` + entidad `User`),
  `repositories/user_repo.py` y `repositories/refresh_token_repo.py` (interfaces +
  impl en memoria; refresh tokens hasheados, nunca en texto plano), `utils/jwt.py`
  (create/verify de JWT tipados access/refresh, refresh con `jti` único),
  `services/auth_service.py` (register/login/refresh con rotación §2.5/logout;
  bcrypt + SHA-256 previo; errores genéricos §2.3) y `middleware/auth.py`
  (`PUBLIC_ROUTES` + `auth_middleware`) + tests (8/8).
- Endpoints de auth + shell de onboarding (cableado sobre la seguridad ya existente):
  `controllers/auth_controller.py` (orquesta `auth_service` + onboarding sobre
  `user_repo`), `routers/auth_router.py` (`POST /api/auth/register|login|refresh|logout`),
  `routers/me_router.py` (`GET /api/me`, `POST /api/onboarding/complete`),
  `schemas/auth.py` (`RefreshRequest`, `MeResponse`), `get_current_user` en
  `middleware/auth.py` (id del token, §2.4) y `update_onboarding_completed` en
  `user_repo`. `main.py` registra `auth_middleware` (orden `CORS → SecurityHeaders
  → auth`; `/health` y `PUBLIC_ROUTES` pasan sin token) + tests (7/7).
- Redactor IA del informe (agente transversal, fuentes aún sin conectar):
  `integrations/anthropic_client.py` (wrapper fino del SDK, aísla la API §6.2; key
  de `settings`; `generar_texto` con system separado del user §6.1; fallo →
  `CLAUDE_UNAVAILABLE` 503) y `services/report_service.py` (`SYSTEM_PROMPT` solo
  hechos/sin valorativos, `sanitizar_datos_entrada` §6.1, `generar_informe`,
  `validar_salida` §6.3 → `REPORT_VALIDATION_FAILED` 500). Sin cablear al
  `job_service` todavía (se conecta al enchufar BCRA) + tests (6/6, cliente mockeado).

**Pendiente:** conectar fuentes de datos (BCRA/ARCA) en el pipeline (con caché) y
cablear el redactor en `job_service`, persistencia real
(`SupabaseJobRepository`/`SupabaseUserRepository`), rate limiting, migraciones SQL
con RLS, más tests del flujo de informe. Ver `ARCHITECTURE.md` para la deuda técnica.
