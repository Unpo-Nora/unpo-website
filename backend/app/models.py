from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Numeric, Text, TIMESTAMP, JSON, Enum, DateTime, func
from sqlalchemy.orm import relationship
from .database import Base
import enum
from datetime import datetime
import pytz

def get_ar_time():
    return datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    NEGOTIATION = "NEGOTIATION"
    CLOSED = "CLOSED"
    LOST = "LOST"
    CLIENT = "CLIENT"

class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    slug = Column(String, unique=True, index=True)
    
    products = relationship("Product", back_populates="brand")
    categories = relationship("Category", back_populates="brand")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    
    brand = relationship("Brand", back_populates="categories")
    products = relationship("Product", back_populates="category")

class Settings(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=False)

class CapitalIva(Base):
    __tablename__ = "capital_ivas"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_ar_time)
    observation = Column(String, nullable=True)
    created_by = Column(String, nullable=True)

class Product(Base):
    __tablename__ = "products"

    sku = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    brand_id = Column(Integer, ForeignKey("brands.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    
    price_wholesale = Column(Numeric(12, 2), nullable=True) # ARS (Deprecated/Legacy)
    price_retail = Column(Numeric(12, 2), nullable=True)    # ARS
    cost_price = Column(Numeric(12, 2), nullable=True)     # ARS
    price_usd = Column(Numeric(12, 2), nullable=True)      # New USD master price
    iva_percent = Column(Numeric(5, 2), default=21.0)      # Porcentaje de IVA
    price_breakdown = Column(JSON, nullable=True)          # JSON object for constructed price details
    
    moq = Column(Integer, default=1) # Minimum Order Quantity
    stock_quantity = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    # Physical Attributes
    weight = Column(Numeric(10, 3), nullable=True) # Kg
    height = Column(Numeric(10, 2), nullable=True) # cm
    width = Column(Numeric(10, 2), nullable=True)  # cm
    length = Column(Numeric(10, 2), nullable=True) # cm
    color = Column(String, nullable=True)
    provider_name = Column(String, nullable=True)
    
    specs = Column(JSON, nullable=True) 
    images = Column(JSON, nullable=True) # ["url1", "url2"]
    videos = Column(JSON, nullable=True) # ["url1", "url2"]

    brand = relationship("Brand", back_populates="products")
    category = relationship("Category", back_populates="products")

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=get_ar_time, server_default=func.now())
    lead_date = Column(DateTime(timezone=True), nullable=True) # Fecha original del lead (de Excel o Meta)
    
    # Core Contact Info
    full_name = Column(String, index=True)
    email = Column(String, index=True)
    phone = Column(String)
    
    # Business Details (UNPO B2B)
    business_type = Column(String, nullable=True)
    purchase_volume = Column(String, nullable=True)
    category_interest = Column(String, nullable=True)
    experience_level = Column(String, nullable=True)
    product_interest = Column(String, nullable=True)
    
    # Additional Notes / Feedback
    notes = Column(Text, nullable=True)
    feedback_status = Column(String, nullable=True) # Respondio, No responde, Numero erroneo
    
    # Tracking
    source = Column(String, default="WEB_UNPO")
    campaign = Column(String, nullable=True)
    ad_set = Column(String, nullable=True)
    ad_name = Column(String, nullable=True)
    platform = Column(String, nullable=True)
    seller = Column(String, nullable=True)
    
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW)
    contacted_at = Column(DateTime(timezone=True), nullable=True)
    assigned_seller_phone = Column(String, nullable=True)
    
    # Billing & Shipping Info
    dni_cuit = Column(String, nullable=True)
    address = Column(String, nullable=True)
    locality = Column(String, nullable=True)
    province = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)
    
    orders = relationship("SaleOrder", back_populates="lead")

class SaleOrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"

class SaleOrder(Base):
    __tablename__ = "sale_orders"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=get_ar_time, server_default=func.now())
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    status = Column(Enum(SaleOrderStatus), default=SaleOrderStatus.COMPLETED)
    
    total_amount = Column(Numeric(12, 2), default=0.0)
    
    # Transport Details
    transport_name = Column(String, nullable=True)
    transport_dni = Column(String, nullable=True)
    vehicle_model = Column(String, nullable=True)
    license_plate = Column(String, nullable=True)
    delivery_address = Column(String, nullable=True)
    delivery_date = Column(DateTime(timezone=True), nullable=True)
    
    lead = relationship("Lead", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("sale_orders.id"), nullable=False)
    product_sku = Column(String, ForeignKey("products.sku"), nullable=False)
    
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    total_price = Column(Numeric(12, 2), nullable=False)
    
    order = relationship("SaleOrder", back_populates="items")
    product = relationship("Product")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String, nullable=True)
    role = Column(String, default="admin")

class PageView(Base):
    __tablename__ = "page_views"

    id = Column(Integer, primary_key=True, index=True)
    visitor_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), default=get_ar_time, server_default=func.now())

class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(String, nullable=False)
    date = Column(DateTime(timezone=True), default=get_ar_time, server_default=func.now())
    user_email = Column(String, nullable=True)

class InventoryAuditLog(Base):
    __tablename__ = "inventory_audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, index=True)
    action = Column(String) # e.g. "STOCK_UPDATE", "PRICE_UPDATE", "NEW_PRODUCT", "EXCHANGE_RATE"
    details = Column(String)
    created_at = Column(DateTime(timezone=True), default=get_ar_time, server_default=func.now())

class Employee(Base):
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, unique=True, index=True)
    hire_date = Column(DateTime(timezone=True), nullable=True)
    salary = Column(Numeric(12, 2), nullable=True)
    role_function = Column(String, nullable=True)
    
    absent_days_this_month = Column(Integer, default=0)
    vacation_days_available = Column(Integer, default=14)
    
    # Optional link to a system user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    user = relationship("User", backref="employee_profile")

class TransactionType(str, enum.Enum):
    INGRESO = "INGRESO"
    EGRESO = "EGRESO"
    CUENTA_POR_PAGAR = "CUENTA_POR_PAGAR"
    PAGO = "PAGO"

class TransactionCategory(str, enum.Enum):
    MERCADERIA = "MERCADERIA"
    DEPOSITO = "DEPOSITO"
    OPERATIVO = "OPERATIVO"
    LOGISTICA = "LOGISTICA"
    IMPUESTOS = "IMPUESTOS"
    OTROS = "OTROS"

class TransactionStatus(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    PAGADO = "PAGADO"
    VENCIDO = "VENCIDO"

class PurchasePaymentType(str, enum.Enum):
    CONTADO = "CONTADO"
    DIAS_30 = "30_DIAS"
    DIAS_60 = "60_DIAS"

class PurchaseStatus(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    PARCIAL = "PARCIAL"
    PAGADO = "PAGADO"

class CostType(str, enum.Enum):
    PRODUCTO = "PRODUCTO"
    FLETE = "FLETE"
    IMPUESTOS = "IMPUESTOS"
    OTROS = "OTROS"

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True, nullable=False)
    contacto = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    email = Column(String, nullable=True)

    purchases = relationship("Purchase", back_populates="supplier")

class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    proveedor_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    descripcion = Column(String, nullable=True)
    cantidad_total = Column(Integer, default=0)
    monto_total = Column(Numeric(12, 2), default=0.0)
    moneda = Column(String, default="ARS")
    fecha_compra = Column(DateTime(timezone=True), default=get_ar_time)
    tipo_pago = Column(Enum(PurchasePaymentType), default=PurchasePaymentType.CONTADO)
    estado = Column(Enum(PurchaseStatus), default=PurchaseStatus.PENDIENTE)

    supplier = relationship("Supplier", back_populates="purchases")
    cost_details = relationship("PurchaseCostDetail", back_populates="purchase", cascade="all, delete-orphan")
    items = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")

class PurchaseCostDetail(Base):
    __tablename__ = "purchase_cost_details"

    id = Column(Integer, primary_key=True, index=True)
    compra_id = Column(Integer, ForeignKey("purchases.id"), nullable=False)
    tipo_costo = Column(Enum(CostType), nullable=False)
    monto = Column(Numeric(12, 2), nullable=False)

    purchase = relationship("Purchase", back_populates="cost_details")

class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id = Column(Integer, primary_key=True, index=True)
    compra_id = Column(Integer, ForeignKey("purchases.id"), nullable=False)
    product_sku = Column(String, ForeignKey("products.sku"), nullable=False)
    cantidad = Column(Integer, nullable=False)

    purchase = relationship("Purchase", back_populates="items")
    product = relationship("Product")

class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    id = Column(Integer, primary_key=True, index=True)
    tipo_movimiento = Column(Enum(TransactionType), nullable=False)
    categoria = Column(Enum(TransactionCategory), nullable=False)
    descripcion = Column(String, nullable=False)
    monto = Column(Numeric(12, 2), nullable=False)
    moneda = Column(String, default="ARS")
    fecha = Column(DateTime(timezone=True), default=get_ar_time)
    fecha_vencimiento = Column(DateTime(timezone=True), nullable=True)
    estado = Column(Enum(TransactionStatus), default=TransactionStatus.PAGADO)
    
    proveedor_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    compra_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_ar_time)

    supplier = relationship("Supplier")
    purchase = relationship("Purchase")
