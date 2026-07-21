"""
Helpers de redacción para logging seguro del módulo WhatsApp.

Regla del proyecto: los logs NUNCA contienen cuerpos completos, teléfonos completos,
nombres completos, contenido de mensajes, tokens, secretos ni firmas. Para poder
correlacionar se usan ids internos, hashes truncados y sufijos enmascarados.
"""

_MASK = "***"


def mask_identifier(value, keep: int = 4) -> str:
    """
    Enmascara un identificador (wa_id, teléfono, recipient_id) dejando solo los
    últimos `keep` caracteres: `5491100000000` -> `***0000`.

    Valores cortos o vacíos se enmascaran por completo (no aportan correlación y sí
    riesgo de reidentificación).
    """
    if not value:
        return _MASK
    text = str(value)
    if len(text) <= keep:
        return _MASK
    return f"{_MASK}{text[-keep:]}"


def short_key(value, keep: int = 12) -> str:
    """Trunca una clave/hash/id externo para logs: `sha256:abc123...`."""
    if not value:
        return _MASK
    text = str(value)
    return text if len(text) <= keep else f"{text[:keep]}…"


# Marcadores con los que los drivers de base de datos adjuntan la sentencia, los
# parámetros bindeados y la fila conflictiva al mensaje de error. Todo lo que viene
# después puede contener datos del payload (teléfono, nombre, texto del mensaje) y se
# descarta antes de persistir o logear.
_DB_NOISE_MARKERS = ("[SQL:", "[parameters:", "DETAIL:", "CONTEXT:", "HINT:", "LINE ")


def safe_error(exc, limit: int = 200) -> str:
    """
    Convierte una excepción (o texto) en una línea corta apta para persistir en
    `last_error_safe` / `error_message_safe` y para logging.

    Recorta la sentencia SQL, los parámetros bindeados y el `DETAIL:` de PostgreSQL
    (que incluye la fila completa), colapsa espacios y trunca. Truncar NO alcanza: el
    prefijo de un `UniqueViolation` o de un `NotNullViolation` puede entrar dentro del
    límite y arrastrar el valor conflictivo.
    """
    if exc is None:
        return ""
    text = exc if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
    text = str(text)
    for marker in _DB_NOISE_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    text = " ".join(text.split())
    return text[:limit]
