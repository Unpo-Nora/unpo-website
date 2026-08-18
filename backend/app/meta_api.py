import httpx
import logging
import os
import unicodedata
from typing import Optional, Dict, Any

logger = logging.getLogger("uvicorn.error")

# Versión por defecto de la Graph API. Overridable via META_GRAPH_API_VERSION
# (sin valor real hardcodeado). Se lee en tiempo de llamada para que un cambio de
# entorno no requiera reimportar el módulo.
DEFAULT_META_API_VERSION = "v19.0"

# --- Detección tolerante de campos del formulario de Lead Ads -----------------
# Meta expone las preguntas ESTÁNDAR con nombres fijos (`phone_number`, `email`,
# `full_name`) pero las preguntas PERSONALIZADAS con un nombre generado a partir
# del texto de la pregunta (p. ej. `¿cuál_es_tu_whatsapp?`). Diagnóstico 2026-08:
# el 100 % de los leads de Meta llegaba sin teléfono porque el formulario de la
# agencia pide el teléfono como pregunta personalizada y el código solo reconocía
# el nombre estándar. La detección se hace por PALABRA CLAVE, normalizando
# acentos/mayúsculas, para no depender del texto exacto de la pregunta.
_PHONE_KEYWORDS = ("phone", "telefono", "celular", "whatsapp", "movil", "cel")
_NAME_KEYWORDS = ("full_name", "first_name", "last_name", "nombre")
_EMAIL_KEYWORDS = ("email", "e-mail", "correo", "mail")

# Preguntas personalizadas del formulario UNPO (nombres tal como los genera Meta).
_CUSTOM_FIELD_MAP = {
    "¿qué_tipo_de_negocio_tenés?": "business_type",
    "selecciona_tu_volumen_de_compra": "purchase_volume",
    "¿por_cuál_categoría_estár_más_interesado?": "category_interest",
    "¿hace_cuántos_años_estás_en_el_mercado?": "experience_level",
    "¿en_qué_producto_estabas_interesado/a?": "product_interest",
}


def _norm(name: str) -> str:
    """Minúsculas, sin acentos ni signos ¿?¡! — para comparar nombres de campo."""
    text = unicodedata.normalize("NFKD", str(name or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().replace("¿", "").replace("?", "").replace("¡", "").replace("!", "").strip()


def _matches(norm_name: str, keywords) -> bool:
    return any(k in norm_name for k in keywords)


def _graph_url() -> str:
    version = os.getenv("META_GRAPH_API_VERSION") or DEFAULT_META_API_VERSION
    return f"https://graph.facebook.com/{version}"


async def get_lead_data(leadgen_id: str, access_token: str) -> Optional[Dict[str, Any]]:
    """
    Recupera los detalles de un lead desde la Meta Graph API.
    """
    url = f"{_graph_url()}/{leadgen_id}"
    params = {
        "access_token": access_token,
        "fields": "id,created_time,field_data,platform,ad_name,campaign_name"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                # No logueamos el token ni el body crudo de la respuesta (puede
                # contener datos personales del lead). Sólo id + status HTTP.
                print(f"Error recuperando lead {leadgen_id}: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"Excepción al llamar a Meta API para lead {leadgen_id}: {e}")
            return None


def transform_meta_lead_to_schemas(meta_data: Dict[str, Any], brand: str = "unpo") -> Dict[str, Any]:
    """
    Transforma el formato de Meta Lead Ads al esquema interno LeadCreate.
    Meta devuelve los campos en una lista 'field_data'.

    brand:
      - "unpo" (default, comportamiento histórico) -> source FACEBOOK_ADS / INSTAGRAM_ADS
      - "nora" -> source FACEBOOK_NORA / INSTAGRAM_NORA
    Se parametriza para NO mezclar marcas: el webhook NORA pasa brand="nora" y el
    webhook UNPO conserva el default sin cambios.
    """
    field_data = meta_data.get("field_data", [])

    # Extract platform from Meta response payload (usually 'fb' or 'ig')
    platform_val = str(meta_data.get("platform", "ig")).lower()
    is_facebook = platform_val in ("fb", "facebook")
    assigned_platform = "facebook" if is_facebook else "instagram"

    if brand == "nora":
        assigned_source = "FACEBOOK_NORA" if is_facebook else "INSTAGRAM_NORA"
    else:
        assigned_source = "FACEBOOK_ADS" if is_facebook else "INSTAGRAM_ADS"

    transformed_data = {
        "full_name": "Unknown",
        "email": "unknown@example.com",
        "phone": None,
        "source": assigned_source,
        "platform": assigned_platform,
        "lead_date": meta_data.get("created_time")
    }

    # Tracking de campaña/anuncio usando columnas YA existentes (campaign / ad_name).
    # No agrega columnas nuevas (no requiere migración).
    if meta_data.get("campaign_name"):
        transformed_data["campaign"] = meta_data.get("campaign_name")
    if meta_data.get("ad_name"):
        transformed_data["ad_name"] = meta_data.get("ad_name")

    unrecognized = []
    for field in field_data:
        name = field.get("name")
        values = field.get("values", [])
        if not values or not name:
            continue

        value = values[0]
        norm = _norm(name)

        if name in _CUSTOM_FIELD_MAP:
            transformed_data[_CUSTOM_FIELD_MAP[name]] = value
        elif name in ("full_name", "first_name", "last_name") or _matches(norm, _NAME_KEYWORDS):
            # first_name/last_name: si vienen ambos se concatenan; si no, se pisa.
            if name == "last_name" and transformed_data.get("full_name") not in (None, "Unknown"):
                transformed_data["full_name"] = f"{transformed_data['full_name']} {value}".strip()
            else:
                transformed_data["full_name"] = value
        elif name in ("email",) or _matches(norm, _EMAIL_KEYWORDS):
            transformed_data["email"] = value
        elif name in ("phone_number", "phone") or _matches(norm, _PHONE_KEYWORDS):
            # Primer teléfono gana (si el formulario tuviera dos preguntas de contacto).
            if not transformed_data.get("phone"):
                transformed_data["phone"] = str(value).strip() or None
        else:
            unrecognized.append(name)

    # Solo NOMBRES de campo no reconocidos (nunca valores: son datos personales).
    # Permite detectar un cambio del formulario sin volver a perder datos en silencio.
    if unrecognized:
        logger.warning("[meta-leads] campos de formulario no reconocidos: %s", unrecognized)
    if not transformed_data.get("phone"):
        logger.warning("[meta-leads] lead sin teléfono; campos recibidos: %s",
                       [f.get("name") for f in field_data])

    return transformed_data
