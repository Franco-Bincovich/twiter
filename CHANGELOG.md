# Changelog

Formato basado en commits convencionales (ver ORDEN-Y-LEGIBILIDAD.md sección 8).

## [Sin publicar]

### Fixed

- Agente ARCA — tercera corrección tras prueba real (Sesión ARCA.3): el parser no
  separaba los campos del meta description y `razon_social` se quedaba con TODO el string
  (el resto en None).
  - **Causa:** cuitonline sirve el separador `·` corrupto en origen (bytes `EF BF BD`).
    httpx decodifica el body como UTF-8 (charset declarado), así que esos bytes llegan como
    U+FFFD (replacement char) y son irrecuperables desde los bytes. El `descripcion.split(" · ")`
    no encontraba el `·` y devolvía un solo elemento.
  - **`integrations/arca_parser.py`:** el split pasa a un regex `_SEPARADOR` que acepta
    U+FFFD (lo que realmente llega) y U+00B7 `·` (fallback por si lo corrigen), 1+ veces y
    comiéndose los espacios alrededor. El patrón se arma con `chr(0xFFFD)`/`chr(0x00B7)` para
    no introducir caracteres no-ASCII en el fuente. El resto del parseo (mapeo por prefijo,
    keywords) no cambia.
  - **`services/arca_normalizer.py`** (excepción autorizada a la restricción de archivos):
    `normalizar` ahora propaga `localidad` (`raw.get("localidad")`), que antes se descartaba;
    se recortó 1 línea del docstring para mantener el límite de 100. El script de validación
    end-to-end (razon_social/localidad/fecha/tipo_persona contra cuitonline real) pasa.
  - **`tests/test_arca_service.py`:** la fixture `HTML_CRISTEM` se reconstruye con el
    separador REAL (U+FFFD, vía `chr(0xFFFD)`) para reproducir el bug; el test de parser
    verifica que `razon_social` queda solo con el nombre y que cada campo (incl. `localidad`)
    se separa bien; el test de servicio verifica `localidad` en el dict normalizado. 62/62.

- Agente ARCA — segunda corrección tras prueba real (Sesión ARCA.2): `/constancia/{cuit}`
  también devuelve 404. La URL que responde 200 es `/detalle/{cuit}/{slug}.html`, donde el
  slug es la razón social en formato url-friendly.
  - **`integrations/arca_client.py`:** se eliminó `buscar_cuit(cuit)` y se reemplazó por
    `construir_url(cuit, razon_social) → str` (función pura, sin request): arma la URL del
    detalle generando el slug desde la razón social (minúsculas, acentos transliterados a
    ASCII, espacios→guiones, se elimina lo que no sea letra/número/guion, guiones colapsados
    y stripeados). Ej.: "CRISTEM S A" → `cristem-s-a`; "CLINICA PRIVADA RANELAGH S.A." →
    `clinica-privada-ranelagh-sa`. `obtener_constancia(url)` no cambia.
  - **`services/arca_service.py`:** `obtener_datos_arca` pasa a recibir `razon_social` como
    parámetro obligatorio; usa `construir_url` (ya no `await buscar_cuit`). `raw is None`
    (detalle inexistente) ahora → `ARCA_CUIT_NOT_FOUND` (404); desaparece `ARCA_NO_DATA`
    (ya no hay un paso de búsqueda separado del de detalle).
  - **`services/job_service.py`:** el bloque ARCA de `_ejecutar_pipeline` llama
    `obtener_datos_arca(cuit, job.razon_social)`. Si `job.razon_social` es None/vacía,
    degrada ARCA a None con `arca_error {code: "ARCA_NO_RAZON_SOCIAL"}` sin consultar la
    fuente ni lanzar (mismo patrón de degradación ya existente). BCRA no se toca.
  - **`tests/`:** `test_arca_service.py` mockea solo `obtener_constancia` (ya no
    `buscar_cuit`), pasa `razon_social` en las llamadas, agrega `test_construir_url_genera_slug`
    (valida los dos ejemplos de slug) y elimina el test de `ARCA_NO_DATA` (path inexistente).
    `test_job_service.py`: los tests de pipeline que esperan ARCA pasan razón social, y se
    agrega `test_pipeline_arca_sin_razon_social_degrada` (ARCA_NO_RAZON_SOCIAL, fuente nunca
    consultada). Suite total 62/62.

- Agente ARCA — corrección tras la primera prueba real contra cuitonline.com (Sesión
  ARCA.1). La prueba reveló dos supuestos equivocados del scraping inicial:
  - **`buscar_cuit` ya no usa `/search.html?q={cuit}`** (esa URL devuelve 404, no existe).
    Ahora la URL del detalle se resuelve por el redirect de `/constancia/{cuit}`: el
    cliente hace GET con `follow_redirects=True` y toma `respuesta.url` (que queda apuntando
    a `/detalle/{cuit}/{slug}.html` con el slug real). 404 → None. Se agregó
    `follow_redirects=True` al `AsyncClient` de `_get`.
  - **`extraer_constancia` ya no parsea el body** (está bloqueado por un paywall de
    adblocker). Ahora lee ÚNICAMENTE los meta tags: de `<meta name="description">` (campos
    separados por " · ") saca razón social, CUIT, tipo de persona, domicilio, localidad,
    fecha de contrato social y Ganancias/IVA (por prefijo, defensivo ante campos ausentes o
    en otro orden); de `<meta name="keywords">` saca `es_empleador` (bool) y confirma el
    tipo de persona. `es_persona_fisica` ahora evalúa el `tipo_persona` parseado.
  - Se **eliminó `extraer_url_resultado`** (ya no se busca; la URL viene del redirect).
  - Consecuencia de datos: el meta NO trae estado de inscripción, regímenes ni actividad
    económica; esos campos quedan en None/[] y `nivel_alerta` cae a "medio" por defecto
    (ver deuda técnica en CLAUDE.md).
  - `tests/test_arca_service.py`: se actualizó el fixture `RAW` a los campos reales que
    devuelve el parser desde el meta (datos de CRISTEM S.A.) y las aserciones del caso
    válido; se agregaron 2 tests de parser que ejercen `extraer_constancia` contra el meta
    real (persona jurídica con empleador, y detección de persona física). `arca_normalizer`,
    `report_*` y `job_service` no se tocaron. Suite total 61/61.

### Added

- Agente ARCA (segunda fuente real del producto): datos de inscripción fiscal/societaria
  de una empresa desde cuitonline.com (scraping HTML). Mismo patrón de 4 capas que el
  BCRA, con informe **independiente** (el unificador cruza BCRA+ARCA en la Sesión 9).
  - `integrations/arca_client.py`: wrapper de transporte con httpx async que aísla TODA
    llamada a cuitonline (SEGURIDAD-PENTEST.md 6.2). `buscar_cuit` (busca en
    `/search.html?q=` y devuelve la URL del detalle exacto, o None) y `obtener_constancia`
    (GET del detalle → campos crudos, o None en 404). Headers de browser real (anti-bloqueo),
    timeout 15s, reintentos 3× con backoff exponencial `1s·2^n`, y rate limit defensivo
    (≥1s entre requests al mismo host, serializado con un lock). 404 → None; 429/403 →
    `AppError('ARCA_RATE_LIMITED', 503)`; 5xx/timeout/red agotados → `ARCA_UNAVAILABLE` 503;
    persona física → `ARCA_PERSONA_FISICA` 422. Sin lógica de negocio.
  - `integrations/arca_parser.py`: parseo con BeautifulSoup extraído del client por el
    límite de 100 líneas. `extraer_url_resultado`, `extraer_constancia` y `es_persona_fisica`.
    Estrategia defensiva por etiqueta. ADVERTENCIA: selectores best-effort NO calibrados
    contra el HTML real (los tests mockean el client); calibrar antes de producción.
  - `services/arca_service.py`: `obtener_datos_arca(cuit)` orquesta buscar → constancia →
    normalizar. Sin URL → `ARCA_CUIT_NOT_FOUND` 404; detalle sin datos → `ARCA_NO_DATA` 404.
  - `services/arca_normalizer.py`: normalización pura (patrón de `bcra_normalizer`):
    razon_social title-case, estado_inscripcion → activo/inactivo/dado_de_baja, es_empleador
    a bool, fecha_contrato_social → ISO 8601 (o None si no se reconoce), regimenes →
    [{nombre, fecha_desde}], y `nivel_alerta` (alto = baja, medio = inactivo, bajo = activo;
    medio ante estado desconocido).
  - `services/prompts/arca_analista.py`: system prompt aislado (experto fiscal y societario,
    ex AFIP). Informe en 4 secciones (situación registral, perfil fiscal, perfil laboral,
    observaciones), máx 400 palabras; no recomienda decisiones comerciales ni inventa datos
    ausentes (los marca "no disponible").
  - `services/report_arca.py` (módulo nuevo): `generar_informe_arca` y `validar_salida_arca`
    (versión ARCA sin los guardrails crediticios del BCRA: fuga de prompt + recomendaciones
    de decisión comercial). Vive aparte de `report_service.py` porque ese archivo ya estaba
    en 149/150 líneas; reutiliza su `sanitizar_datos_entrada` (source-agnostic).
  - `requirements.txt`: se agrega `beautifulsoup4==4.12.3` (nueva dependencia directa, §7.1).
  - `tests/test_arca_service.py`: 9 casos con `arca_client` mockeado, sin pegarle a
    cuitonline (CUIT válido, no encontrado, sin datos en detalle, fuente caída; normalizador:
    estado activo/dado_de_baja, fecha a ISO, nivel_alerta, estructura de regímenes).

### Changed

- `services/job_service.py`: `_ejecutar_pipeline` suma el bloque ARCA después del BCRA, con
  su propia caché (`TTL_ARCA`). ARCA es complementario e independiente: si la fuente o el
  redactor de ARCA fallan, el job **degrada sin tumbarse** (el informe BCRA ya generado se
  conserva; `datos_arca`/`informe_arca` quedan en None y `arca_error` lleva `{message, code}`).
  El resultado del job pasa de `{..., informe, fuente_cache}` a `{cuit, denominacion,
  datos_bcra, informe_bcra, fuente_cache_bcra, datos_arca, informe_arca, fuente_cache_arca,
  arca_error}` (se renombran las claves BCRA por simetría con las de ARCA).
  - `tests/test_job_service.py`: los tests de pipeline que llegan al bloque ARCA ahora
    mockean `arca_service` y `report_arca` (sin llamadas reales); se ajustan las aserciones
    a las claves renombradas y se agrega un caso de **degradado de ARCA** (job DONE con
    informe BCRA conservado y `arca_error` anotado). Suite total 59/59.
  - NOTA: `frontend_prueba/index.html` (scratch temporal, no se tocó por consigna) quedó
    desfasado: leía `resultado.informe`/`.fuente_cache`, ahora `informe_bcra`/`fuente_cache_bcra`.
    No crashea, pero no renderiza el informe ni ARCA; actualizar o descartar al armar el front real.

- `frontend_prueba/index.html` (TEMPORAL — solo validación manual de la Entrega 1):
  un único HTML vanilla (CSS+JS inline, sin frameworks, sin build, sin CDN), feo a
  propósito. Input de CUIT + botón "Consultar": hace `POST /consultas`, luego polling
  `GET /consultas/{job_id}` cada 1.5s (máx 20 intentos → timeout). Estados UX mínimos
  (UX-UI.md): "Consultando..." en pending/processing; en done muestra denominación +
  informe y los `datos_bcra` crudos en un `<details>`/`<pre>` colapsable; en error
  muestra `message` + `code` en rojo. Maneja 400/422 del POST sin romper. No tiene
  tests (es scratch manual). Quitar junto con los bypass de desarrollo abajo.
- Modo prueba en backend (SOLO `app_env == "development"`, para habilitar el front):
  - `middleware/auth.py`: bypass de auth para `/consultas` y `/consultas/{job_id}`
    (`_is_dev_bypass`), condicional a development. En prod (`app_env != development`)
    esas rutas siguen exigiendo Bearer. Comentado como bypass que NO debe quedar en
    prod; nunca es público de forma permanente. Loguea un warning en cada bypass.
  - `main.py`: en development se agregan `http://localhost:5500` y
    `http://127.0.0.1:5500` a los orígenes CORS (front de prueba); en prod no se
    agregan. No se usa `"*"`.

- `services/job_service.py`: se cablea el pipeline real en `_ejecutar_pipeline`,
  reemplazando el stub que devolvía `{"placeholder": "sin fuentes conectadas aún"}`.
  El job ahora resuelve el BCRA por caché (`cache_service`): con HIT usa lo cacheado
  y no golpea la fuente; con MISS consulta `bcra_service.obtener_situacion_crediticia`
  y guarda el resultado normalizado (`TTL_BCRA`) **antes** de redactar, para que un
  reintento no vuelva a pegarle al BCRA si falla el informe. Luego pasa los datos a
  `report_service.generar_informe` y devuelve `{cuit, denominacion, datos_bcra,
  informe, fuente_cache}`. No se crearon fuentes nuevas: solo se consumen los services
  existentes (`bcra_service`, `cache_service`, `report_service`, `cuit_service`).
  - Manejo de errores (lo envuelve `procesar_job`, que marca el job en ERROR con el
    `code` del `AppError`): `BCRA_UNAVAILABLE`/`BCRA_INVALID_CUIT` (cae la deuda
    actual) → ERROR sin cachear nada; `CLAUDE_UNAVAILABLE`/`REPORT_VALIDATION_FAILED`
    → ERROR pero con los datos del BCRA ya cacheados.
  - `tests/test_job_service.py`: el test del placeholder se reemplaza por casos del
    pipeline real (mockeando `bcra_service` y `report_service`, sin API real): cache
    MISS (consulta + cachea + informe, `fuente_cache` False), cache HIT (no consulta,
    `fuente_cache` True), `BCRA_UNAVAILABLE` (ERROR sin cachear) y fallo de informe
    (ERROR con BCRA cacheado, verificado por HIT en el reintento). 8 casos.

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
