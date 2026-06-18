# Changelog

Formato basado en commits convencionales (ver ORDEN-Y-LEGIBILIDAD.md sección 8).

## [0.1.0] — Entrega 1 · Scaffold del backend

### Added

- Estructura base del backend FastAPI por capas (`routers`, `controllers`,
  `services`, `repositories`, `integrations`, `schemas`, `middleware`, `utils`,
  `migrations`, `tests`).
- `main.py`: configuración de la app con handler global de errores, middleware de
  security headers, CORS con lista blanca y endpoint `GET /health`.
- `config/settings.py`: configuración centralizada con pydantic-settings; único
  módulo que lee el entorno.
- `utils/errors.py`: clase `AppError(message, code, status_code)`.
- `utils/logger.py`: logger JSON estructurado.
- `middleware/error_handler.py`: handler global con formato de error uniforme
  `{"error": True, "message": ..., "code": ...}`.
- `requirements.txt` con versiones exactas y `.env.example` con todas las variables.
- `.gitignore`, `README.md`, `ARCHITECTURE.md` y `CLAUDE.md` del proyecto.
- `services/cuit_service.py`: validación y clasificación de CUIT (lógica pura).
  Funciones `limpiar_cuit`, `validar_digito_verificador` (módulo 11),
  `detectar_tipo_persona` y el guardrail `validar_cuit_juridica`, que solo deja
  pasar personas jurídicas válidas.
- `tests/test_cuit_service.py`: 6 casos del guardrail (jurídica válida, jurídica
  con separadores, física no permitida, dígito verificador incorrecto, menos de
  11 dígitos, prefijo desconocido).
- Maquinaria async/job (sin fuentes de datos todavía, solo el esqueleto):
  - `schemas/job.py`: enum `JobStatus`, `JobCreateRequest`, entidad `Job` y
    `JobResponse`.
  - `repositories/job_repo.py`: interfaz abstracta `JobRepository` +
    `InMemoryJobRepository` (dict en memoria, thread-safe con `asyncio.Lock`).
    Temporal hasta conectar Supabase con la misma interfaz.
  - `services/job_service.py`: `crear_job` (valida vía `cuit_service`), `procesar_job`
    (PENDING→PROCESSING→DONE/ERROR; pipeline de fuentes como STUB) y `obtener_job`.
  - `controllers/job_controller.py`: orquesta el service y dispara `procesar_job`
    en background con `BackgroundTasks`.
  - `routers/job_router.py`: `POST /consultas` (202 Accepted, PENDING) y
    `GET /consultas/{job_id}` (polling). Registrado en `main.py`.
  - `tests/test_job_service.py`: 4 casos (jurídica→PENDING, física→
    PERSONA_FISICA_NOT_ALLOWED, PENDING→DONE con stub, inexistente→JOB_NOT_FOUND).
- Maquinaria de caché con TTL para respuestas de fuentes externas (sin fuentes
  conectadas todavía, solo el esqueleto; el cableado se hace al enchufar BCRA):
  - `repositories/cache_repo.py`: interfaz abstracta `CacheRepository`
    (`get`/`set`/`delete` async) + `InMemoryCacheRepository` (dict en memoria,
    thread-safe con `asyncio.Lock`, expiración lazy medida con `time.monotonic()`).
    Temporal hasta conectar Supabase con la misma interfaz.
  - `services/cache_service.py`: capa fina sobre el repo. `construir_key`
    (formato `"{fuente}:{cuit}"`), `obtener_cacheado`, `guardar_en_cache` y los
    TTL por defecto `TTL_BCRA`/`TTL_ARCA` (24h) y `TTL_BORA` (7 días).
  - `tests/test_cache_service.py`: 5 casos (set+get, key inexistente→None,
    entrada expirada→None, formato de key, delete remueve la entrada).

### Fixed

- `utils/logger.py`: el `JSONFormatter` de SEGURIDAD §8.2 no anexaba los campos de
  `extra={...}` al JSON. `logging` no los expone como `record.extra`, sino como
  atributos sueltos del `LogRecord`; ahora `format()` los recupera comparando los
  atributos del record contra un `LogRecord` base y anexa los no estándar.
- `main.py`: el `SecurityHeadersMiddleware` del snippet de SEGURIDAD §5.1 usaba
  `response.headers.pop("server", None)`, pero `MutableHeaders` de Starlette no
  soporta `pop()`. Se reemplazó por `if "server" in response.headers: del
  response.headers["server"]`.

### Changed

- `ARCHITECTURE.md` y `CLAUDE.md`: las referencias a los documentos base ahora
  apuntan a `docs/ORDEN-Y-LEGIBILIDAD.md` y `docs/SEGURIDAD-PENTEST.md` (antes
  `../`), reflejando que los docs viven en `docs/` dentro del repo.

### Notas

- Scaffold puro: sin lógica de negocio ni endpoints de feature (solo `/health`).
