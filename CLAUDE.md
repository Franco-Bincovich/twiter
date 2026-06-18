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

**Pendiente:** autenticación (JWT + refresh), integraciones Supabase/Anthropic,
rate limiting, migraciones SQL con RLS, más tests del flujo de informe.
Ver `ARCHITECTURE.md` para la deuda técnica detallada.
