"""Errores tipados de la aplicación (ver ORDEN-Y-LEGIBILIDAD.md sección 7)."""


class AppError(Exception):
    """Error tipado de la aplicación. Lleva HTTP status y código interno."""

    def __init__(self, message: str, code: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
