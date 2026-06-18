# Orden y Legibilidad — Agencia

> Documento de referencia para todo desarrollador de la agencia.
> El código que producimos tiene que ser navegable por IA en el día a día
> y legible por un humano cuando algo falla en producción a las 2 AM.
> Stack: Python · FastAPI · React · Next.js

---

## Principios generales

**El código se lee mucho más de lo que se escribe.**
Cada función, archivo y carpeta tiene que comunicar su propósito sin necesidad de explicación extra.

**La IA es parte del equipo.**
Si un archivo tiene más de 200 líneas, la IA pierde contexto y empieza a romper cosas.
La modularidad no es opcional — es lo que hace que el desarrollo asistido por IA funcione bien.

**Un humano tiene que poder orientarse solo.**
Cuando algo falla en producción, quien lo resuelve no puede depender de contexto que solo existe
en la cabeza de quien lo escribió. El código tiene que explicarse a sí mismo.

---

## 1. Estructura de carpetas

### Backend — Python / FastAPI

```
backend/
├── main.py                  ← punto de entrada, solo configuración de la app
├── config/
│   └── settings.py          ← única fuente de configuración y variables de entorno
├── routers/                 ← definición de endpoints, sin lógica de negocio
│   ├── auth.py
│   ├── contacts.py
│   └── ...
├── controllers/             ← orquestación del flujo entre routers y services
│   ├── auth_controller.py
│   ├── contact_controller.py
│   └── ...
├── services/                ← toda la lógica de negocio
│   ├── auth_service.py
│   ├── contact_service.py
│   └── ...
├── repositories/            ← único punto de acceso a la base de datos
│   ├── contact_repo.py
│   └── ...
├── integrations/            ← wrappers de servicios externos
│   ├── anthropic_client.py
│   └── supabase_client.py
├── schemas/                 ← modelos Pydantic de entrada y salida
│   ├── contact.py
│   └── ...
├── middleware/              ← auth, rate limiting, errores, logging
│   ├── auth.py
│   ├── error_handler.py
│   └── ...
├── utils/                   ← funciones helpers reutilizables
│   ├── logger.py
│   └── ...
├── migrations/              ← SQL versionado de cambios al schema
│   ├── 001_create_contacts.sql
│   └── ...
└── tests/                   ← tests organizados como el proyecto
    ├── test_contact_service.py
    └── ...
```

### Frontend — React / Next.js

```
frontend/
├── app/                     ← rutas de Next.js App Router
│   ├── (auth)/
│   │   ├── login/
│   │   │   └── page.tsx
│   │   └── register/
│   │       └── page.tsx
│   ├── dashboard/
│   │   └── page.tsx
│   └── layout.tsx
├── components/
│   ├── ui/                  ← componentes genéricos reutilizables (Button, Input, Modal)
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   └── ...
│   └── features/            ← componentes específicos de una feature
│       ├── contacts/
│       │   ├── ContactCard.tsx
│       │   └── ContactList.tsx
│       └── ...
├── hooks/                   ← custom hooks reutilizables
│   ├── useContacts.ts
│   └── useAuth.ts
├── services/                ← llamadas a la API del backend
│   ├── api.ts               ← cliente base con interceptors
│   ├── contactService.ts
│   └── authService.ts
├── store/                   ← estado global (Zustand / Context)
│   └── authStore.ts
├── types/                   ← tipos TypeScript compartidos
│   └── index.ts
└── utils/                   ← funciones helper del frontend
    └── formatters.ts
```

---

## 2. Límites de tamaño de archivos

Estos límites no son sugerencias — son la línea donde un archivo deja de ser navegable
por la IA y difícil de revisar para un humano.

| Tipo de archivo | Límite de líneas |
|---|---|
| Router / Page | 80 líneas |
| Controller | 100 líneas |
| Service | 150 líneas |
| Repository | 100 líneas |
| Componente React | 150 líneas |
| Custom Hook | 80 líneas |
| Cualquier otro archivo | 200 líneas |

Si un archivo supera su límite, se divide en módulos más pequeños.
No hay excepciones — si algo parece imposible de dividir, es señal de que tiene demasiadas responsabilidades.

---

## 3. Naming — nombres que explican sin comentarios

### Python — backend

```python
# ✅ Nombres completos y descriptivos
async def find_contact_by_email(email: str) -> Contact: ...
async def generate_cold_email(product_description: str, tone: str) -> str: ...
async def send_campaign_email(contact_id: UUID, campaign_id: UUID) -> bool: ...

# ❌ Abreviaciones que requieren contexto para entenderse
async def find_ct(em: str): ...
async def gen_email(desc: str, t: str): ...
async def send(c_id, camp_id): ...
```

```python
# Variables: snake_case, descriptivas
contact_list = await contact_repo.find_all_by_user(user_id)
daily_usage_count = await usage_repo.get_daily_count(user_id)

# Constantes: UPPER_SNAKE_CASE
MAX_REQUESTS_PER_DAY = 100
DEFAULT_EMAIL_TONE = "profesional"

# Clases: PascalCase
class ContactRepository: ...
class EmailGenerationService: ...
class CreateContactRequest(BaseModel): ...
```

### TypeScript — frontend

```typescript
// Componentes: PascalCase
const ContactCard = ({ contact }: ContactCardProps) => { ... }
const DashboardLayout = ({ children }: LayoutProps) => { ... }

// Hooks: camelCase con prefijo "use"
const useContactList = (userId: string) => { ... }
const useAuthSession = () => { ... }

// Funciones y variables: camelCase, descriptivas
const fetchContactsByUser = async (userId: string): Promise<Contact[]> => { ... }
const isEmailValid = (email: string): boolean => { ... }

// Constantes: UPPER_SNAKE_CASE
const MAX_CONTACTS_PER_PAGE = 20
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL

// Tipos e interfaces: PascalCase
type ContactStatus = "active" | "inactive" | "pending"
interface CreateContactPayload { ... }
```

### Archivos y carpetas

```
# Python — snake_case
contact_service.py
auth_repository.py
email_generator.py

# React/Next.js — PascalCase para componentes, camelCase para el resto
ContactCard.tsx
useContacts.ts
contactService.ts
authStore.ts
```

---

## 4. Una función, un propósito

Cada función hace exactamente una cosa. Si necesita un "y" para describir lo que hace, se divide.

```python
# ✅ Una responsabilidad clara
async def validate_contact_email(email: str) -> bool:
    """Verifica que el email tiene formato válido y no está duplicado."""
    ...

async def save_contact(contact_data: CreateContactRequest, user_id: UUID) -> Contact:
    """Persiste un contacto nuevo en la base de datos."""
    ...

async def create_contact(contact_data: CreateContactRequest, user_id: UUID) -> Contact:
    """Orquesta la validación y el guardado de un contacto nuevo."""
    is_valid = await validate_contact_email(contact_data.email)
    if not is_valid:
        raise AppError("Email inválido o duplicado", "INVALID_EMAIL", 400)
    return await save_contact(contact_data, user_id)


# ❌ Demasiadas responsabilidades en una función
async def create_contact(contact_data, user_id):
    # valida el email
    # busca duplicados en la DB
    # guarda el contacto
    # llama a Claude para enriquecer los datos
    # envía email de bienvenida
    # registra en el log de actividad
    ...
```

---

## 5. Documentación del código

### Python — docstrings obligatorios en services e integrations

```python
# services/email_service.py
async def generate_cold_email(
    product_description: str,
    tone: str,
    objective: str,
    variants: int = 2
) -> list[str]:
    """
    Genera variantes de email frío usando Claude.

    Args:
        product_description: Descripción del producto o servicio a ofrecer.
        tone: Tono del email. Valores: 'profesional' | 'directo' | 'amigable' | 'consultivo'.
        objective: Objetivo del email. Valores: 'reunion' | 'demo' | 'propuesta'.
        variants: Cantidad de variantes a generar. Default: 2.

    Returns:
        Lista con las variantes del email generadas.

    Raises:
        AppError: code 'CLAUDE_UNAVAILABLE' si la API de Anthropic no responde.
        AppError: code 'GENERATION_FAILED' si Claude no puede generar el contenido.
    """
    ...
```

### TypeScript — JSDoc en hooks y services

```typescript
// hooks/useContacts.ts

/**
 * Hook para gestionar la lista de contactos del usuario autenticado.
 *
 * @param userId - ID del usuario cuyos contactos se cargan.
 * @returns contacts, isLoading, error y las funciones createContact, deleteContact.
 *
 * @example
 * const { contacts, isLoading, createContact } = useContacts(userId)
 */
export const useContacts = (userId: string) => { ... }
```

### Comentarios inline — solo cuando el código no se explica solo

```python
# ✅ Comentario que agrega valor — explica el por qué, no el qué
# Supabase devuelve 200 aunque no encuentre filas, por eso chequeamos el array
if not response.data:
    raise AppError("Contacto no encontrado", "NOT_FOUND", 404)

# Anthropic recomienda separar el system prompt del user input para prevenir inyecciones
response = client.messages.create(
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": clean_input}]
)

# ❌ Comentario que no agrega nada — el código ya lo dice
# Incrementar el contador en 1
count += 1

# Devolver el contacto
return contact
```

---

## 6. Herramientas de formato y linting

### Backend — Python

Stack: **Ruff** (linter + formatter). Reemplaza a Black, Flake8 e isort en una sola herramienta.

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",   # errores de estilo
    "F",   # errores de lógica (variables no usadas, imports no usados)
    "I",   # orden de imports
    "N",   # naming conventions
    "UP",  # upgrades a sintaxis moderna de Python
]
ignore = ["E501"]  # líneas largas — Ruff formatter las maneja

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

```bash
# Correr linter
ruff check .

# Formatear código
ruff format .

# Correr ambos (lo más común en el día a día)
ruff check . --fix && ruff format .
```

### Frontend — React / Next.js

Stack: **ESLint** + **Prettier**.

```json
// .eslintrc.json
{
  "extends": [
    "next/core-web-vitals",
    "plugin:@typescript-eslint/recommended",
    "prettier"
  ],
  "rules": {
    "no-unused-vars": "error",
    "no-console": "warn",
    "prefer-const": "error",
    "eqeqeq": "error",
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/explicit-function-return-type": "warn"
  }
}
```

```json
// .prettierrc
{
  "semi": false,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100
}
```

### Pre-commit hooks — el código no entra si no pasa el linter

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v4.0.0
    hooks:
      - id: prettier
        types_or: [javascript, jsx, ts, tsx]

  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v9.0.0
    hooks:
      - id: eslint
        files: \.[jt]sx?$
```

```bash
# Instalación inicial en cada repo
pip install pre-commit
pre-commit install
```

---

## 7. Manejo de errores

### Formato de respuesta de error — siempre el mismo

```python
# Nunca devolver formatos de error distintos en distintos endpoints
# ✅ Siempre este formato
{
    "error": True,
    "message": "Descripción legible para el usuario",
    "code": "SNAKE_CASE_ERROR_CODE"
}
```

### Clase base de errores tipados

```python
# utils/errors.py
class AppError(Exception):
    """Error tipado de la aplicación. Lleva HTTP status y código interno."""

    def __init__(self, message: str, code: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


# Uso en cualquier service
raise AppError("Contacto no encontrado", "CONTACT_NOT_FOUND", 404)
raise AppError("Email duplicado", "DUPLICATE_EMAIL", 409)
raise AppError("Claude no disponible", "CLAUDE_UNAVAILABLE", 503)
```

### Handler global — un único lugar que captura todo

```python
# middleware/error_handler.py
from fastapi import Request
from fastapi.responses import JSONResponse

async def global_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, AppError):
        logger.warning(exc.message, extra={"code": exc.code, "path": request.url.path})
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": True, "message": exc.message, "code": exc.code}
        )

    # Error inesperado — loguear completo pero no exponer detalle al cliente
    logger.error("Error inesperado", extra={"error": str(exc), "path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": "Error interno del servidor", "code": "INTERNAL_ERROR"}
    )

# main.py
app.add_exception_handler(Exception, global_error_handler)
```

---

## 8. Convenciones de Git

### Formato de commits — convencional y obligatorio

```
tipo: descripción corta en presente e imperativo

feat:     nueva funcionalidad
fix:      corrección de bug
refactor: cambio de código que no agrega ni corrige nada
chore:    tareas de mantenimiento (deps, config, etc.)
docs:     cambios solo en documentación
test:     agregar o modificar tests
style:    cambios de formato que no afectan la lógica
```

```bash
# ✅ Buenos commits
feat: agregar búsqueda de contactos por industria
fix: corregir refresh de token cuando expira en medio de una sesión
refactor: separar lógica de generación de emails en módulo propio
chore: actualizar dependencias de seguridad
docs: agregar instrucciones de deploy al README

# ❌ Commits que no sirven de nada
fix: arreglar bug
update: cambios
wip
asdfgh
```

### Flujo de branches para hasta 3 devs

```
main          ← producción, siempre estable
└── develop   ← integración, base para nuevas features
    ├── feat/contact-search
    ├── feat/email-generation
    └── fix/token-refresh
```

- Nadie pushea directo a `main`
- Nadie pushea directo a `develop` — siempre desde una branch de feature o fix
- El nombre de la branch describe exactamente lo que hace: `feat/contact-search`, `fix/token-refresh`
- Pull Request obligatorio para mergear a `develop` — al menos 1 review si hay otro dev disponible

---

## 9. README obligatorio en cada proyecto

Tres secciones, nada más. Si hay que leer más para levantar el proyecto, el README está roto.

```markdown
# Nombre del Proyecto

Descripción en una oración de qué hace este proyecto.

## Requisitos

- Python 3.11+
- Node.js 20+
- Docker y Docker Compose

## Instalación

git clone [repo]
cd [proyecto]
cp .env.example .env  # completar las variables
docker-compose up --build

## Cómo correr

Backend: uvicorn main:app --reload
Frontend: npm run dev
Tests: pytest / npm test
```

---

## Checklist de legibilidad — antes de cada PR

```
[ ] Ningún archivo supera su límite de líneas
[ ] Todas las funciones tienen un solo propósito
[ ] Los nombres describen qué hace la función/variable sin necesitar contexto extra
[ ] Las funciones de services e integrations tienen docstring completo
[ ] No hay comentarios que solo repiten lo que ya dice el código
[ ] Ruff y ESLint/Prettier pasan sin errores
[ ] Los commits del PR siguen el formato convencional
[ ] El .env.example está actualizado si se agregaron variables nuevas
```

---

*Agencia · Documento interno de desarrollo · 2026*
*Versión 1.0 — Stack: Python · FastAPI · React · Next.js*
