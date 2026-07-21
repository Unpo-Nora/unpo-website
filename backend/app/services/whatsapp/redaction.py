"""
Helpers de redacción para logging seguro del módulo WhatsApp.

Regla del proyecto: los logs NUNCA contienen cuerpos completos, teléfonos completos,
nombres completos, contenido de mensajes, identificadores externos completos, tokens,
secretos ni firmas. Para poder correlacionar se usan ids internos, hashes truncados y
sufijos enmascarados.
"""

import hashlib

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
    """
    Trunca una clave que YA es un hash (p. ej. `sha256:abc123…`) para los logs.

    No sirve para identificadores externos: si el valor es más corto que `keep` se
    devuelve entero. Para `wamid` / ids de Meta usar `mask_external_id`.
    """
    if not value:
        return _MASK
    text = str(value)
    return text if len(text) <= keep else f"{text[:keep]}…"


def mask_external_id(value, keep: int = 10) -> str:
    """
    Huella estable y NO reversible de un identificador externo (`wamid`, ids de Meta).

    Truncar no alcanza: un `wamid` corto quedaría completo en el log. Se emite un
    prefijo del sha256, que permite correlacionar dos apariciones del mismo id sin
    exponerlo nunca entero.
    """
    if not value:
        return _MASK
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
    return f"ext:{digest[:keep]}"


# Marcadores con los que los drivers de base de datos adjuntan la sentencia, los
# parámetros bindeados y la fila conflictiva al mensaje de error. Todo lo que viene
# después puede contener datos del payload (teléfono, nombre, texto del mensaje) y se
# descarta antes de persistir o logear.
#
# `: "` cubre la otra familia de errores, donde el valor va en el mensaje PRIMARIO y no
# en el DETAIL:  `invalid input syntax for type integer: "<valor>"`.
_DB_NOISE_MARKERS = ("[SQL:", "[parameters:", "DETAIL:", "CONTEXT:", "HINT:", "LINE ",
                     ': "', ": '")


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
    etiqueta = "error" if isinstance(exc, str) else type(exc).__name__
    text = exc if isinstance(exc, str) else f"{etiqueta}: {exc}"
    text = str(text)
    for marker in _DB_NOISE_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
    # `split()` colapsa además cualquier carácter de control; se quitan explícitamente
    # el NUL y los surrogates, que PostgreSQL no puede almacenar en `last_error_safe`.
    text = "".join(c for c in text if c != "\x00" and not 0xD800 <= ord(c) <= 0xDFFF)
    # `rstrip` de puntuación: al cortar por marcador suele quedar un "Tipo:" colgado.
    text = " ".join(text.split()).rstrip(" :;,-")
    if not text:
        # El mensaje entero era ruido del driver (empezaba con DETAIL:, por ejemplo).
        # Se conserva al menos el tipo, para no persistir un error vacío.
        return etiqueta
    return text[:limit]
