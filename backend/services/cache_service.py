"""Caché de respuestas de fuentes externas: capa fina sobre CacheRepository.

Estandariza las keys por fuente (formato "{fuente}:{cuit}") y centraliza los TTL
por defecto de cada fuente. No conoce ninguna fuente real todavía: solo provee la
maquinaria para que BCRA/ARCA/BORA se enchufen después sin reescribir el caché.
"""

from repositories.cache_repo import CacheRepository, InMemoryCacheRepository

# TTL por defecto, en segundos, por fuente externa.
# BCRA: el status crediticio/financiero se actualiza con cadencia diaria como
# máximo, así que cachear 24h evita golpear la fuente en consultas repetidas del
# mismo día sin servir datos materialmente desactualizados.
TTL_BCRA = 24 * 60 * 60  # 24 horas
# ARCA: padrón e inscripciones cambian poco día a día; mismo criterio que BCRA.
TTL_ARCA = 24 * 60 * 60  # 24 horas
# BORA: los boletines publicados son históricos e inmutables una vez emitidos,
# así que un TTL largo (7 días) es seguro y reduce mucho las consultas externas.
TTL_BORA = 7 * 24 * 60 * 60  # 7 días

# Repositorio activo. Temporalmente en memoria; al conectar Supabase se reemplaza
# por SupabaseCacheRepository (misma interfaz CacheRepository).
cache_repo: CacheRepository = InMemoryCacheRepository()


def construir_key(fuente: str, cuit: str) -> str:
    """Arma la key de caché para una fuente y un CUIT.

    Args:
        fuente: Identificador corto de la fuente externa (ej. 'bcra', 'arca').
        cuit: CUIT ya limpio (11 dígitos) que identifica a la empresa consultada.

    Returns:
        La key en formato "{fuente}:{cuit}" (ej. "bcra:30716595540").
    """
    return f"{fuente}:{cuit}"


async def obtener_cacheado(fuente: str, cuit: str) -> dict | None:
    """Devuelve la respuesta cacheada de una fuente para un CUIT, si sigue vigente.

    Args:
        fuente: Identificador corto de la fuente externa.
        cuit: CUIT ya limpio que identifica a la empresa consultada.

    Returns:
        El value cacheado, o None si no existe o ya expiró.
    """
    return await cache_repo.get(construir_key(fuente, cuit))


async def guardar_en_cache(
    fuente: str, cuit: str, value: dict, ttl_seconds: int
) -> None:
    """Guarda la respuesta de una fuente para un CUIT con un TTL.

    Args:
        fuente: Identificador corto de la fuente externa.
        cuit: CUIT ya limpio que identifica a la empresa consultada.
        value: Respuesta de la fuente a cachear.
        ttl_seconds: Vigencia en segundos; usar las constantes TTL_* del módulo.
    """
    await cache_repo.set(construir_key(fuente, cuit), value, ttl_seconds)
