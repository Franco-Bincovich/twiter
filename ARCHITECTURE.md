# Arquitectura — Status Empresarial por CUIT

## Stack elegido y por qué

| Capa | Tecnología | Por qué |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Tipado con Pydantic, validación automática de inputs (422 antes de la lógica), async nativo. Stack estándar de la agencia. |
| Base de datos | Supabase (PostgreSQL + Storage + Auth) | Postgres administrado con RLS como segunda línea de defensa de autorización; Storage para los informes generados. |
| Motor de IA | Anthropic API — Claude | Para la redacción/estructuración del informe de status a partir de los datos del CUIT. |
| Config | pydantic-settings | Un único punto que lee el entorno; el resto del código nunca toca `os.environ`. |

Documentos base que rigen el proyecto:

- `docs/ORDEN-Y-LEGIBILIDAD.md` — estructura por capas, límites de líneas, naming, manejo de errores.
- `docs/SEGURIDAD-PENTEST.md` — secretos, auth, validación, RLS, headers, logging.

## Decisiones de diseño

- **Arquitectura por capas estricta**: `router → controller → service → repository`.
  Los routers no contienen lógica de negocio; los repositories son el único punto
  de acceso a la base de datos.
- **Un único formato de error**: `{"error": True, "message": ..., "code": ...}`,
  producido siempre por el handler global (`middleware/error_handler.py`). Los
  services levantan `AppError(message, code, status_code)` y nunca excepciones
  genéricas.
- **Configuración centralizada**: `config/settings.py` es el único módulo que lee
  variables de entorno. Falla al arrancar si falta una variable obligatoria
  (fail-fast).
- **Seguridad desde el día 1**: `.env` bloqueado en `.gitignore`, security headers
  en cada respuesta, CORS con lista blanca explícita (nunca `*`), logging JSON
  estructurado que nunca registra secretos.
- **Solo personas jurídicas**: el dominio se restringe a CUIT de empresas; la
  validación específica del formato y tipo de CUIT se implementará en la capa de
  schemas en entregas siguientes.

## Estado del scaffold

Esqueleto puro, sin lógica de negocio. Lo implementado hoy:

- `main.py` con handler global de errores, middleware de security headers, CORS y
  el endpoint `GET /health`.
- `config/settings.py`, `utils/errors.py`, `utils/logger.py`,
  `middleware/error_handler.py`.
- Paquetes vacíos para `routers`, `controllers`, `services`, `repositories`,
  `integrations`, `schemas`, `tests` y carpeta `migrations`.

## Deuda técnica / pendiente

- **Autenticación**: middleware de auth, JWT con refresh tokens y rotación
  (SEGURIDAD-PENTEST.md sección 2) — pendiente.
- **Validación de CUIT**: schemas Pydantic con validación de dígito verificador y
  filtrado de personas físicas — pendiente.
- **Integraciones**: clientes de Supabase y Anthropic en `integrations/` — stubs
  pendientes.
- **Rate limiting** (slowapi) por endpoint sensible — pendiente.
- **Migraciones SQL versionadas** con RLS por tabla — fase posterior.
- **Tests críticos** del flujo de generación de informe — pendiente.
