# Bases de Desarrollo — Agencia

> Este documento es la constitución de todos los productos digitales de la agencia.
> Todo proyecto nuevo — SaaS, microsistema o herramienta interna — nace desde estas bases.
> Un proyecto que las respeta es mantenible, escalable, seguro y puede correr solo.
> Stack: Python · FastAPI · React · Next.js · Supabase · Anthropic · AWS

---

## Por qué existen estas bases

La agencia construye productos digitales que tienen que funcionar con mínima intervención humana.
Eso significa que cuando algo falla, el sistema tiene que detectarlo, registrarlo y en lo
posible recuperarse solo. Y cuando un desarrollador tiene que intervenir, tiene que poder
orientarse en el código sin depender de quien lo escribió.

Estas bases son los cimientos que hacen posible ese modelo de negocio.
No son opcionales — son lo que diferencia un producto profesional de un prototipo.

Este documento se divide en tres secciones:
- **Las 10 bases universales** — aplican siempre, sin importar cómo se desarrolle
- **Bases de desarrollo manual** — reglas para cuando se escribe código a mano
- **Bases de vibe coding** — reglas para cuando se desarrolla con IA (Claude, Claude Code, Claude Design)

Documentos complementarios:
- **SEGURIDAD-PENTEST.md** — seguridad, autenticación y vulnerabilidades
- **ORDEN-Y-LEGIBILIDAD.md** — estructura de código, naming y herramientas

---

# Sección 1 — Las 10 bases universales

---

### Base 1 — Arquitectura por capas

Cada parte del sistema tiene una responsabilidad única y no invade la de las demás.
Esta separación permite modificar una capa sin romper las otras, y es lo que hace que
el sistema escale sin volverse inmanejable.

#### Backend

| Capa | Responsabilidad | Lo que no hace |
|---|---|---|
| **Routers** | Recibir el request y delegar | Sin lógica de negocio |
| **Controllers** | Orquestar el flujo | Sin acceso directo a la DB |
| **Services** | Toda la lógica de negocio | Sin conocer HTTP ni la DB |
| **Repositories** | Único punto de acceso a la DB | Sin lógica de negocio |
| **Integrations** | Wrappers de servicios externos | Sin lógica de negocio |
| **Schemas** | Validación de entrada y salida | Sin lógica de negocio |

```
# ✅ Flujo correcto
router → controller → service → repository → DB
                   ↘ integration → Anthropic / MercadoPago / Hotmart

# ❌ Lo que nunca debe pasar
router haciendo queries a la DB
controller llamando directamente a Anthropic
service conociendo detalles de HTTP (status codes, headers)
```

#### Frontend

| Capa | Responsabilidad |
|---|---|
| **Pages / App** | Composición de layouts y componentes |
| **Components** | UI pura, sin lógica de negocio |
| **Hooks** | Lógica de estado y efectos secundarios |
| **Services** | Llamadas a la API del backend |
| **Store** | Estado global compartido |

---

### Base 2 — Manejo de errores centralizado

Todos los errores del sistema pasan por un único handler.
El cliente siempre recibe una respuesta con el mismo formato.
Los logs siempre tienen la información necesaria para diagnosticar el problema.

```python
# Formato estándar de error — nunca devolver algo diferente
{
    "error": True,
    "message": "Descripción legible para el usuario",
    "code": "SNAKE_CASE_ERROR_CODE"
}

# Clase base de errores tipados
class AppError(Exception):
    def __init__(self, message: str, code: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code

# Ejemplos de uso en cualquier service
raise AppError("Contacto no encontrado", "CONTACT_NOT_FOUND", 404)
raise AppError("Email duplicado", "DUPLICATE_EMAIL", 409)
raise AppError("Claude no disponible", "CLAUDE_UNAVAILABLE", 503)
```

> Ver implementación completa del handler global en **ORDEN-Y-LEGIBILIDAD.md**

---

### Base 3 — Configuración y secretos externalizados

Cero secretos en el código. Sin negociación.

- Un único `config/settings.py` lee el entorno y exporta todo
- El resto del código solo importa `settings`, nunca `os.environ` directamente
- `.env` bloqueado en `.gitignore` desde el día 1
- `.env.example` siempre actualizado con todas las variables del proyecto
- En producción, las variables se configuran en AWS — nunca desde archivos

> Ver implementación completa en **SEGURIDAD-PENTEST.md — Sección 1**

---

### Base 4 — Validación en la frontera

Todo input externo se valida antes de llegar a la lógica de negocio.
El sistema interno asume que lo que recibe es dato limpio.

- Schemas Pydantic en cada endpoint del backend
- TypeScript estricto en el frontend — `any` prohibido
- Si el input no es válido → error 400 claro, sin llegar al service
- Los IDs externos siempre como UUID tipado

> Ver implementación completa en **SEGURIDAD-PENTEST.md — Sección 3**

---

### Base 5 — Base de datos con migraciones versionadas

El schema de la DB nunca se toca a mano en producción.

- Cada cambio al schema es un archivo SQL numerado y versionado
- Todos los archivos viven en `/migrations` en el repositorio
- El estado de la base es completamente reproducible desde cero
- RLS (Row Level Security) habilitado en todas las tablas con datos de usuario
- Los comentarios en las migraciones explican el **por qué**, no solo el qué

```sql
-- migrations/001_create_users.sql
-- Tabla base de usuarios del sistema.
-- plan puede ser 'free', 'pro' o 'enterprise'.
-- onboarding_completed indica si el usuario finalizó el flujo de activación autónoma.

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    plan TEXT CHECK (plan IN ('free', 'pro', 'enterprise')) DEFAULT 'free',
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
```

---

### Base 6 — Onboarding autónomo

El usuario se registra, paga y empieza a usar el producto sin intervención del equipo.
Este es el modelo de negocio de la agencia — cualquier paso que requiera acción manual
es un punto de falla y un costo operativo.

#### Flujo estándar de onboarding

```
1. Registro → validación de email automática
2. Selección de plan → redirección a MercadoPago / Hotmart
3. Confirmación de pago → webhook activa el plan automáticamente
4. Onboarding in-app → el usuario configura su cuenta guiado por la interfaz
5. Activación → acceso completo al producto sin intervención humana
```

#### Reglas de implementación

```python
# El webhook de pago activa el plan automáticamente
@router.post("/webhooks/payment")
async def payment_webhook(payload: PaymentWebhookPayload):
    await payment_service.process_payment_confirmation(payload)
    # Activa el plan, envía email de bienvenida, marca onboarding como iniciado
    # Sin intervención humana

# El sistema detecta usuarios con onboarding incompleto y los redirige
@router.get("/dashboard")
async def dashboard(current_user: User = Depends(get_current_user)):
    if not current_user.onboarding_completed:
        raise AppError("Onboarding pendiente", "ONBOARDING_REQUIRED", 403)
```

#### Emails transaccionales obligatorios

Cada producto implementa estos emails desde el día 1 — son parte del onboarding autónomo:

| Evento | Email |
|---|---|
| Registro | Bienvenida + verificación de email |
| Pago confirmado | Confirmación + acceso al producto |
| Pago fallido | Notificación + link de reintento |
| Trial por vencer | Recordatorio 3 días antes |
| Suscripción cancelada | Confirmación + opción de reactivar |

---

### Base 7 — Logging útil

Los logs existen para diagnosticar problemas, no para registrar todo.
Un log que nadie lee es ruido. Un log que falta cuando algo falla es un problema grave.

#### Qué se loguea y qué no

```python
# ✅ Loguear — eventos que importan para diagnosticar problemas
logger.info("Usuario registrado", extra={"user_id": user_id})
logger.info("Pago confirmado", extra={"user_id": user_id, "plan": plan, "amount": amount})
logger.warning("Intento de login fallido", extra={"ip": ip, "email": email})
logger.warning("Rate limit excedido", extra={"ip": ip, "endpoint": endpoint})
logger.error("Error en webhook de pago", extra={"payload": payload, "error": str(e)})
logger.error("Claude no disponible", extra={"error": str(e), "user_id": user_id})

# ❌ No loguear — ruido que no aporta valor
logger.info("Entrando a la función get_contacts")
logger.info("Query ejecutada correctamente")
logger.debug("Variable x tiene valor 42")
```

#### Niveles de log y cuándo usarlos

| Nivel | Cuándo usarlo |
|---|---|
| `INFO` | Eventos de negocio importantes: registro, pago, activación |
| `WARNING` | Situaciones anómalas que no rompen el sistema: login fallido, rate limit |
| `ERROR` | Algo falló y necesita atención: error en webhook, servicio externo caído |
| `DEBUG` | Solo en desarrollo local — nunca en producción |

#### Regla de oro del logging

> Si un log no te ayuda a responder "qué pasó, cuándo y con quién",
> no tiene razón de existir.

---

### Base 8 — Deploy reproducible en AWS

El proceso de deploy es documentado, repetible y no depende de pasos manuales ocultos.

#### Estructura mínima en AWS por producto

```
AWS
├── EC2 o ECS          ← servidor de la aplicación
├── RDS o Supabase     ← base de datos
├── S3                 ← archivos estáticos y backups
├── CloudWatch         ← logs centralizados y alertas
└── Route 53           ← DNS y dominio
```

#### Variables de entorno en producción

Las variables de entorno se configuran en AWS Systems Manager Parameter Store
o directamente en las variables de entorno del servicio de deploy.
Nunca en archivos `.env` en el servidor.

#### Checklist de deploy

```
[ ] Variables de entorno configuradas en AWS
[ ] Migraciones de DB ejecutadas antes del deploy
[ ] pip-audit sin vulnerabilidades (backend)
[ ] npm audit sin vulnerabilidades (frontend)
[ ] HTTPS configurado con certificado válido
[ ] CloudWatch configurado para capturar logs de la aplicación
[ ] Alerta configurada para errores 5xx
[ ] Backup automático de la DB activado
[ ] Dominio apuntando al nuevo servidor
```

---

### Base 9 — Testing mínimo obligatorio en flujos críticos

No se pide cobertura de tests al 100%. Se pide que los flujos que sostienen el negocio
no se rompan silenciosamente.

En un sistema que corre solo, un bug en el flujo de pago o registro puede significar
usuarios que no pueden activar su cuenta sin que nadie se entere.

#### Los flujos que siempre tienen test

```python
# tests/test_critical_flows.py

# 1. Registro de usuario
async def test_user_registration_success(): ...
async def test_user_registration_duplicate_email(): ...

# 2. Login y autenticación
async def test_login_success(): ...
async def test_login_wrong_password(): ...
async def test_protected_endpoint_without_token(): ...

# 3. Webhook de pago
async def test_payment_webhook_activates_plan(): ...
async def test_payment_webhook_invalid_signature(): ...

# 4. Funcionalidad core del producto (varía por proyecto)
async def test_[funcionalidad_principal]_success(): ...
async def test_[funcionalidad_principal]_with_invalid_input(): ...
```

#### Cómo correr los tests

```bash
# Backend
pytest tests/test_critical_flows.py -v

# Frontend — flujos críticos con Playwright o Cypress
npx playwright test tests/critical/
```

#### Regla práctica

Antes de cada deploy, los tests críticos pasan. Si un test falla, el deploy no sale.
Esto reemplaza la verificación manual en local y da garantía real de que el sistema funciona.

---

### Base 10 — Documentación mínima por proyecto

Cada proyecto tiene tres documentos internos. Sin estos tres, el proyecto no está terminado.

```
proyecto/
├── README.md          ← requisitos, instalación, cómo correr (máximo 1 página)
├── ARCHITECTURE.md    ← decisiones de arquitectura y por qué se tomaron
└── CHANGELOG.md       ← historial de cambios relevantes por versión
```

#### ARCHITECTURE.md — las decisiones que importan

```markdown
# Arquitectura — [Nombre del Proyecto]

## Stack elegido y por qué
- FastAPI sobre Django: proyecto pequeño, necesitamos velocidad y tipado estricto
- Supabase sobre RDS: RLS nativo, auth integrado, menos infraestructura a mantener

## Decisiones de diseño
- Multi-tenancy por user_id en cada tabla: escala bien para el volumen esperado
- Webhooks síncronos para pagos: MercadoPago requiere respuesta en menos de 5 segundos

## Deuda técnica conocida
- [fecha] Los emails transaccionales usan SMTP directo — migrar a SendGrid cuando escale
```

---

# Sección 2 — Bases de desarrollo manual

Estas bases aplican cuando el código se escribe a mano, sin asistencia de IA.

---

### M1 — Pensar antes de escribir

Antes de abrir el editor, definir:

1. **Qué capa** va a contener este código (router, service, repository, etc.)
2. **Qué función** va a tener y cuál es su única responsabilidad
3. **Qué recibe y qué devuelve** — los tipos de entrada y salida
4. **Qué puede fallar** y cómo se maneja ese error

Si no se puede responder estas cuatro preguntas en dos minutos, el diseño no está claro
y escribir código en ese estado produce deuda técnica.

---

### M2 — Una tarea a la vez

No abrir cinco archivos y modificar cosas en paralelo.
Terminar una función, probarla, commitearla, y recién pasar a la siguiente.

Esto aplica especialmente al trabajar en equipo de hasta 3 personas —
los conflictos de merge más dolorosos vienen de cambios dispersos en muchos archivos.

---

### M3 — El commit es la unidad de trabajo

Cada commit representa un cambio completo y coherente.
Si el commit incluye tres cosas distintas, debería haber sido tres commits.

```bash
# ✅ Un commit, una cosa
feat: agregar endpoint de búsqueda de contactos por industria

# ❌ Un commit, muchas cosas mezcladas
feat: búsqueda de contactos, fix del login, actualizar dependencias y cambiar colores
```

---

### M4 — Revisar el diff antes de commitear

Antes de cada commit, revisar `git diff` para verificar:

- No hay secrets accidentales en el código
- No hay `print()` o `console.log()` de debug olvidados
- No hay cambios en archivos que no debían tocarse
- El `.env` no está incluido en el staging

```bash
# Siempre antes de commitear
git diff --staged
```

---

### M5 — No romper lo que funciona

Si un módulo funciona y no es parte de la tarea actual, no se toca.
La tentación de "mejorar de paso" algo que no está en el scope es la causa más
común de regresiones inesperadas.

Si se detecta algo que debería mejorarse en otro módulo, se abre un issue o se anota
en el CHANGELOG como deuda técnica — no se toca en el momento.

---

# Sección 3 — Bases de vibe coding

Estas bases aplican cuando se desarrolla con IA — Claude, Claude Code o Claude Design.
El vibe coding bien hecho es más rápido y produce mejor código que el desarrollo manual.
El vibe coding mal hecho produce código que nadie entiende y que se rompe solo.

---

### V1 — El archivo CLAUDE.md es obligatorio en cada proyecto

`CLAUDE.md` es el documento de contexto que Claude lee al inicio de cada sesión de trabajo.
Sin este archivo, Claude no conoce el proyecto y empieza a inventar convenciones.

```markdown
# CLAUDE.md — [Nombre del Proyecto]

## Qué es este proyecto
[Una o dos oraciones que describen qué hace el producto]

## Stack
- Backend: Python 3.11 + FastAPI
- Frontend: React + Next.js 14 (App Router)
- DB: Supabase (PostgreSQL)
- IA: Anthropic Claude
- Deploy: AWS

## Estructura de carpetas
[Pegar la estructura de carpetas del proyecto]

## Convenciones de código
- Seguir ORDEN-Y-LEGIBILIDAD.md de la agencia
- Errores: siempre AppError con message, code y status_code
- Logs: solo eventos de negocio importantes — ver BASES-DE-DESARROLLO.md Base 7
- Máximo 150 líneas por archivo de service, 100 en routers

## Reglas para Claude
- No modificar archivos fuera del scope de la tarea
- Si un archivo supera el límite de líneas, proponer cómo dividirlo antes de escribir
- Siempre incluir docstring en funciones de services e integrations
- No usar print() ni console.log() — usar el logger centralizado
- Ante la duda entre dos enfoques, preguntar antes de implementar

## Estado actual del proyecto
- [Qué está implementado]
- [Qué está en desarrollo]
- [Deuda técnica conocida]
```

Este archivo se actualiza cada vez que cambia algo relevante del proyecto.

---

### V2 — Prompt con contexto completo

Un prompt sin contexto produce código genérico que no encaja con el proyecto.
Un prompt con contexto produce código que ya sigue las convenciones y se integra solo.

#### Estructura de un buen prompt

```
[Contexto del módulo donde voy a trabajar]
[Qué existe hoy relacionado con la tarea]
[Qué quiero lograr — específico y acotado]
[Qué restricciones aplican]
```

#### Ejemplo real

```
# ❌ Prompt sin contexto
"Haceme un endpoint para buscar contactos"

# ✅ Prompt con contexto
"Estoy en el módulo de contactos del backend. Ya existe contact_repo.py con
find_by_email() y save(). Necesito agregar un endpoint GET /contacts/search
que reciba 'industry' y 'company' como query params opcionales y devuelva
una lista paginada de contactos. Tiene que seguir la arquitectura por capas
del proyecto: router → controller → service → repository. El service tiene
que tener docstring completo. Máximo 80 líneas en el router."
```

---

### V3 — Una tarea por sesión de Claude

No pedirle a Claude que construya tres features al mismo tiempo.
Cuanto más grande la tarea, más probable que Claude pierda contexto y rompa algo.

#### División correcta del trabajo

```
# ❌ Una tarea gigante
"Construime el módulo completo de pagos con MercadoPago, webhook,
activación del plan, emails transaccionales y panel de administración"

# ✅ Tareas atómicas
Sesión 1: "Crear el schema Pydantic para el webhook de MercadoPago"
Sesión 2: "Crear el endpoint POST /webhooks/payment que recibe y valida el payload"
Sesión 3: "Crear payment_service.py con process_payment_confirmation()"
Sesión 4: "Integrar la activación del plan en el service de usuarios"
Sesión 5: "Agregar el envío de email de confirmación al flujo de pago"
```

---

### V4 — Revisar siempre el código generado

Claude puede producir código que funciona pero que no sigue las convenciones del proyecto,
tiene lógica innecesariamente compleja, o rompe algo en otro módulo.

#### Checklist de revisión de código generado por IA

```
[ ] El código sigue la arquitectura por capas del proyecto
[ ] No hay lógica de negocio en el router
[ ] No hay queries directas a la DB fuera del repository
[ ] Los nombres siguen las convenciones de ORDEN-Y-LEGIBILIDAD.md
[ ] El archivo no supera el límite de líneas para su tipo
[ ] Los errores usan AppError con code y status_code correctos
[ ] No hay print() ni console.log() de debug
[ ] Las funciones de services tienen docstring completo
[ ] No se modificaron archivos que no eran parte de la tarea
[ ] El código nuevo no duplica lógica que ya existe en otro módulo
```

---

### V5 — Darle feedback a Claude cuando algo no está bien

Si el código generado no sigue las convenciones, corregirlo en el prompt siguiente
en lugar de editarlo a mano en silencio.

Editar en silencio significa que Claude va a volver a cometer el mismo error
en la próxima sesión porque no aprendió qué estaba mal.

```
# ✅ Feedback explícito
"El código que generaste pone lógica de negocio en el router, eso va en el service.
Además el archivo tiene 180 líneas, el límite es 150. Reorganizalo respetando
la arquitectura por capas y dividiendo si es necesario."
```

---

### V6 — Claude Code para tareas de refactor y análisis

Claude Code (terminal) es especialmente útil para tareas que requieren leer
múltiples archivos en paralelo:

```bash
# Casos de uso ideales para Claude Code
- "Revisá todos los services y fijate si hay lógica duplicada"
- "Buscá todos los lugares donde se usa os.environ directamente y reemplazalos por settings"
- "Revisá que todos los endpoints tengan su schema Pydantic de validación"
- "Buscá print() y console.log() en todo el proyecto y reemplazalos con el logger"
```

Para features nuevas, Claude en el chat con contexto del CLAUDE.md es más controlado.

---

### V7 — Claude Design para UI/UX

Claude Design se usa para generar componentes visuales y layouts.
El output siempre se revisa contra el documento de UX/UI de la agencia
antes de integrarlo al proyecto.

Reglas para prompts de diseño:

```
# Siempre incluir en el prompt de diseño
- El design system del proyecto (colores, tipografía, espaciado)
- El componente o página específica que se quiere generar
- El estado de los datos (cargando, vacío, con error, con datos)
- Si es mobile-first o desktop-first
```

---

## Resumen — las bases de un vistazo

### Las 10 bases universales

| # | Base | Por qué importa |
|---|---|---|
| 1 | Arquitectura por capas | Cambiar una parte no rompe las otras |
| 2 | Errores centralizados | El cliente siempre recibe el mismo formato |
| 3 | Config y secrets externalizados | Cero vulnerabilidades por secrets expuestos |
| 4 | Validación en la frontera | El sistema interno trabaja con datos limpios |
| 5 | Migraciones versionadas | La DB es reproducible desde cero |
| 6 | Onboarding autónomo | El negocio funciona sin intervención humana |
| 7 | Logging útil | Se puede diagnosticar cualquier problema |
| 8 | Deploy reproducible en AWS | El deploy no depende de pasos manuales ocultos |
| 9 | Testing de flujos críticos | Los flujos de negocio no se rompen silenciosamente |
| 10 | Documentación mínima | El proyecto es entendible sin depender de quien lo escribió |

### Las 5 bases de desarrollo manual

| # | Base |
|---|---|
| M1 | Pensar antes de escribir |
| M2 | Una tarea a la vez |
| M3 | El commit es la unidad de trabajo |
| M4 | Revisar el diff antes de commitear |
| M5 | No romper lo que funciona |

### Las 7 bases de vibe coding

| # | Base |
|---|---|
| V1 | CLAUDE.md obligatorio en cada proyecto |
| V2 | Prompt con contexto completo |
| V3 | Una tarea por sesión de Claude |
| V4 | Revisar siempre el código generado |
| V5 | Darle feedback a Claude cuando algo no está bien |
| V6 | Claude Code para refactor y análisis |
| V7 | Claude Design para UI/UX |

---

*Agencia · Documento interno de desarrollo · 2026*
*Versión 1.0 — Stack: Python · FastAPI · React · Next.js · Supabase · Anthropic · AWS*
