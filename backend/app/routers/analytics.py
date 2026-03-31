from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import models, database, crud
from .auth import get_current_user
from pydantic import BaseModel
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

class VisitRequest(BaseModel):
    visitor_id: str

@router.post("/visit")
def record_visit(request: VisitRequest, db: Session = Depends(get_db)):
    # Check if visitor already exists
    existing_visit = db.query(models.PageView).filter(models.PageView.visitor_id == request.visitor_id).first()
    if not existing_visit:
        new_visit = models.PageView(visitor_id=request.visitor_id)
        db.add(new_visit)
        db.commit()
    return {"status": "ok"}

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

    all_product_data = _group_product_stats(raw_product_stats)
    product_data = all_product_data[:5]

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

    # A. Leads y Contactos por día (Mes Actual)
    monthly_leads_query = db.query(models.Lead.created_at, models.Lead.status).filter(
        models.Lead.created_at >= current_month_start
    ).all()

    leads_by_day = {str(d): 0 for d in range(1, month_days + 1)}
    contacts_by_day = {str(d): 0 for d in range(1, month_days + 1)}
    
    for lead_date, lead_status in monthly_leads_query:
        if lead_date:
            day_str = str(lead_date.day)
            leads_by_day[day_str] += 1
            if lead_status in [models.LeadStatus.CONTACTED, models.LeadStatus.NEGOTIATION, models.LeadStatus.CLOSED, models.LeadStatus.CLIENT]:
                contacts_by_day[day_str] += 1
            
    leads_per_day_data = [{"day": k, "leads": v} for k, v in leads_by_day.items()]
    contacts_per_day_data = [{"day": k, "contacts": v} for k, v in contacts_by_day.items()]

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

    # D. Visitantes Unicos (Totales y Mensuales)
    total_unique_visitors = db.query(models.PageView).count()
    monthly_unique_visitors = db.query(models.PageView).filter(
        models.PageView.created_at >= current_month_start
    ).count()

    # E. Monto Vendido (Mes Actual)
    raw_monthly_sales_amount = db.query(
        func.sum(models.SaleOrder.total_amount)
    ).filter(
        models.SaleOrder.status == models.SaleOrderStatus.COMPLETED,
        models.SaleOrder.created_at >= current_month_start
    ).scalar()
    monthly_total_sales = float(raw_monthly_sales_amount or 0)

    # F. Historical Sales
    all_completed_sales = db.query(
        models.SaleOrder.created_at,
        models.SaleOrder.total_amount,
        models.SaleOrder.id
    ).filter(
        models.SaleOrder.status == models.SaleOrderStatus.COMPLETED
    ).all()

    monthly_sales_dict = {}
    for created_at, amount, s_id in all_completed_sales:
        if not created_at: continue
        month_key = created_at.strftime("%Y-%m")
        if month_key not in monthly_sales_dict:
            monthly_sales_dict[month_key] = {"amount": 0.0, "count": 0}
        monthly_sales_dict[month_key]["amount"] += float(amount or 0)
        monthly_sales_dict[month_key]["count"] += 1

    historical_monthly_sales = [
        {
            "month": k, 
            "total_amount": v["amount"], 
            "sales_count": v["count"]
        } for k, v in sorted(monthly_sales_dict.items())
    ][-12:] # Las 12 months

    # 9. Stock Valuation
    rate_setting = crud.get_setting(db, key="manual_exchange_rate")
    exchange_rate = float(rate_setting.value) if rate_setting else 1450.0

    raw_stock_value = db.query(
        models.Product.name,
        models.Product.stock_quantity,
        models.Product.price_retail,
        models.Product.price_usd
    ).filter(
        models.Product.stock_quantity > 0,
        models.Product.is_active == True
    ).all()
    
    stock_value_data = []
    total_inventory_value = 0.0
    for name, stock, p_retail, p_usd in raw_stock_value:
        usd_val = float(p_usd or 0)
        retail_val = float(p_retail or 0)
        
        if usd_val > 0:
            p_price = usd_val * exchange_rate
        else:
            p_price = retail_val
            
        value = stock * p_price
        total_inventory_value += value
        stock_value_data.append({
            "product_name": name,
            "stock_value": float(value)
        })
    stock_value_data = sorted(stock_value_data, key=lambda x: x["stock_value"], reverse=True)[:15]

    # 10. Least Requested Products (Bottom active products with stock > 0)
    active_products = db.query(models.Product.name).filter(
        models.Product.is_active == True,
        models.Product.stock_quantity > 0
    ).all()
    active_product_names = [p[0].strip().upper() for p in active_products]
    
    product_interest_counts = {str(p["product"]).upper(): int(p["count"]) for p in all_product_data}
    for p_name in active_product_names:
        if p_name not in product_interest_counts:
             product_interest_counts[p_name] = 0
             
    least_requested_sorted = sorted(
        [{"product_name": k.title(), "count": v} for k, v in product_interest_counts.items() if k not in ["TODO", "HUMIDIFICADOR", "DECORACIÓN", "LUNCHERA", "VARIOS", "CATALOGO", "NADA"]],
        key=lambda x: x["count"]
    )
    least_requested_data = least_requested_sorted[:10]

    # 11. Lead Feedback
    raw_feedback = db.query(
        models.Lead.feedback_status,
        func.count(models.Lead.id)
    ).filter(
        models.Lead.feedback_status != None
    ).group_by(models.Lead.feedback_status).all()
    
    feedback_counts = {}
    for status, count in raw_feedback:
        if not status: continue
        if status.startswith("Respondio - "):
            options = status.replace("Respondio - ", "").split(", ")
            for opt in options:
                clean_opt = opt.split("(")[0].strip()
                feedback_counts[clean_opt] = feedback_counts.get(clean_opt, 0) + count
        else:
            feedback_counts[status] = feedback_counts.get(status, 0) + count
            
    feedback_data = [{"status": k, "count": v} for k, v in feedback_counts.items()]
    feedback_data = sorted(feedback_data, key=lambda x: x["count"], reverse=True)

    # 12. Website visits per day (Mes Actual)
    visits_per_day_data = []
    if total_unique_visitors > 0:
        visits_by_day = {str(d): 0 for d in range(1, month_days + 1)}
        monthly_visits_q = db.query(models.PageView.created_at).filter(
            models.PageView.created_at >= current_month_start
        ).all()
        for (v_date,) in monthly_visits_q:
            if v_date:
                visits_by_day[str(v_date.day)] += 1
        visits_per_day_data = [{"day": k, "visits": v} for k, v in visits_by_day.items()]

    # 13. Origin / Platform
    raw_platforms = db.query(
        models.Lead.platform,
        func.count(models.Lead.id)
    ).group_by(models.Lead.platform).all()
    
    final_platform = {}
    for plat, count in raw_platforms:
        p_name = plat or "Página Web"
        p_lower = str(p_name).lower()
        if "ig" in p_lower or "instagram" in p_lower: p_name = "Instagram"
        elif p_lower in ["f", "fb"] or "facebook" in p_lower: p_name = "Facebook"
        elif p_lower in ["g", "web"] or "página web" in p_lower or "pagina web" in p_lower: p_name = "Página Web"
        
        final_platform[p_name] = final_platform.get(p_name, 0) + count
    platform_data = [{"platform": k, "count": v} for k, v in final_platform.items()]

    return {
        "visitors": {
            "total": total_unique_visitors,
            "monthly": monthly_unique_visitors
        },
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
        "stock_valuation": {
            "total_value": total_inventory_value,
            "top_products": stock_value_data
        },
        "least_requested_products": least_requested_data,
        "lead_feedback": feedback_data,
        "lead_origins": platform_data,
        "monthly_metrics": {
            "leads_per_day": leads_per_day_data,
            "contacts_per_day": contacts_per_day_data,
            "visits_per_day": visits_per_day_data,
            "top_products_interest": monthly_product_data,
            "top_products_sold": monthly_top_sold_data,
            "total_amount_sold": monthly_total_sales,
            "historical_monthly_sales": historical_monthly_sales
        }
    }

@router.get("/historical")
def get_historical_analytics(
    year: int,
    month: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        return {"error": "Unauthorized"}
    
    start_date = datetime(year, month, 1)
    month_days = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, month_days, 23, 59, 59, 999999)

    # 1. Ventas: Total amount y count
    sales_q = db.query(
        func.count(models.SaleOrder.id),
        func.sum(models.SaleOrder.total_amount)
    ).filter(
        models.SaleOrder.status == models.SaleOrderStatus.COMPLETED,
        models.SaleOrder.created_at >= start_date,
        models.SaleOrder.created_at <= end_date
    ).first()
    sales_count = sales_q[0] or 0
    sales_amount = float(sales_q[1] or 0)

    # 2. Leads ingresados
    leads_entered = db.query(models.Lead).filter(
        models.Lead.created_at >= start_date,
        models.Lead.created_at <= end_date
    ).count()

    # 3. Leads contactados y que pasaron a clientes
    leads_contacted = db.query(models.Lead).filter(
        models.Lead.created_at >= start_date,
        models.Lead.created_at <= end_date,
        models.Lead.status.in_([models.LeadStatus.CONTACTED, models.LeadStatus.NEGOTIATION, models.LeadStatus.CLOSED, models.LeadStatus.CLIENT])
    ).count()
    
    leads_clients = db.query(models.Lead).filter(
        models.Lead.created_at >= start_date,
        models.Lead.created_at <= end_date,
        models.Lead.status == models.LeadStatus.CLIENT
    ).count()

    # 4. Top Sellers in that month
    raw_seller_sales = db.query(
        models.Lead.seller,
        func.count(models.SaleOrder.id),
        func.sum(models.SaleOrder.total_amount)
    ).join(
        models.SaleOrder, models.SaleOrder.lead_id == models.Lead.id
    ).filter(
        models.SaleOrder.status == models.SaleOrderStatus.COMPLETED,
        models.SaleOrder.created_at >= start_date,
        models.SaleOrder.created_at <= end_date
    ).group_by(models.Lead.seller).order_by(
        func.sum(models.SaleOrder.total_amount).desc()
    ).all()

    seller_sales_data = [
        {
            "seller": s[0] or "Sin Asignar",
            "sales_count": s[1],
            "total_amount": float(s[2] or 0)
        } for s in raw_seller_sales
    ]

    # 5. Productos más y menos vendidos
    raw_monthly_products = db.query(
        models.Product.name,
        func.sum(models.OrderItem.quantity)
    ).join(
        models.OrderItem, models.OrderItem.product_sku == models.Product.sku
    ).join(
        models.SaleOrder, models.SaleOrder.id == models.OrderItem.order_id
    ).filter(
        models.SaleOrder.status == models.SaleOrderStatus.COMPLETED,
        models.SaleOrder.created_at >= start_date,
        models.SaleOrder.created_at <= end_date
    ).group_by(models.Product.name).order_by(
        func.sum(models.OrderItem.quantity).desc()
    ).all()

    product_sales_dict = {p[0]: int(p[1] or 0) for p in raw_monthly_products}
    top_products = [{"product_name": k, "quantity_sold": v} for k, v in list(product_sales_dict.items())[:10]]
    
    # 6. Productos menos vendidos (Solo con stock actual)
    active_products = db.query(models.Product.name).filter(
        models.Product.is_active == True,
        models.Product.stock_quantity > 0
    ).all()
    active_product_names = [p[0] for p in active_products]

    bottom_products = []
    for p_name in active_product_names:
        qty = product_sales_dict.get(p_name, 0)
        bottom_products.append({"product_name": p_name, "quantity_sold": qty})
    
    bottom_products.sort(key=lambda x: x["quantity_sold"])
    bottom_products = bottom_products[:10]

    # 7. Plataforma Origen
    raw_platforms = db.query(
        models.Lead.platform,
        func.count(models.Lead.id)
    ).filter(
        models.Lead.created_at >= start_date,
        models.Lead.created_at <= end_date
    ).group_by(models.Lead.platform).all()
    
    final_platform = {}
    for plat, count in raw_platforms:
        p_name = plat or "Página Web"
        p_lower = str(p_name).lower()
        if "ig" in p_lower or "instagram" in p_lower: p_name = "Instagram"
        elif p_lower in ["f", "fb"] or "facebook" in p_lower: p_name = "Facebook"
        elif p_lower in ["g", "web"] or "página web" in p_lower or "pagina web" in p_lower: p_name = "Página Web"
        
        final_platform[p_name] = final_platform.get(p_name, 0) + count
        
    platform_data = [{"platform": k, "count": v} for k, v in final_platform.items()]

    # 8. Visitas y Contactos Diarios para el mes histórico
    visits_by_day = {str(d): 0 for d in range(1, month_days + 1)}
    monthly_visits_q = db.query(models.PageView.created_at).filter(
        models.PageView.created_at >= start_date,
        models.PageView.created_at <= end_date
    ).all()
    for (v_date,) in monthly_visits_q:
        if v_date: visits_by_day[str(v_date.day)] += 1
    visits_per_day_data = [{"day": k, "visits": v} for k, v in visits_by_day.items()]

    contacts_by_day = {str(d): 0 for d in range(1, month_days + 1)}
    historical_contacts_q = db.query(models.Lead.created_at).filter(
        models.Lead.created_at >= start_date,
        models.Lead.created_at <= end_date,
        models.Lead.status.in_([models.LeadStatus.CONTACTED, models.LeadStatus.NEGOTIATION, models.LeadStatus.CLOSED, models.LeadStatus.CLIENT])
    ).all()
    for (c_date,) in historical_contacts_q:
        if c_date: contacts_by_day[str(c_date.day)] += 1
    contacts_per_day_data = [{"day": k, "contacts": v} for k, v in contacts_by_day.items()]

    return {
        "sales": {
            "amount": sales_amount,
            "count": sales_count
        },
        "leads": {
            "entered": leads_entered,
            "contacted": leads_contacted,
            "converted_clients": leads_clients
        },
        "sellers_performance": seller_sales_data,
        "top_products": top_products,
        "bottom_products": bottom_products,
        "platforms": platform_data,
        "daily_metrics": {
            "visits_per_day": visits_per_day_data,
            "contacts_per_day": contacts_per_day_data
        },
        "period": {
            "year": year,
            "month": month
        }
    }
