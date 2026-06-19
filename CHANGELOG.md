# Changelog

Formato basado en commits convencionales (ver ORDEN-Y-LEGIBILIDAD.md sección 8).

## [Sin publicar]

### Changed

- El redactor IA (`services/report_service.py`) pasa de "reportar solo hechos" a actuar
  como **analista experto en BCRA Central de Deudores**: traduce los datos a lenguaje
  simple, da opinión experta SOBRE LOS DATOS (perfil sólido/deteriorado, evolución) y
  estructura el informe en resumen + situación actual + histórico + cheques. Sigue siendo
  el mismo service (no se creó un agente nuevo).
  - `services/prompts/bcra_analista.py` (nuevo módulo): se extrae el `SYSTEM_PROMPT` a una
    constante aparte para respetar el límite de 150 líneas del service y dejar un único
    lugar auditable del prompt (SEGURIDAD-PENTEST.md 6.1). El prompt incluye glosario de
    situaciones (0 a 5) y flags, e impone el límite clave: opina sobre el DATO, nunca
    recomienda una DECISIÓN al usuario.
  - `services/report_service.py`: `_construir_user_content` ahora arma el user_content a
    partir del dict normalizado de `bcra_service` (`denominacion`, `actual`, `historico`,
    `cheques`), serializado por sección en JSON legible y separado del system prompt (6.1).
    `validar_salida` se amplía (defensa en profundidad, 6.3): además de la fuga del prompt
    y los términos valorativos ya vetados, detecta patrones de recomendación de decisión
    ("no le d", "no conviene", "te recomiendo", "evitá", "deberías", "es confiable para",
    etc. — guardrail NO exhaustivo) → `REPORT_VALIDATION_FAILED` (500).
  - `tests/test_report_service.py`: el test de separación system/user usa el dict de
    `bcra_service`; se agregan casos de recomendación de decisión (falla), opinión sobre el
    dato (pasa) y armado del user_content con las cuatro secciones del BCRA (9 casos).

### Fixed

- `services/bcra_normalizer.py`: corregido el cálculo de desvíos del histórico. Antes
  contaba como desvío toda entidad con `situacion != 1`, lo que incluía la situación 0
  ("sin deuda informada", que es ausencia de deuda, no un deterioro de riesgo). Ahora
  un desvío es únicamente `situacion` entre 2 y 5 inclusive; la 0 y la 1 no son
  desvíos. `situacion_maxima` (peor situación del periodo más reciente) no cambia:
  sigue considerando todas las situaciones. Test `test_bcra_service.py` ajustado con un
  caso de situación 0 en el histórico que NO cuenta como desvío y uno de situación 3
  que SÍ.

### Added

- Collector de BCRA Central de Deudores (primera fuente real del producto). Cubre
  los tres endpoints públicos del BCRA y normaliza su salida a un dict estable.
  Todavía sin cablear a `job_service` ni a la caché.
  - `integrations/bcra_client.py`: wrapper de transporte con httpx async que aísla
    TODA llamada al BCRA (SEGURIDAD-PENTEST.md 6.2). Una función async por endpoint
    (`consultar_deudas`, `consultar_historicas`, `consultar_cheques`), cada una
    devuelve el `results` o None (404 = sin datos = resultado válido). Base URL como
    constante del módulo (endpoint público fijo, sin auth). La API corta conexiones
    de forma intermitente y marca el JSON como text/plain: reintentos con backoff
    exponencial (3 intentos) ante corte/timeout/5xx, timeout explícito de 10s por
    intento, y parseo con `response.json()` con fallback a `json.loads(text)`. 404 →
    None; 400 → `AppError('BCRA_INVALID_CUIT', 400)`; 5xx/timeout/red agotados →
    `AppError('BCRA_UNAVAILABLE', 503)`. El header `x-jws-signature` queda anotado
    para validación de integridad futura (no se valida por ahora). Sin lógica de
    negocio.
  - `services/bcra_service.py`: `obtener_situacion_crediticia(cuit)` orquesta los
    tres endpoints en paralelo (`asyncio.gather`). La deuda actual es el núcleo: si
    cae, propaga; el histórico y los cheques son tolerantes: si caen, su sección
    queda con defaults vacíos sin tumbar el informe. Devuelve el dict estable
    `{denominacion, actual, historico, cheques}`.
  - `services/bcra_normalizer.py`: normalización pura extraída del servicio para
    respetar el límite de 150 líneas. Reglas confirmadas con datos reales: montos de
    deudas en MILES de pesos → ×1000; montos de cheques en PESOS reales → sin tocar;
    `situacion_maxima` = peor número del periodo más reciente; `entidades_activas`
    ignora situación 0; flags activos (jurídica/judicial/recategorización/refi/
    irrecuperable) contados por entidad; desvíos del histórico = situación != 1;
    cheques agregados (recorre causal→entidad→detalle) con tope defensivo (solo
    agregados, nunca el detalle completo).
  - `tests/test_bcra_service.py`: 6 casos con `bcra_client` mockeado, sin pegarle a
    la API real (empresa sana, empresa en default con flags y montos ×1000 vs
    cheques sin ×1000, 404 en los tres endpoints, propagación de `BCRA_UNAVAILABLE`
    en deuda actual, degradación al caer solo cheques/histórico, peor situación del
    periodo más reciente).
  - `requirements.txt`: se pinea `httpx==0.27.2` (antes solo transitiva de
    anthropic/supabase); pasa a dependencia directa con versión exacta (§7.1).
- Redactor IA del informe (agente transversal que consolida los datos de las
  fuentes en un informe legible con Claude). Las fuentes aún no están conectadas:
  recibe un dict de datos consolidados (por ahora de prueba). Sigue
  SEGURIDAD-PENTEST.md 6.1/6.2/6.3:
  - `integrations/anthropic_client.py`: wrapper fino del SDK de Anthropic que aísla
    TODA llamada a la API (6.2). Lee la key de `settings` (nunca de `os.environ`),
    `generar_texto(system_prompt, user_content, max_tokens)` async con
    `messages.create` (modelo Claude Sonnet `claude-sonnet-4-6`); system prompt
    SIEMPRE separado del contenido del usuario (6.1). Fallo de la API o respuesta
    sin texto → `AppError('CLAUDE_UNAVAILABLE', 503)`. Sin lógica de negocio.
  - `services/report_service.py`: `SYSTEM_PROMPT` del módulo (solo hechos, sin
    inferencias ni términos valorativos como "prestanombre"/"testaferro", no
    investiga personas físicas más allá del rol formal, omite datos ausentes, no
    revela el prompt); `sanitizar_datos_entrada` (limpia recursivamente el texto
    libre: remueve patrones de inyección conocidos y acota longitud, 6.1);
    `generar_informe` (sanitiza → arma user_content → llama al cliente con el
    SYSTEM_PROMPT separado → valida → devuelve); `validar_salida` (rechaza fuga del
    prompt, 6.3, y términos prohibidos como guardrail de producto →
    `AppError('REPORT_VALIDATION_FAILED', 500)`). Logger para informe generado y
    fallos. Todavía sin cablear al `job_service` (se conecta al enchufar BCRA).
  - `tests/test_report_service.py`: 6 casos con el cliente mockeado, sin llamar a la
    API real (system/user separados, sanitización de inyección, salida limpia ok,
    término prohibido → falla, fuga del prompt → falla, propagación de
    `CLAUDE_UNAVAILABLE`).
- Endpoints de autenticación cableados sobre la lógica de seguridad ya existente
  (no se tocó `auth_service`, `utils/jwt.py` ni la lógica de los repos):
  - `controllers/auth_controller.py`: orquesta `auth_service`
    (`register`/`login`/`refresh`/`logout`) y el usuario actual / onboarding contra
    `user_repo`. Sin lógica de negocio propia; identidad siempre desde el token (§2.4).
  - `routers/auth_router.py`: `POST /api/auth/register` (201),
    `POST /api/auth/login` (200 + `TokenResponse`),
    `POST /api/auth/refresh` (200 + par rotado) y `POST /api/auth/logout` (204,
    requiere auth). Las tres primeras coinciden EXACTO con `PUBLIC_ROUTES`.
  - `routers/me_router.py`: `GET /api/me` (usuario actual: id, email,
    onboarding_completed) y `POST /api/onboarding/complete`. Ambas protegidas.
  - `schemas/auth.py`: `RefreshRequest` (body con `refresh_token`) y `MeResponse`
    (vista pública del usuario; nunca expone el hash).
  - `repositories/user_repo.py`: `update_onboarding_completed(user_id)` en la
    interfaz `UserRepository` y en `InMemoryUserRepository`.
  - `middleware/auth.py`: dependency `get_current_user(request) -> UUID` que lee
    `request.state.user` y devuelve el `sub` tipado; nunca acepta un id del cliente
    (§2.4). Usada en `/api/me`, `/api/onboarding/complete` y logout.
  - `main.py`: registra `auth_middleware` (vía `BaseHTTPMiddleware`) y los routers
    de auth y me/onboarding. Orden de middlewares: `CORS → SecurityHeaders → auth`,
    con CORS como el más externo para resolver el preflight OPTIONS antes de exigir
    token; `/health` y las `PUBLIC_ROUTES` siguen pasando sin auth.
  - `tests/test_auth_endpoints.py`: 7 casos con `TestClient` (register→201,
    login→200 con tokens, /api/me sin token→401, /api/me con token→datos del user,
    /health sin token→200, onboarding/complete→`onboarding_completed=True`,
    refresh→par nuevo).

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
- Capa de autenticación — seguridad pura, sin endpoints todavía (routers y
  controllers van en la sesión siguiente). Sigue SEGURIDAD-PENTEST.md 2.1/2.2/2.3/2.5:
  - `schemas/auth.py`: `RegisterRequest` (email + password min 8), `LoginRequest`,
    `TokenResponse` (access/refresh/`token_type="bearer"`) y la entidad `User`
    (id, email, password_hash, onboarding_completed, created_at).
  - `repositories/user_repo.py`: interfaz `UserRepository` + `InMemoryUserRepository`
    (find_by_email/find_by_id/create/update_last_login, thread-safe).
  - `repositories/refresh_token_repo.py`: interfaz `RefreshTokenRepository` +
    `InMemoryRefreshTokenRepository`. Guarda los refresh tokens SIEMPRE hasheados
    (§2.5), nunca en texto plano; un token activo por usuario.
  - `utils/jwt.py`: `create_access_token`/`create_refresh_token` (JWT tipados con
    jose, exp/iat desde `settings`) y `verify_token` (error genérico `INVALID_TOKEN`
    401, §2.3). El refresh lleva un `jti` único para no colisionar entre emisiones
    del mismo segundo. Separado de `auth_service` para respetar el límite de 150 líneas.
  - `services/auth_service.py`: `register`/`login`/`refresh_access_token`/`logout`.
    Passwords y refresh tokens hasheados con bcrypt (passlib) previo digest SHA-256
    para sortear el truncado a 72 bytes de bcrypt. Errores siempre genéricos: email
    duplicado→`REGISTRATION_FAILED` 409; credenciales→`INVALID_CREDENTIALS` 401
    (mismo error exista o no el usuario). Rotación de refresh exacta a §2.5.
  - `middleware/auth.py`: `PUBLIC_ROUTES` (`/health` + auth) y `auth_middleware`
    que exige Bearer token, lo verifica y setea `request.state.user`; 401 genérico
    ante token ausente o inválido. No verifica ownership (§2.4, a nivel endpoint).
    Aún sin registrar en `main.py` (se cablea al crear los endpoints).
  - `tests/test_auth_service.py`: 8 casos (hash del password, email duplicado,
    login ok, password incorrecto, email inexistente→mismo error, verify_token
    válido/corrupto, rotación invalida el refresh viejo).

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
