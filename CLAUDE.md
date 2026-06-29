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
- Redactor IA del informe = analista experto en BCRA Central de Deudores (agente
  transversal, fuentes aún sin conectar): `integrations/anthropic_client.py` (wrapper
  fino del SDK, aísla la API §6.2; key de `settings`; `generar_texto` con system
  separado del user §6.1; fallo → `CLAUDE_UNAVAILABLE` 503),
  `services/prompts/bcra_analista.py` (`SYSTEM_PROMPT` extraído del service por el
  límite de 150 líneas y como único lugar auditable §6.1: traduce los datos, opina
  SOBRE LOS DATOS con glosario de situaciones 0-5 y flags, pero NUNCA recomienda una
  DECISIÓN al usuario) y `services/report_service.py` (`_construir_user_content` arma
  el user_content desde el dict normalizado de `bcra_service` —denominacion/actual/
  historico/cheques— por sección en JSON §6.1; `sanitizar_datos_entrada`;
  `generar_informe`; `validar_salida` §6.3 verifica fuga del prompt + términos
  valorativos + patrones de recomendación de decisión → `REPORT_VALIDATION_FAILED`
  500). Sin cablear al `job_service` todavía (se conecta al enchufar BCRA) + tests
  (9/9, cliente mockeado).
- Collector de BCRA Central de Deudores (primera fuente real, fuentes-a-pipeline aún
  sin cablear): `integrations/bcra_client.py` (transporte httpx async que aísla la
  API §6.2; `consultar_deudas`/`consultar_historicas`/`consultar_cheques`, cada una
  devuelve `results` o None en 404; base URL pública fija; reintentos con backoff
  exponencial 3x ante corte/timeout/5xx, timeout 10s/intento; parseo `.json()` con
  fallback `json.loads(text)` por el text/plain del BCRA; 400 → `BCRA_INVALID_CUIT`,
  5xx/red agotados → `BCRA_UNAVAILABLE` 503; header `x-jws-signature` anotado para
  validación futura), `services/bcra_service.py` (`obtener_situacion_crediticia`
  orquesta los tres endpoints con `asyncio.gather`; deuda actual = núcleo que
  propaga, histórico/cheques se degradan a vacío si caen) y
  `services/bcra_normalizer.py` (normalización pura extraída por el límite de 150
  líneas: deudas ×1000 = pesos reales, cheques sin ×1000, `situacion_maxima` peor del
  periodo reciente, `entidades_activas` ignora situación 0, flags por entidad,
  desvíos = situación != 1, cheques agregados con tope defensivo). Se pinea
  `httpx==0.27.2` (§7.1, antes solo transitiva) + tests (6/6, `bcra_client` mockeado).
- Pipeline real cableado en `services/job_service.py` (`_ejecutar_pipeline` reemplaza
  el stub del placeholder): resuelve el BCRA por caché (`cache_service`) —HIT usa lo
  cacheado sin golpear la fuente; MISS consulta `bcra_service` y cachea el normalizado
  (`TTL_BCRA`) ANTES de redactar, para que un reintento no vuelva al BCRA si cae el
  informe— y pasa los datos a `report_service.generar_informe`. Devuelve `{cuit,
  denominacion, datos_bcra, informe, fuente_cache}`. Errores (los envuelve
  `procesar_job`, que marca ERROR con el `code` del `AppError`): `BCRA_UNAVAILABLE`/
  `BCRA_INVALID_CUIT` → ERROR sin cachear; `CLAUDE_UNAVAILABLE`/
  `REPORT_VALIDATION_FAILED` → ERROR con el BCRA ya cacheado. No se crearon fuentes
  nuevas, solo se consumen los services existentes + tests (8/8, `bcra_service` y
  `report_service` mockeados; caché en memoria reseteada por test).
- `frontend_prueba/index.html` (TEMPORAL, solo validación manual de la Entrega 1):
  HTML vanilla feo a propósito (sin build/frameworks/CDN) que hace `POST /consultas`
  + polling de `GET /consultas/{job_id}` con estados de carga/error/done. Para que
  funcione sin auth se agregaron DOS bypass de desarrollo, ambos condicionales a
  `app_env == "development"` (en prod no aplican): en `middleware/auth.py`,
  `_is_dev_bypass` deja pasar `/consultas` y `/consultas/{job_id}` sin token; en
  `main.py`, CORS suma `http://localhost:5500` y `http://127.0.0.1:5500` (nunca
  `"*"`). Todo esto es scratch de prueba y se quita antes de producción.
- **Sesión ARCA — COMPLETA.** Segundo agente (fuente cuitonline.com, scraping HTML),
  mismo patrón de 4 capas que el BCRA, con su informe INDEPENDIENTE (el unificador los
  cruza en la Sesión 9): `integrations/arca_client.py` (transporte httpx async que
  aísla cuitonline §6.2; headers de browser real, timeout 15s, retry 3× backoff `1s·2^n`,
  rate limit defensivo ≥1s entre requests al mismo host, `follow_redirects=True`;
  `construir_url(cuit, razon_social)` arma la URL del detalle directamente
  (`/detalle/{cuit}/{slug}.html`, slug url-friendly de la razón social: minúsculas, sin
  acentos, espacios→guiones, sin otros símbolos) y `obtener_constancia` baja y parsea esa
  URL; 404→None, 429/403→`ARCA_RATE_LIMITED` 503, 5xx/timeout/red→`ARCA_UNAVAILABLE` 503,
  persona física→`ARCA_PERSONA_FISICA` 422), `integrations/arca_parser.py` (parseo extraído
  por el límite de 100 líneas del client; el body del detalle está bajo paywall de adblocker,
  así que los datos se leen SOLO de los meta tags: `<meta name="description">` —campos
  separados por un punto medio que cuitonline sirve corrupto y llega como U+FFFD (el split
  acepta U+FFFD y `·`): razón social, CUIT, tipo de persona, domicilio, localidad, fecha de
  contrato, Ganancias/IVA por prefijo— y `<meta name="keywords">` —empleador y tipo de
  persona—; calibrado contra datos reales, ej. CUIT 30549738644), `services/arca_service.py`
  (`obtener_datos_arca(cuit, razon_social)` orquesta construir_url→constancia→normalizar;
  detalle inexistente (404 → raw None) → `ARCA_CUIT_NOT_FOUND` 404), `services/arca_normalizer.py` (puro: razon_social
  title-case, estado→activo/inactivo/dado_de_baja, es_empleador bool, fecha→ISO 8601 o None,
  regimenes [{nombre, fecha_desde}], `nivel_alerta` alto/medio/bajo) y
  `services/prompts/arca_analista.py` (system prompt experto fiscal/societario, 4 secciones,
  máx 400 palabras, sin recomendar decisiones comerciales). El informe ARCA vive en
  `services/report_arca.py` (`generar_informe_arca` + `validar_salida_arca`), NO en
  `report_service.py` —que ya estaba en 149/150 líneas—, reutilizando su
  `sanitizar_datos_entrada`. Cableado en `_ejecutar_pipeline` DESPUÉS del bloque BCRA con
  caché propia (`TTL_ARCA`): ARCA es complementario y **degrada sin tumbar el job** (si falta
  la razón social, o la fuente/el redactor caen, el informe BCRA se conserva y ARCA queda en
  None con el error anotado). Como la URL de ARCA necesita la razón social, el bloque la exige:
  si `job.razon_social` es None/vacía degrada con `ARCA_NO_RAZON_SOCIAL` sin consultar la
  fuente. El resultado del job es `{cuit, denominacion, datos_bcra, informe_bcra,
  fuente_cache_bcra, datos_arca, informe_arca, fuente_cache_arca, arca_error}`. Se pinea
  `beautifulsoup4==4.12.3` (§7.1) + tests (test_arca_service: service mockeado + slug de
  `construir_url` + 2 de parser contra el meta real de CRISTEM; test_job_service: degradado
  por fuente caída y por razón social ausente). Suite total 62/62.
  - **Corrección post-prueba real (Sesión ARCA.1):** la prueba contra cuitonline reveló
    que `/search.html?q={cuit}` daba 404 (no existe) y que el body del detalle está
    bloqueado por paywall. Se reemplazó la búsqueda por el redirect de `/constancia/{cuit}`
    y el parseo del body por el de meta tags; se eliminó `extraer_url_resultado`.
  - **Corrección post-prueba real (Sesión ARCA.2):** `/constancia/{cuit}` también daba 404.
    Se eliminó `buscar_cuit` y se reemplazó por `construir_url(cuit, razon_social)`, que arma
    `/detalle/{cuit}/{slug}.html` directamente desde la razón social (sin request previo).
    `obtener_datos_arca` pasa a requerir `razon_social`; `ARCA_NO_DATA` desaparece (raw None
    ahora → `ARCA_CUIT_NOT_FOUND`) y el job degrada con `ARCA_NO_RAZON_SOCIAL` si no hay razón
    social. Detalle en CHANGELOG.
  - **Corrección post-prueba real (Sesión ARCA.3):** el parser no separaba los campos:
    cuitonline sirve el separador `·` corrupto (bytes EF BF BD), que al decodificar UTF-8
    llega como U+FFFD y es irrecuperable desde los bytes, así que `split(" · ")` dejaba todo
    el string en `razon_social`. El split pasa a un regex que acepta U+FFFD (lo real) y `·`
    (fallback), armado con `chr()` para no meter caracteres no-ASCII en el fuente. Además se
    propaga `localidad` en `arca_normalizer.normalizar` (antes se descartaba) — excepción
    autorizada a la restricción de archivos. Fixture del test reconstruida con el separador
    real (U+FFFD). Detalle en CHANGELOG.
- **Sesión BORA — COMPLETA.** Tercer agente (fuente dateas.com, scraping HTML), mismo patrón
  de 4 capas que ARCA, informe INDEPENDIENTE: `integrations/bora_client.py` (transporte httpx
  igual a ARCA; `construir_url(cuit, razon_social)` → `/es/empresa/{slug}-{cuit}` usando
  `utils.slug.generar_slug`; `obtener_datos` baja y delega en el parser; 404→None,
  429/403→`BORA_RATE_LIMITED` 503, 5xx/timeout→`BORA_UNAVAILABLE` 503),
  `integrations/bora_parser.py` (BeautifulSoup; tres bloques confirmados con datos reales: dos
  `table.entity-table-vertical` —Datos Básicos y ARCA, filas th/td, se remueven links como
  "Ver Informe Completo"— y `div.search-result` por publicación —título, url, snippet, fecha
  dd/mm/aaaa→ISO y sección parseadas del título, máx 10—; devuelve strings crudos),
  `services/bora_service.py` (`obtener_datos_bora(cuit, razon_social)`; sin página (404 → raw
  None) → `BORA_CUIT_NOT_FOUND` 404), `services/bora_normalizer.py` (puro: razon_social
  title-case, ganancias/iva/monotributo "Activo/Inactivo/No Inscripto"→activo/inactivo/
  no_inscripto, empleador "Si"→bool, publicaciones ordenadas por fecha desc máx 10,
  `nivel_alerta` alto si hay "concurso"/"quiebra" en título o snippet, medio si hay
  publicaciones, bajo si no; `alertas_criticas` = las que dispararon alto) y
  `services/prompts/bora_analista.py` (experto societario/boletines, 4 secciones, máx 400
  palabras, sin recomendar). Informe en `services/report_bora.py` (`generar_informe_bora` +
  `validar_salida_bora` que además rechaza afirmar concurso/quiebra sin respaldo en los datos,
  con guard anti-falsos-positivos por negación). Slug extraído a `utils/slug.py` (compartido;
  ARCA conserva su copia inline por la restricción de no tocar `arca_*`). El pipeline se
  **extrajo de `job_service` a `services/pipeline_service.py`** (job_service quedaba en 150/150):
  `ejecutar_pipeline` resuelve BCRA (núcleo) y luego ARCA y BORA vía `_resolver_complementaria`
  (helper genérico: caché propia, degrada con `{FUENTE}_NO_RAZON_SOCIAL` si falta razón social,
  o con el error de la fuente, sin tumbar el job). El resultado suma `datos_bora`, `informe_bora`,
  `fuente_cache_bora`, `bora_error` (`TTL_BORA`=7d). Tests: `test_bora_service` (11: slug,
  service mockeado, normalizer niveles/empleador, parser sobre HTML fixture real) +
  `test_job_service` migrado a mockear `pipeline_service` y caso `bora_sin_razon_social`.
  Suite total 73/73. Validado end-to-end contra dateas real (CUIT 30549738644: 3 publicaciones).

**Pendiente:** persistencia real (`SupabaseJobRepository`/`SupabaseUserRepository`),
rate limiting, migraciones SQL con RLS, más tests del flujo de informe, **unificador
BCRA+ARCA+BORA (Sesión 9)**. Ver `ARCHITECTURE.md` para la deuda técnica.

**Deuda técnica detectada en la Sesión ARCA:**
- **Parser de cuitonline ahora desde meta tags (calibrado parcial):** tras la corrección
  Sesión ARCA.1, `arca_parser.py` lee de `<meta name="description">` y `keywords`, con
  tests contra el meta real de CRISTEM. Limita lo disponible: el meta NO trae
  estado_inscripcion, regímenes ni actividad económica, así que esos campos quedan en
  None/[] y `nivel_alerta` cae a "medio" por defecto. Falta validar con más empresas
  (variaciones de orden/ausencia de campos en el description) y, si se necesitan los
  campos faltantes, encontrar otra fuente (el body sigue bajo paywall).
- **`construir_url` depende de que el slug coincida EXACTO con el de cuitonline:** el slug se
  genera desde la razón social que envía el usuario; si difiere del que usa cuitonline (orden
  de palabras, abreviaturas, puntuación atípica), la URL da 404 → ARCA_CUIT_NOT_FOUND aunque
  la empresa exista. Validar el algoritmo de slug con un set amplio de empresas reales.
- **`frontend_prueba/index.html` quedó desfasado:** lee `resultado.informe` y
  `resultado.fuente_cache`, que pasaron a llamarse `informe_bcra`/`fuente_cache_bcra`. No
  crashea (JS muestra vacío), pero no renderiza el informe ni el bloque ARCA. Es scratch
  temporal (no se tocó por consigna); actualizar o descartar al armar el front real.
- **Informe ARCA partido en `report_arca.py`:** la consigna pedía `generar_informe_arca`
  dentro de `report_service.py`, pero ese archivo estaba en 149/150 líneas. Se movió a un
  módulo propio (criterio: límite de líneas no negociable). Si más adelante se unifican los
  redactores, conviene revisar esta separación.
- **Scraping frágil por naturaleza:** cuitonline/dateas pueden cambiar el HTML o endurecer el
  anti-scraping (Cloudflare, captcha). El rate limit es global de proceso (`time.monotonic`
  en memoria); con múltiples instancias/workers no se coordina entre procesos.

**Deuda técnica detectada en la Sesión BORA:**
- **Slug duplicado:** `utils/slug.generar_slug` es la versión compartida (la usa `bora_client`),
  pero `arca_client.construir_url` conserva su slug inline porque la consigna prohibía tocar
  `arca_*`. Unificar ARCA sobre `utils/slug` cuando se pueda tocar ese archivo. Igual que ARCA,
  `bora_client.construir_url` depende de que el slug coincida EXACTO con el de dateas.
- **Parser de dateas por índice de tabla:** `bora_parser` asume tabla[0]=básicos, tabla[1]=ARCA
  (hay exactamente dos `entity-table-vertical`). Si dateas agrega/reordena tablas, el mapeo se
  rompe; convendría anclar cada tabla a su `<h2>`. Validado solo contra una empresa (CRISTEM).
- **`validar_salida_bora` (no-inventar concurso/quiebra) es best-effort:** usa regex con guard
  de negación `(?<!no )`; otras negaciones ("tampoco", "sin") podrían dar falsos positivos/negativos.
- **`pipeline_service` cubierto solo vía `test_job_service`:** no tiene tests unitarios propios;
  los casos del pipeline (incl. degradación ARCA/BORA) se ejercen a través de `procesar_job`.
