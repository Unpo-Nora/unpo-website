from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Numeric, Text, TIMESTAMP, JSON, Enum, DateTime, func
from sqlalchemy.orm import relationship
from .database import Base
import enum
from datetime import datetime

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
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
