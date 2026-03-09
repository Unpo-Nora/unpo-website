import httpx
import os
from typing import Optional, Dict, Any

META_API_VERSION = "v19.0"
GRAPH_URL = f"https://graph.facebook.com/{META_API_VERSION}"

async def get_lead_data(leadgen_id: str, access_token: str) -> Optional[Dict[str, Any]]:
    """
    Recupera los detalles de un lead desde la Meta Graph API.
    """
    url = f"{GRAPH_URL}/{leadgen_id}"
    params = {
        "access_token": access_token
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error recuperando lead {leadgen_id}: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Excepción al llamar a Meta API: {e}")
            return None

def transform_meta_lead_to_schemas(meta_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforma el formato de Meta Lead Ads al esquema interno LeadCreate.
    Meta devuelve los campos en una lista 'field_data'.
    """
    field_data = meta_data.get("field_data", [])
    transformed_data = {
        "full_name": "Unknown",
        "email": "unknown@example.com",
        "phone": None,
        "source": "INSTAGRAM_ADS",
        "platform": "instagram",
        "lead_date": meta_data.get("created_time")
    }
    
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
