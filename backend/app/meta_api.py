import httpx
import os
from typing import Optional, Dict, Any

# Versión por defecto de la Graph API. Overridable via META_GRAPH_API_VERSION
# (sin valor real hardcodeado). Se lee en tiempo de llamada para que un cambio de
# entorno no requiera reimportar el módulo.
DEFAULT_META_API_VERSION = "v19.0"


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

    for field in field_data:
        name = field.get("name")
        values = field.get("values", [])
        if not values:
            continue

        value = values[0]

        if name in ["full_name", "first_name", "last_name"]:
            transformed_data["full_name"] = value
        elif name == "email":
            transformed_data["email"] = value
        elif name in ["phone_number", "phone"]:
            transformed_data["phone"] = value
        elif name == "¿qué_tipo_de_negocio_tenés?":
            transformed_data["business_type"] = value
        elif name == "selecciona_tu_volumen_de_compra":
            transformed_data["purchase_volume"] = value
        elif name == "¿por_cuál_categoría_estár_más_interesado?":
            transformed_data["category_interest"] = value
        elif name == "¿hace_cuántos_años_estás_en_el_mercado?":
            transformed_data["experience_level"] = value
        elif name == "¿en_qué_producto_estabas_interesado/a?":
            transformed_data["product_interest"] = value

    return transformed_data
