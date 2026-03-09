from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

class LeadBase(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    lead_date: Optional[datetime] = None
    
    # Business Details
    business_type: Optional[str] = None
    purchase_volume: Optional[str] = None
    category_interest: Optional[str] = None
    experience_level: Optional[str] = None
    product_interest: Optional[str] = None
    
    # Billing & Shipping Info
    dni_cuit: Optional[str] = None
    address: Optional[str] = None
    locality: Optional[str] = None
    province: Optional[str] = None
    zip_code: Optional[str] = None
    
    # Extras
    notes: Optional[str] = None
    
    # Tracking (Automated or Manual)
    source: Optional[str] = "WEB_UNPO"
    campaign: Optional[str] = None
    ad_set: Optional[str] = None
    ad_name: Optional[str] = None
    platform: Optional[str] = None
    seller: Optional[str] = None
    status: Optional[str] = "NEW"
    feedback_status: Optional[str] = None

class LeadCreate(LeadBase):
    pass

class LeadUpdate(BaseModel):
  status: Optional[str] = None
  notes: Optional[str] = None
  seller: Optional[str] = None
  feedback_status: Optional[str] = None

class LeadResponse(LeadBase):
    id: int
    created_at: Optional[datetime] = None
    contacted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Order Schemas ---

class OrderItemBase(BaseModel):
    product_sku: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal

class OrderItemCreate(OrderItemBase):
    pass

class OrderItem(OrderItemBase):
    id: int
    order_id: int

    class Config:
        from_attributes = True

class SaleOrderBase(BaseModel):
    lead_id: int
    status: Optional[str] = "COMPLETED"
    total_amount: Decimal
    
    # Transport Details
    transport_name: Optional[str] = None
    transport_dni: Optional[str] = None
    license_plate: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_date: Optional[datetime] = None
    
    # Billing fields coming from the frontend to update the Lead
    dni_cuit: Optional[str] = None
    address: Optional[str] = None
    locality: Optional[str] = None
    province: Optional[str] = None
    zip_code: Optional[str] = None

class SaleOrderCreate(SaleOrderBase):
    items: List[OrderItemCreate]

class SaleOrder(SaleOrderBase):
    id: int
    created_at: datetime
    items: List[OrderItem] = []

    class Config:
        from_attributes = True

# --- Product Schemas ---

class CategoryBase(BaseModel):
    name: str
    brand_id: Optional[int] = None

class CategoryCreate(CategoryBase):
    pass

class Category(CategoryBase):
    id: int

    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    brand_id: Optional[int] = None
    category_id: Optional[int] = None
    price_wholesale: Optional[Decimal] = None
    price_retail: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    price_usd: Optional[Decimal] = None
    iva_percent: Optional[Decimal] = Field(default=Decimal(21.0))
    moq: int = 1
    stock_quantity: int = 0
    is_active: bool = True
    
    # Physical Attributes
    weight: Optional[Decimal] = None
    height: Optional[Decimal] = None
    width: Optional[Decimal] = None
    length: Optional[Decimal] = None
    color: Optional[str] = None
    provider_name: Optional[str] = None
    
    specs: Optional[Dict[str, Any]] = None
    images: Optional[List[str]] = None
    videos: Optional[List[str]] = None

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    class Config:
        from_attributes = True

# --- Settings Schemas ---

class SettingsBase(BaseModel):
    key: str
    value: str

class SettingsUpdate(BaseModel):
    value: str
    password: Optional[str] = None # For sensitive settings like exchange rate

class Settings(SettingsBase):
    class Config:
        from_attributes = True
