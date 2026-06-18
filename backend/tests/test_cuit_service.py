"""Tests del guardrail de CUIT (services/cuit_service.py).

Los CUIT de ejemplo tienen dígito verificador real calculado con módulo 11.
"""

import pytest

from services.cuit_service import validar_cuit_juridica
from utils.errors import AppError

# Persona jurídica (prefijo 30) con dígito verificador correcto.
CUIT_JURIDICA_VALIDO = "30716595540"
# Persona física (prefijo 20) con dígito verificador correcto.
CUIT_FISICA_VALIDO = "20123456786"
# Prefijo no reconocido (99), dígito verificador correcto para llegar al chequeo.
CUIT_PREFIJO_DESCONOCIDO = "99123456781"


def test_cuit_juridica_valido_pasa():
    assert validar_cuit_juridica(CUIT_JURIDICA_VALIDO) == CUIT_JURIDICA_VALIDO


def test_cuit_juridica_con_separadores_se_limpia_y_pasa():
    assert validar_cuit_juridica("  30-71659554-0 ") == CUIT_JURIDICA_VALIDO


def test_cuit_fisica_valido_no_permitido():
    with pytest.raises(AppError) as exc:
        validar_cuit_juridica(CUIT_FISICA_VALIDO)
    assert exc.value.code == "PERSONA_FISICA_NOT_ALLOWED"
    assert exc.value.status_code == 422


def test_cuit_digito_verificador_incorrecto():
    with pytest.raises(AppError) as exc:
        validar_cuit_juridica("30716595541")  # último dígito alterado
    assert exc.value.code == "INVALID_CUIT"
    assert exc.value.status_code == 400


def test_cuit_con_menos_de_11_digitos():
    with pytest.raises(AppError) as exc:
        validar_cuit_juridica("30-7165955-4")  # solo 10 dígitos
    assert exc.value.code == "INVALID_CUIT"
    assert exc.value.status_code == 400


def test_cuit_prefijo_desconocido():
    with pytest.raises(AppError) as exc:
        validar_cuit_juridica(CUIT_PREFIJO_DESCONOCIDO)
    assert exc.value.code == "UNKNOWN_CUIT_PREFIX"
    assert exc.value.status_code == 400
