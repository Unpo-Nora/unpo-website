from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import models, database
from .auth import get_current_user
from typing import List, Dict, Any
from datetime import datetime
import calendar

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"]
)

get_db = database.get_db

def _group_product_stats(raw_stats):
    grouped_products = {}
    for product_name, count in raw_stats:
        normalized_name = str(product_name).strip().upper()
        if normalized_name in ["NAN", "NINGUNO", "-", ""]:
            continue
            
        todo_terms = [
            "TODOS", "TODO", "VARIO", "VARIOS", "VARIADA", "VARIADAS", 
            "VARIADOS", "VARIADO", "CUALQUIERA", "VARIEDAD", ".", 
            "MIX COMPLETO", "MIX", "CATALOGO", "CATÁLOGO"
        ]
        
        if (normalized_name in todo_terms or 
            "EN TODO" in normalized_name or 
            "ENTODO" in normalized_name or
            "DE TODO" in normalized_name or
            "DE TODO UN POCO" in normalized_name):
            grouped_products["TODO"] = grouped_products.get("TODO", 0) + count
            continue
            
        if "DIFUSOR" in normalized_name:
             grouped_products["HUMIDIFICADOR"] = grouped_products.get("HUMIDIFICADOR", 0) + count
             continue
             
        if normalized_name == "DECO" or "DECORACION" in normalized_name or "DECORACIÓN" in normalized_name:
             grouped_products["DECORACIÓN"] = grouped_products.get("DECORACIÓN", 0) + count
             continue
             
        if "VIANDA" in normalized_name or "TUPPER" in normalized_name or "LUNCHERA" in normalized_name or "LONCHERA" in normalized_name:
             grouped_products["LUNCHERA"] = grouped_products.get("LUNCHERA", 0) + count
             continue
            
        clean_key = normalized_name
        if clean_key.endswith("ES"):
            clean_key = clean_key[:-2]
        elif clean_key.endswith("S"):
            clean_key = clean_key[:-1]
            
        if "HUMIFI" in clean_key:
            clean_key = clean_key.replace("HUMIFI", "HUMIDIFI")
            
        grouped_products[clean_key] = grouped_products.get(clean_key, 0) + count

    sorted_products = sorted(
        [{"product": k, "count": v} for k, v in grouped_products.items()],
        key=lambda x: x["count"], 
        reverse=True
    )
    return sorted_products

@router.get("/summary")
def get_analytics_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Solo administradores pueden ver métricas gerenciales
    if current_user.role != "admin":
        return {"error": "Unauthorized"}

    # 1. Resumen de Leads
    total_leads = db.query(models.Lead).count()
    new_leads = db.query(models.Lead).filter(models.Lead.status == models.LeadStatus.NEW).count()
    contacted_leads = db.query(models.Lead).filter(models.Lead.status == models.LeadStatus.CONTACTED).count()

    # 2. Gestión por Vendedor (Top Sellers en contacto)
    seller_stats = db.query(
        models.Lead.seller, 
        func.count(models.Lead.id)
    ).filter(
        models.Lead.status == models.LeadStatus.CONTACTED,
        models.Lead.seller != None
    ).group_by(models.Lead.seller).all()
    
    seller_data = [{"email": s[0], "count": s[1]} for s in seller_stats]

    # 3. Alertas de Stock (<= 5 o Agotado)
    stock_alerts = db.query(models.Product).filter(
        models.Product.stock_quantity <= 5,
        models.Product.is_active == True
    ).order_by(models.Product.stock_quantity.asc()).limit(15).all()
    
    alert_data = [
        {
            "sku": p.sku, 
            "name": p.name, 
            "stock": p.stock_quantity
        } for p in stock_alerts
    ]

    # 4. Interés por Categoría (Basado en Leads)
    raw_category_stats = db.query(
        models.Lead.category_interest,
        func.count(models.Lead.id)
    ).filter(
        models.Lead.category_interest != None
    ).group_by(models.Lead.category_interest).all()
    
    grouped_categories = {}
    for cat_name, count in raw_category_stats:
        normalized_cat = str(cat_name).strip().upper().replace("_", " ")
        normalized_cat = " ".join(normalized_cat.split())
        
        # Group "Artículos de cocina" variations
        if normalized_cat in ["ARTÍCULOS DE COCINA", "ARTICULOS DE COCINA"]:
            normalized_cat = "ARTÍCULOS DE COCINA"
            
        grouped_categories[normalized_cat] = grouped_categories.get(normalized_cat, 0) + count
        
    sorted_categories = sorted(
        [{"category": k, "count": v} for k, v in grouped_categories.items()],
        key=lambda x: x["count"],
        reverse=True
    )
    category_data = sorted_categories[:5]

    # 5. Interés por Producto (Basado en Leads)
    # Get all products, we will group them in memory since string manipulation in SQLite/SQLAlchemy 
    # can be tricky across different DB dialects, and the number of distinct products is usually manageable.
    raw_product_stats = db.query(
        models.Lead.product_interest,
        func.count(models.Lead.id)
    ).filter(
        models.Lead.product_interest != None,
        models.Lead.product_interest != ""
    ).group_by(models.Lead.product_interest).all()

    product_data = _group_product_stats(raw_product_stats)[:5]

    # 6. Ventas por Vendedor (Montos y Cantidades)
    raw_seller_sales = db.query(
        models.Lead.seller,
        func.count(models.SaleOrder.id),
        func.sum(models.SaleOrder.total_amount)
    ).join(
        models.SaleOrder, models.SaleOrder.lead_id == models.Lead.id
    ).filter(
        models.SaleOrder.status == models.SaleOrderStatus.COMPLETED
    ).group_by(models.Lead.seller).all()

    seller_sales_data = [
        {
            "seller": s[0] or "Sin Asignar",
            "sales_count": s[1],
            "total_amount": float(s[2] or 0)
        } for s in raw_seller_sales
    ]

    # 7. Clientes con Más Compras
    raw_top_clients = db.query(
        models.Lead.full_name,
        func.count(models.SaleOrder.id),
        func.sum(models.SaleOrder.total_amount)
    ).join(
        models.SaleOrder, models.SaleOrder.lead_id == models.Lead.id
    ).filter(
        models.SaleOrder.status == models.SaleOrderStatus.COMPLETED
    ).group_by(models.Lead.full_name).order_by(
        func.sum(models.SaleOrder.total_amount).desc()
    ).limit(10).all()

    top_clients_data = [
        {
            "client_name": c[0] or "Desconocido",
            "purchases": c[1],
            "total_amount": float(c[2] or 0)
        } for c in raw_top_clients
    ]

    # 8. Productos Más Vendidos
    raw_top_products = db.query(
        models.Product.name,
        models.Category.name,
        func.sum(models.OrderItem.quantity)
    ).join(
        models.OrderItem, models.OrderItem.product_sku == models.Product.sku
    ).join(
        models.SaleOrder, models.SaleOrder.id == models.OrderItem.order_id
    ).outerjoin(
        models.Category, models.Product.category_id == models.Category.id
    ).filter(
        models.SaleOrder.status == models.SaleOrderStatus.COMPLETED
    ).group_by(models.Product.name, models.Category.name).order_by(
        func.sum(models.OrderItem.quantity).desc()
    ).limit(10).all()

    top_products_sold_data = [
        {
            "product_name": p[0],
            "category": p[1] or "General",
            "quantity_sold": int(p[2] or 0)
        } for p in raw_top_products
    ]

    # --- DATOS MENSUALES ---
    now = datetime.now()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_days = calendar.monthrange(now.year, now.month)[1]

    # A. Leads por día (Mes Actual)
    monthly_leads_query = db.query(models.Lead.created_at).filter(
        models.Lead.created_at >= current_month_start
    ).all()

    leads_by_day = {str(d): 0 for d in range(1, month_days + 1)}
    for (lead_date,) in monthly_leads_query:
        if lead_date:
            day_str = str(lead_date.day)
            leads_by_day[day_str] += 1
            
    leads_per_day_data = [{"day": k, "leads": v} for k, v in leads_by_day.items()]

    # B. Interés por Producto (Mes Actual)
    raw_monthly_product_stats = db.query(
        models.Lead.product_interest,
        func.count(models.Lead.id)
    ).filter(
        models.Lead.created_at >= current_month_start,
        models.Lead.product_interest != None,
        models.Lead.product_interest != ""
    ).group_by(models.Lead.product_interest).all()

    monthly_product_data = _group_product_stats(raw_monthly_product_stats)[:10]

    # C. Productos Más Vendidos (Mes Actual)
    raw_monthly_top_products = db.query(
        models.Product.name,
        func.sum(models.OrderItem.quantity)
    ).join(
        models.OrderItem, models.OrderItem.product_sku == models.Product.sku
    ).join(
        models.SaleOrder, models.SaleOrder.id == models.OrderItem.order_id
    ).filter(
        models.SaleOrder.status == models.SaleOrderStatus.COMPLETED,
        models.SaleOrder.created_at >= current_month_start
    ).group_by(models.Product.name).order_by(
        func.sum(models.OrderItem.quantity).desc()
    ).limit(10).all()

    monthly_top_sold_data = [
        {"product_name": p[0], "quantity_sold": int(p[1] or 0)}
        for p in raw_monthly_top_products
    ]

    return {
        "leads": {
            "total": total_leads,
            "new": new_leads,
            "contacted": contacted_leads,
            "conversion_rate": round((contacted_leads / total_leads * 100), 2) if total_leads > 0 else 0
        },
        "sellers": seller_data,
        "stock_alerts": alert_data,
        "category_interest": category_data,
        "product_interest": product_data,
        "seller_sales": seller_sales_data,
        "top_clients": top_clients_data,
        "top_products_sold": top_products_sold_data,
        "monthly_metrics": {
            "leads_per_day": leads_per_day_data,
            "top_products_interest": monthly_product_data,
            "top_products_sold": monthly_top_sold_data
        }
    }
