from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Numeric, Text, TIMESTAMP, JSON, Enum, DateTime, func, Index, UniqueConstraint, text, UUID
from sqlalchemy.dialects import postgresql
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


# ===========================================================================
# WhatsApp Cloud API — modelo de datos multiagente (Etapa 1B)
#
# Diseño aprobado en docs/unpo-whatsapp-cloud-api-architecture.md. Reglas clave:
#  - Estados como String (validados por aplicación / CHECK futuro), NO enums PG nativos,
#    para evitar ALTER TYPE en migraciones posteriores.
#  - Contactos GLOBALES (sin line_id); las conversaciones son por (línea, contacto).
#  - Idempotencia: unique parcial de mensajes (external_message_id / client_request_id),
#    unique de event_key en eventos de estado y de webhook.
#  - NUNCA se almacenan tokens ni secretos en la base (solo config no secreta de líneas).
#  - Política ondelete: FKs hacia users/leads en SET NULL (conservar historial); tablas
#    hijas propias del módulo en CASCADE; line_id/contact_id de conversaciones en RESTRICT
#    (las líneas se desactivan con is_active, no se borran físicamente).
# ===========================================================================

class WhatsAppLine(Base):
    """Configuración NO secreta de cada línea de WhatsApp. NUNCA almacena tokens."""
    __tablename__ = "whatsapp_lines"

    id = Column(Integer, primary_key=True)
    provider = Column(String(32), nullable=False, default="meta")
    phone_number_id = Column(String(128), nullable=False)
    waba_id = Column(String(128), nullable=False)
    display_number = Column(String(32), nullable=False)
    label = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user_access = relationship("WhatsAppLineUserAccess", back_populates="line", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("provider", "phone_number_id", name="uq_whatsapp_lines_provider_phone_number_id"),
        UniqueConstraint("provider", "display_number", name="uq_whatsapp_lines_provider_display_number"),
    )


class WhatsAppLineUserAccess(Base):
    """Permisos por línea y por usuario (ver/enviar). Config viva, no historial → CASCADE."""
    __tablename__ = "whatsapp_line_user_access"

    id = Column(Integer, primary_key=True)
    line_id = Column(Integer, ForeignKey("whatsapp_lines.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    can_view = Column(Boolean, nullable=False, server_default=text("true"))
    can_send = Column(Boolean, nullable=False, server_default=text("true"))
    is_default = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    line = relationship("WhatsAppLine", back_populates="user_access")

    __table_args__ = (
        UniqueConstraint("line_id", "user_id", name="uq_whatsapp_line_user_access_line_user"),
        Index("ix_whatsapp_line_user_access_user_id", "user_id"),
        Index("ix_whatsapp_line_user_access_line_id", "line_id"),
    )


class WhatsAppContact(Base):
    """Persona GLOBAL (sin line_id). No se asume que siempre tenga teléfono."""
    __tablename__ = "whatsapp_contacts"

    id = Column(Integer, primary_key=True)
    display_name = Column(String(255), nullable=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    identifiers = relationship("WhatsAppContactIdentifier", back_populates="contact", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_whatsapp_contacts_lead_id", "lead_id"),
    )


class WhatsAppContactIdentifier(Base):
    """Identificadores de un contacto: wa_id | phone_e164 | bsuid. Dependientes → CASCADE."""
    __tablename__ = "whatsapp_contact_identifiers"

    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("whatsapp_contacts.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(32), nullable=False, default="meta")
    identifier_type = Column(String(32), nullable=False)
    identifier_value = Column(String(255), nullable=False)
    is_primary = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    contact = relationship("WhatsAppContact", back_populates="identifiers")

    __table_args__ = (
        UniqueConstraint("provider", "identifier_type", "identifier_value", name="uq_whatsapp_contact_identifiers_value"),
        Index("ix_whatsapp_contact_identifiers_contact_id", "contact_id"),
        Index("ix_whatsapp_contact_identifiers_identifier_value", "identifier_value"),
    )


class WhatsAppConversation(Base):
    """Hilo por (línea, contacto). status: open | closed | archived."""
    __tablename__ = "whatsapp_conversations"

    id = Column(Integer, primary_key=True)
    line_id = Column(Integer, ForeignKey("whatsapp_lines.id", ondelete="RESTRICT"), nullable=False)
    contact_id = Column(Integer, ForeignKey("whatsapp_contacts.id", ondelete="RESTRICT"), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(32), nullable=False, default="open")
    assignment_source = Column(String(32), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    last_inbound_at = Column(DateTime(timezone=True), nullable=True)
    customer_service_window_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    messages = relationship("WhatsAppMessage", back_populates="conversation", cascade="all, delete-orphan")
    reads = relationship("WhatsAppConversationRead", back_populates="conversation", cascade="all, delete-orphan")
    assignments = relationship("WhatsAppConversationAssignment", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("line_id", "contact_id", name="uq_whatsapp_conversations_line_contact"),
        Index("ix_whatsapp_conversations_assigned_status_last_msg", "assigned_user_id", "status", "last_message_at"),
        Index("ix_whatsapp_conversations_line_status_last_msg", "line_id", "status", "last_message_at"),
        Index("ix_whatsapp_conversations_lead_id", "lead_id"),
        Index("ix_whatsapp_conversations_contact_id", "contact_id"),
    )


class WhatsAppMessage(Base):
    """Mensaje in/out. Idempotencia por unique parcial de external_message_id / client_request_id.
    Los salientes se crean como 'pending' ANTES de llamar a Meta."""
    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(32), nullable=False, default="meta")
    external_message_id = Column(String(255), nullable=True)
    # UUID genérico (cross-dialect): nativo `uuid` en PostgreSQL, CHAR en SQLite (tests).
    client_request_id = Column(UUID(as_uuid=True), nullable=True)
    direction = Column(String(32), nullable=False)
    message_type = Column(String(32), nullable=False)
    text_body = Column(Text, nullable=True)
    current_status = Column(String(32), nullable=False, default="pending")
    context_external_message_id = Column(String(255), nullable=True)
    sender_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    origin = Column(String(32), nullable=False, default="unknown")
    provider_timestamp = Column(DateTime(timezone=True), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    error_code = Column(String(64), nullable=True)
    error_message_safe = Column(Text, nullable=True)

    conversation = relationship("WhatsAppConversation", back_populates="messages")
    status_events = relationship("WhatsAppMessageStatusEvent", back_populates="message", cascade="all, delete-orphan")

    __table_args__ = (
        # Idempotencia: unique PARCIAL (solo cuando el valor no es NULL).
        Index("uq_whatsapp_messages_provider_external_id", "provider", "external_message_id",
              unique=True, postgresql_where=text("external_message_id IS NOT NULL")),
        Index("uq_whatsapp_messages_client_request_id", "client_request_id",
              unique=True, postgresql_where=text("client_request_id IS NOT NULL")),
        Index("ix_whatsapp_messages_conversation_provider_ts", "conversation_id", "provider_timestamp"),
        Index("ix_whatsapp_messages_conversation_created_at", "conversation_id", "created_at"),
        Index("ix_whatsapp_messages_sender_user_id", "sender_user_id"),
        Index("ix_whatsapp_messages_current_status", "current_status"),
    )


class WhatsAppConversationRead(Base):
    """Estado de lectura POR usuario (no un unread_count global).
    La FK last_read_message_id → whatsapp_messages tiene nombre explícito y la migración la
    agrega con op.create_foreign_key() DESPUÉS de crear ambas tablas. No usa use_alter: no
    existe un ciclo real (whatsapp_messages no depende de whatsapp_conversation_reads), por lo
    que el orden topológico de create_all() alcanza y se evita ALTER ADD CONSTRAINT en SQLite."""
    __tablename__ = "whatsapp_conversation_reads"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    last_read_message_id = Column(
        Integer,
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL",
                   name="fk_whatsapp_conversation_reads_last_read_message_id"),
        nullable=True,
    )
    last_read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    conversation = relationship("WhatsAppConversation", back_populates="reads")

    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_whatsapp_conversation_reads_conversation_user"),
    )


class WhatsAppMessageStatusEvent(Base):
    """Eventos de estado (sent/delivered/read/failed). APPEND-ONLY. Dedupe por event_key."""
    __tablename__ = "whatsapp_message_status_events"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("whatsapp_messages.id", ondelete="CASCADE"), nullable=False)
    event_key = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False)
    provider_timestamp = Column(DateTime(timezone=True), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # JSONB en PostgreSQL; degrada a JSON en SQLite (solo para create_all() de los tests).
    safe_payload = Column(postgresql.JSONB().with_variant(JSON(), "sqlite"), nullable=True)

    message = relationship("WhatsAppMessage", back_populates="status_events")

    __table_args__ = (
        UniqueConstraint("event_key", name="uq_whatsapp_message_status_events_event_key"),
        Index("ix_whatsapp_message_status_events_message_id", "message_id"),
    )


class WhatsAppWebhookEvent(Base):
    """Cola/dedupe persistente de webhooks crudos. event_key determinístico (no ext_id)."""
    __tablename__ = "whatsapp_webhook_events"

    id = Column(Integer, primary_key=True)
    provider = Column(String(32), nullable=False, default="meta")
    event_key = Column(String(255), nullable=False)
    payload_hash = Column(String(64), nullable=True)
    event_type = Column(String(64), nullable=True)
    processing_status = Column(String(32), nullable=False, default="pending")
    attempt_count = Column(Integer, nullable=False, server_default=text("0"))
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    last_error_safe = Column(Text, nullable=True)
    raw_payload = Column(postgresql.JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    raw_payload_expires_at = Column(DateTime(timezone=True), nullable=True)
    # --- Etapa 1D: lease de reprocesamiento (migración b1e9d4c7f0a2) ---
    # processing_started_at: inicio del lease; detecta `processing` atascados tras crash.
    # next_retry_at: elegibilidad + backoff; evita reintentar poison pills cada corrida.
    # locked_by: trazabilidad del worker (NO sustituye el lock de PostgreSQL).
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    locked_by = Column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "event_key", name="uq_whatsapp_webhook_events_provider_event_key"),
        Index("ix_whatsapp_webhook_events_status_received", "processing_status", "received_at"),
        Index("ix_whatsapp_webhook_events_raw_payload_expires_at", "raw_payload_expires_at"),
        # Índices PARCIALES (PostgreSQL): en SQLite se crean completos, sin la cláusula
        # WHERE, que es funcionalmente equivalente para los tests.
        Index("ix_whatsapp_webhook_events_processing_lease", "processing_started_at",
              postgresql_where=text("processing_status = 'processing'")),
        Index("ix_whatsapp_webhook_events_retry_eligible", "next_retry_at", "received_at",
              postgresql_where=text("processing_status IN ('failed', 'pending')")),
    )


class WhatsAppConversationAssignment(Base):
    """Historial de asignaciones (auditoría). FKs a users en SET NULL para conservar historial."""
    __tablename__ = "whatsapp_conversation_assignments"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"), nullable=False)
    from_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assignment_source = Column(String(32), nullable=False)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    conversation = relationship("WhatsAppConversation", back_populates="assignments")

    __table_args__ = (
        Index("ix_whatsapp_conversation_assignments_conversation_created", "conversation_id", "created_at"),
        Index("ix_whatsapp_conversation_assignments_to_user_id", "to_user_id"),
    )
