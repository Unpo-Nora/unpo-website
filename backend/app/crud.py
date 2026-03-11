from sqlalchemy.orm import Session
from . import models, schemas
from sqlalchemy import or_

# --- Brand & Category ---
def get_brand_by_slug(db: Session, slug: str):
    return db.query(models.Brand).filter(models.Brand.slug == slug).first()

def get_categories(db: Session):
    return db.query(models.Category).join(models.Product).filter(
        models.Product.stock_quantity > 0,
        models.Product.is_active == True
    ).distinct().all()

def get_products(db: Session, skip: int = 0, limit: int = 200, brand_slug: str = None, category_id: int = None, in_stock: bool = False):
    query = db.query(models.Product).filter(models.Product.is_active == True)
    
    if brand_slug:
        query = query.join(models.Brand).filter(models.Brand.slug == brand_slug)
    
    if category_id:
        query = query.filter(models.Product.category_id == category_id)
        
    if in_stock:
        query = query.filter(models.Product.stock_quantity > 0)
        
    return query.offset(skip).limit(limit).all()

def get_product(db: Session, sku: str):
    return db.query(models.Product).filter(models.Product.sku == sku).first()

def create_product(db: Session, product: schemas.ProductCreate):
    db_product = models.Product(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

def update_product(db: Session, sku: str, product_data: dict):
    db_product = get_product(db, sku)
    if not db_product:
        return None
    for key, value in product_data.items():
        setattr(db_product, key, value)
    db.commit()
    db.refresh(db_product)
    return db_product

def archive_product(db: Session, sku: str):
    db_product = get_product(db, sku)
    if not db_product:
        return None
    db_product.is_active = False
    db.commit()
    db.refresh(db_product)
    return db_product

# --- Settings ---
def get_setting(db: Session, key: str):
    return db.query(models.Settings).filter(models.Settings.key == key).first()

def update_setting(db: Session, key: str, value: str):
    setting = get_setting(db, key)
    if not setting:
        setting = models.Settings(key=key, value=value)
        db.add(setting)
    else:
        setting.value = value
    db.commit()
    db.refresh(setting)
    return setting

# --- Leads ---
def create_lead(db: Session, lead: schemas.LeadCreate):
    db_lead = models.Lead(**lead.model_dump())
    
    if db_lead.status == "CONTACTED" and not getattr(db_lead, "contacted_at", None):
        from datetime import datetime, timezone
        db_lead.contacted_at = datetime.now(timezone.utc)
        
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    return db_lead

def get_lead_by_contact(db: Session, email: str = None, phone: str = None):
    """
    Busca un lead por email o teléfono para evitar duplicados.
    """
    filters = []
    if email:
        filters.append(models.Lead.email == email)
    if phone:
        filters.append(models.Lead.phone == phone)
        
    if not filters:
        return None
        
    return db.query(models.Lead).filter(or_(*filters)).first()

def get_leads(db: Session, skip: int = 0, limit: int = 5000, status: str = None, seller: str = None):
    query = db.query(models.Lead)
    if status:
        query = query.filter(models.Lead.status == status)
    if seller:
        query = query.filter(models.Lead.seller == seller)
    return query.order_by(models.Lead.id.desc()).offset(skip).limit(limit).all()

def update_lead(db: Session, lead_id: int, lead_data: dict):
    db_lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not db_lead:
        return None
    
    if lead_data.get("status") == "CONTACTED" and db_lead.status != "CONTACTED" and not db_lead.contacted_at:
        from datetime import datetime, timezone
        db_lead.contacted_at = datetime.now(timezone.utc)
    
    for key, value in lead_data.items():
        setattr(db_lead, key, value)
        
    db.commit()
    db.refresh(db_lead)
    return db_lead

# --- Sales & Orders ---
def create_sale_order(db: Session, order: schemas.SaleOrderCreate):
    db_order = models.SaleOrder(
        lead_id=order.lead_id,
        total_amount=order.total_amount,
        status=order.status,
        transport_name=order.transport_name,
        transport_dni=order.transport_dni,
        license_plate=order.license_plate,
        delivery_address=order.delivery_address,
        delivery_date=order.delivery_date
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    for item in order.items:
        db_item = models.OrderItem(
            order_id=db_order.id,
            product_sku=item.product_sku,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price
        )
        db.add(db_item)
        
        # Deduct stock
        db_product = get_product(db, item.product_sku)
        if db_product and db_product.stock_quantity >= item.quantity:
            db_product.stock_quantity -= item.quantity
    
    db.commit()
    db.refresh(db_order)
    return db_order

def get_sale_order(db: Session, order_id: int):
    return db.query(models.SaleOrder).filter(models.SaleOrder.id == order_id).first()

def get_sale_orders_by_lead(db: Session, lead_id: int):
    return db.query(models.SaleOrder).filter(models.SaleOrder.lead_id == lead_id).order_by(models.SaleOrder.id.desc()).all()

def cancel_sale_order(db: Session, order_id: int):
    db_order = get_sale_order(db, order_id)
    if not db_order or db_order.status == models.SaleOrderStatus.CANCELED:
        return None
        
    db_order.status = models.SaleOrderStatus.CANCELED
    
    # Restore stock
    for item in db_order.items:
        db_product = get_product(db, item.product_sku)
        if db_product:
            db_product.stock_quantity += item.quantity
            
    # Check if lead has other COMPLETED orders
    other_orders_count = db.query(models.SaleOrder).filter(
        models.SaleOrder.lead_id == db_order.lead_id,
        models.SaleOrder.status == models.SaleOrderStatus.COMPLETED,
        models.SaleOrder.id != order_id
    ).count()
    
    if other_orders_count == 0:
        db_order.lead.status = models.LeadStatus.CONTACTED
            
    db.commit()
    db.refresh(db_order)
    return db_order


# --- Users & Auth ---
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user_data: dict):
    # Asumimos que la contraseña ya viene hasheada desde el router si es necesario 
    # o la hasheamos aquí. Por claridad, la hashearemos aquí.
    from .utils import auth
    db_user = models.User(
        email=user_data["email"],
        hashed_password=auth.get_password_hash(user_data["password"]),
        full_name=user_data.get("full_name"),
        role=user_data.get("role", "admin")
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
