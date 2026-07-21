"""
Validación de la firma `X-Hub-Signature-256` de Meta.

Regla: HMAC-SHA256 del **cuerpo crudo en bytes** (nunca del JSON re-serializado)
con el App Secret, comparado en tiempo constante. La lógica vive acá y no en el
router para poder testearla de forma aislada y no duplicarla.
"""

import hashlib
import hmac

SIGNATURE_HEADER = "X-Hub-Signature-256"
SIGNATURE_PREFIX = "sha256="

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def compute_signature(app_secret: str, raw_body: bytes) -> str:
    """
    Devuelve la firma esperada en el formato de Meta: `sha256=<hex>`.

    Se usa para validar y también para construir fixtures de test firmados con un
    secreto ficticio. NUNCA se logea su resultado.
    """
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def verify_signature(app_secret: str, raw_body: bytes, signature_header: str) -> bool:
    """
    Valida la cabecera `X-Hub-Signature-256` contra el cuerpo crudo.

    Rechaza (devuelve False) cuando:
      - no hay App Secret configurado (no se valida "contra vacío");
      - falta la cabecera o viene vacía;
      - el prefijo no es exactamente `sha256=`;
      - el digest no es hexadecimal o no coincide.

    La comparación final usa `hmac.compare_digest` (tiempo constante).
    """
    if not app_secret:
        return False
    if not signature_header:
        return False
    if not signature_header.startswith(SIGNATURE_PREFIX):
        return False

    received = signature_header[len(SIGNATURE_PREFIX):].strip()
    if not received:
        return False
    # `compare_digest` sobre str exige ASCII; un digest válido siempre es hex puro.
    if any(c not in _HEX_DIGITS for c in received):
        return False

    expected = compute_signature(app_secret, raw_body)[len(SIGNATURE_PREFIX):]
    return hmac.compare_digest(expected, received.lower())
