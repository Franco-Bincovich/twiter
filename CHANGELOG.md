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
