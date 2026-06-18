"""Logger JSON estructurado (ver SEGURIDAD-PENTEST.md sección 8.2).

Nunca loguear passwords, tokens completos ni API keys (sección 8.3).
"""

import json
import logging
from datetime import datetime, timezone

# Atributos que trae cualquier LogRecord por defecto. Todo lo que aparezca en un
# record y no esté aquí proviene del extra={...} de la llamada y se anexa al JSON.
_BASE_RECORD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys())


class JSONFormatter(logging.Formatter):
    """Formatea cada registro como una línea JSON para ingestión por herramientas."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        # logging no expone extra={...} como record.extra: setea cada clave como
        # atributo suelto del record. Los recuperamos descartando los estándar.
        extra = {
            key: value
            for key, value in vars(record).items()
            if key not in _BASE_RECORD_ATTRS
        }
        log_data.update(extra)
        return json.dumps(log_data)


logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
logger.propagate = False

_handler = logging.StreamHandler()
_handler.setFormatter(JSONFormatter())
logger.addHandler(_handler)
