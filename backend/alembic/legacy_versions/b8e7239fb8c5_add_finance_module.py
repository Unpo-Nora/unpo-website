"""add_finance_module

Revision ID: b8e7239fb8c5
Revises: a7da328604d3
Create Date: 2026-04-18 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b8e7239fb8c5'
down_revision: Union[str, None] = 'a7da328604d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create Enums if using postgres (sa.Enum handles this if we define the names, but sometimes we just create tables and let SQLAlchemy map it)
    
    transaction_type_enum = postgresql.ENUM('INGRESO', 'EGRESO', 'CUENTA_POR_PAGAR', 'PAGO', name='transactiontype')
    if op.get_context().dialect.name == 'postgresql':
        transaction_type_enum.create(op.get_bind(), checkfirst=True)
        
    transaction_category_enum = postgresql.ENUM('MERCADERIA', 'DEPOSITO', 'OPERATIVO', 'LOGISTICA', 'IMPUESTOS', 'OTROS', name='transactioncategory')
    if op.get_context().dialect.name == 'postgresql':
        transaction_category_enum.create(op.get_bind(), checkfirst=True)
        
    transaction_status_enum = postgresql.ENUM('PENDIENTE', 'PAGADO', 'VENCIDO', name='transactionstatus')
    if op.get_context().dialect.name == 'postgresql':
        transaction_status_enum.create(op.get_bind(), checkfirst=True)
        
    purchase_payment_enum = postgresql.ENUM('CONTADO', '30_DIAS', '60_DIAS', name='purchasepaymenttype')
    if op.get_context().dialect.name == 'postgresql':
        purchase_payment_enum.create(op.get_bind(), checkfirst=True)
        
    purchase_status_enum = postgresql.ENUM('PENDIENTE', 'PARCIAL', 'PAGADO', name='purchasestatus')
    if op.get_context().dialect.name == 'postgresql':
        purchase_status_enum.create(op.get_bind(), checkfirst=True)
        
    cost_type_enum = postgresql.ENUM('PRODUCTO', 'FLETE', 'IMPUESTOS', 'OTROS', name='costtype')
    if op.get_context().dialect.name == 'postgresql':
        cost_type_enum.create(op.get_bind(), checkfirst=True)


    op.create_table('suppliers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(), nullable=False),
        sa.Column('contacto', sa.String(), nullable=True),
        sa.Column('telefono', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_suppliers_id'), 'suppliers', ['id'], unique=False)
    op.create_index(op.f('ix_suppliers_nombre'), 'suppliers', ['nombre'], unique=False)

    op.create_table('purchases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proveedor_id', sa.Integer(), nullable=True),
        sa.Column('descripcion', sa.String(), nullable=True),
        sa.Column('cantidad_total', sa.Integer(), nullable=True),
        sa.Column('monto_total', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('moneda', sa.String(), nullable=True),
        sa.Column('fecha_compra', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tipo_pago', sa.Enum('CONTADO', '30_DIAS', '60_DIAS', name='purchasepaymenttype'), nullable=True),
        sa.Column('estado', sa.Enum('PENDIENTE', 'PARCIAL', 'PAGADO', name='purchasestatus'), nullable=True),
        sa.ForeignKeyConstraint(['proveedor_id'], ['suppliers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchases_id'), 'purchases', ['id'], unique=False)

    op.create_table('purchase_cost_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('compra_id', sa.Integer(), nullable=False),
        sa.Column('tipo_costo', sa.Enum('PRODUCTO', 'FLETE', 'IMPUESTOS', 'OTROS', name='costtype'), nullable=False),
        sa.Column('monto', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['compra_id'], ['purchases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchase_cost_details_id'), 'purchase_cost_details', ['id'], unique=False)

    op.create_table('purchase_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('compra_id', sa.Integer(), nullable=False),
        sa.Column('product_sku', sa.String(), nullable=False),
        sa.Column('cantidad', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['compra_id'], ['purchases.id'], ),
        sa.ForeignKeyConstraint(['product_sku'], ['products.sku'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchase_items_id'), 'purchase_items', ['id'], unique=False)

    op.create_table('financial_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tipo_movimiento', sa.Enum('INGRESO', 'EGRESO', 'CUENTA_POR_PAGAR', 'PAGO', name='transactiontype'), nullable=False),
        sa.Column('categoria', sa.Enum('MERCADERIA', 'DEPOSITO', 'OPERATIVO', 'LOGISTICA', 'IMPUESTOS', 'OTROS', name='transactioncategory'), nullable=False),
        sa.Column('descripcion', sa.String(), nullable=False),
        sa.Column('monto', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('moneda', sa.String(), nullable=True),
        sa.Column('fecha', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fecha_vencimiento', sa.DateTime(timezone=True), nullable=True),
        sa.Column('estado', sa.Enum('PENDIENTE', 'PAGADO', 'VENCIDO', name='transactionstatus'), nullable=True),
        sa.Column('proveedor_id', sa.Integer(), nullable=True),
        sa.Column('compra_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['proveedor_id'], ['suppliers.id'], ),
        sa.ForeignKeyConstraint(['compra_id'], ['purchases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_financial_transactions_id'), 'financial_transactions', ['id'], unique=False)

    # Migrate data from expenses to financial_transactions
    connection = op.get_bind()
    expenses = connection.execute(sa.text("SELECT id, amount, description, date FROM expenses")).fetchall()
    
    for exp in expenses:
        # Defaults based on rules: type EGRESO, category OPERATIVO, currency ARS, status PAGADO
        connection.execute(sa.text(
            "INSERT INTO financial_transactions (tipo_movimiento, categoria, descripcion, monto, moneda, fecha, estado, created_at) "
            "VALUES (:tipo, :cat, :desc, :monto, :moneda, :fecha, :estado, :created)"
        ), {
            "tipo": "EGRESO",
            "cat": "OPERATIVO",
            "desc": exp.description,
            "monto": exp.amount,
            "moneda": "ARS",
            "fecha": exp.date,
            "estado": "PAGADO",
            "created": exp.date
        })

def downgrade() -> None:
    op.drop_index(op.f('ix_financial_transactions_id'), table_name='financial_transactions')
    op.drop_table('financial_transactions')
    
    op.drop_index(op.f('ix_purchase_items_id'), table_name='purchase_items')
    op.drop_table('purchase_items')
    
    op.drop_index(op.f('ix_purchase_cost_details_id'), table_name='purchase_cost_details')
    op.drop_table('purchase_cost_details')
    
    op.drop_index(op.f('ix_purchases_id'), table_name='purchases')
    op.drop_table('purchases')
    
    op.drop_index(op.f('ix_suppliers_nombre'), table_name='suppliers')
    op.drop_index(op.f('ix_suppliers_id'), table_name='suppliers')
    op.drop_table('suppliers')

    if op.get_context().dialect.name == 'postgresql':
        postgresql.ENUM(name='transactiontype').drop(op.get_bind(), checkfirst=True)
        postgresql.ENUM(name='transactioncategory').drop(op.get_bind(), checkfirst=True)
        postgresql.ENUM(name='transactionstatus').drop(op.get_bind(), checkfirst=True)
        postgresql.ENUM(name='purchasepaymenttype').drop(op.get_bind(), checkfirst=True)
        postgresql.ENUM(name='purchasestatus').drop(op.get_bind(), checkfirst=True)
        postgresql.ENUM(name='costtype').drop(op.get_bind(), checkfirst=True)
