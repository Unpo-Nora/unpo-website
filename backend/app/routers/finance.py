from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional
from datetime import datetime, timedelta
import pytz

from .. import models, schemas, database, crud
from ..dependencies.permissions import require_roles

router = APIRouter(
    prefix="/finance",
    tags=["finance"]
)

get_db = database.get_db

def _get_ar_time():
    return datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))

# --- Exchange Rate Helper ---
def _get_exchange_rate(db: Session) -> float:
    rate_setting = crud.get_setting(db, key="manual_exchange_rate")
    return float(rate_setting.value) if rate_setting else 1450.0

# --- Middleware: Auto-update overdue transactions ---
def _update_overdue_transactions(db: Session):
    now = _get_ar_time()
    overdue_txs = db.query(models.FinancialTransaction).filter(
        models.FinancialTransaction.estado == models.TransactionStatus.PENDIENTE,
        models.FinancialTransaction.fecha_vencimiento != None,
        models.FinancialTransaction.fecha_vencimiento < now
    ).all()
    
    if overdue_txs:
        for tx in overdue_txs:
            tx.estado = models.TransactionStatus.VENCIDO
        db.commit()

# --- SUPPLIERS ---

@router.get("/suppliers", response_model=List[schemas.Supplier])
def get_suppliers(db: Session = Depends(get_db), current_user: models.User = Depends(require_roles("admin"))):
    return db.query(models.Supplier).all()

@router.post("/suppliers", response_model=schemas.Supplier)
def create_supplier(supplier: schemas.SupplierCreate, db: Session = Depends(get_db), current_user: models.User = Depends(require_roles("admin"))):
    db_supplier = models.Supplier(**supplier.model_dump())
    db.add(db_supplier)
    db.commit()
    db.refresh(db_supplier)
    return db_supplier

# --- FINANCIAL TRANSACTIONS ---

@router.get("/financial-transactions", response_model=List[schemas.FinancialTransaction])
def get_transactions(
    tipo: Optional[str] = None,
    categoria: Optional[str] = None,
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    _update_overdue_transactions(db)
    
    query = db.query(models.FinancialTransaction)
    if tipo:
        query = query.filter(models.FinancialTransaction.tipo_movimiento == tipo)
    if categoria:
        query = query.filter(models.FinancialTransaction.categoria == categoria)
    if estado:
        query = query.filter(models.FinancialTransaction.estado == estado)
        
    return query.order_by(models.FinancialTransaction.fecha.desc()).all()

@router.post("/financial-transactions", response_model=schemas.FinancialTransaction)
def create_transaction(
    tx: schemas.FinancialTransactionCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    if tx.tipo_movimiento == models.TransactionType.INGRESO and tx.estado != models.TransactionStatus.PAGADO:
        tx.estado = models.TransactionStatus.PAGADO
    elif tx.tipo_movimiento == models.TransactionType.EGRESO and tx.estado != models.TransactionStatus.PAGADO:
        tx.estado = models.TransactionStatus.PAGADO
    elif tx.tipo_movimiento == models.TransactionType.PAGO and tx.estado != models.TransactionStatus.PAGADO:
        tx.estado = models.TransactionStatus.PAGADO
    elif tx.tipo_movimiento == models.TransactionType.CUENTA_POR_PAGAR and tx.estado != models.TransactionStatus.PENDIENTE:
        tx.estado = models.TransactionStatus.PENDIENTE

    db_tx = models.FinancialTransaction(**tx.model_dump())
    if not db_tx.fecha:
        db_tx.fecha = _get_ar_time()
        
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx

# --- PURCHASES ---

@router.post("/purchases", response_model=schemas.Purchase)
def create_purchase(
    purchase_data: schemas.PurchaseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    # Calculate totals
    total_cost = sum(d.monto for d in purchase_data.cost_details)
    db_purchase = models.Purchase(
        proveedor_id=purchase_data.proveedor_id,
        descripcion=purchase_data.descripcion,
        cantidad_total=purchase_data.cantidad_total,
        monto_total=total_cost, # Derived from costs
        moneda=purchase_data.moneda,
        tipo_pago=purchase_data.tipo_pago,
        fecha_compra=purchase_data.fecha_compra or _get_ar_time(),
        estado=models.PurchaseStatus.PAGADO if purchase_data.tipo_pago == models.PurchasePaymentType.CONTADO else models.PurchaseStatus.PENDIENTE
    )
    db.add(db_purchase)
    db.commit()
    db.refresh(db_purchase)

    # Insert costs
    for cd in purchase_data.cost_details:
        db_cd = models.PurchaseCostDetail(
            compra_id=db_purchase.id,
            tipo_costo=cd.tipo_costo,
            monto=cd.monto
        )
        db.add(db_cd)
        
    # Insert items
    for item in purchase_data.items:
        db_item = models.PurchaseItem(
            compra_id=db_purchase.id,
            product_sku=item.product_sku,
            cantidad=item.cantidad
        )
        db.add(db_item)
        
    # Generate Financial Transaction
    now = db_purchase.fecha_compra
    if purchase_data.tipo_pago == models.PurchasePaymentType.CONTADO:
        tx = models.FinancialTransaction(
            tipo_movimiento=models.TransactionType.EGRESO,
            categoria=models.TransactionCategory.MERCADERIA,
            descripcion=f"Compra Contado - {purchase_data.descripcion}",
            monto=total_cost,
            moneda=purchase_data.moneda,
            fecha=now,
            estado=models.TransactionStatus.PAGADO,
            proveedor_id=purchase_data.proveedor_id,
            compra_id=db_purchase.id
        )
        db.add(tx)
    else:
        days = 30 if purchase_data.tipo_pago == models.PurchasePaymentType.DIAS_30 else 60
        due_date = now + timedelta(days=days)
        tx = models.FinancialTransaction(
            tipo_movimiento=models.TransactionType.CUENTA_POR_PAGAR,
            categoria=models.TransactionCategory.MERCADERIA,
            descripcion=f"Compra a Plazo ({days} días) - {purchase_data.descripcion}",
            monto=total_cost,
            moneda=purchase_data.moneda,
            fecha=now,
            fecha_vencimiento=due_date,
            estado=models.TransactionStatus.PENDIENTE,
            proveedor_id=purchase_data.proveedor_id,
            compra_id=db_purchase.id
        )
        db.add(tx)

    db.commit()
    db.refresh(db_purchase)
    return _populate_purchase_real_cost(db_purchase)

def _populate_purchase_real_cost(purchase: models.Purchase):
    total_cost = sum([float(c.monto) for c in purchase.cost_details])
    qty = purchase.cantidad_total
    
    # Need to return dict or map obj to schema format.
    # We can assign attributes directly if schema accepts it (from_attributes=True)
    if qty and qty > 0:
        purchase.costo_real_unitario = total_cost / float(qty)
    else:
        purchase.costo_real_unitario = 0.0
    return purchase

@router.get("/purchases", response_model=List[schemas.Purchase])
def get_purchases(db: Session = Depends(get_db), current_user: models.User = Depends(require_roles("admin"))):
    purchases = db.query(models.Purchase).order_by(models.Purchase.fecha_compra.desc()).all()
    return [_populate_purchase_real_cost(p) for p in purchases]

@router.get("/purchases/{purchase_id}", response_model=schemas.Purchase)
def get_purchase(purchase_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_roles("admin"))):
    purchase = db.query(models.Purchase).filter(models.Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    return _populate_purchase_real_cost(purchase)

@router.post("/purchases/{purchase_id}/pay")
def pay_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    purchase = db.query(models.Purchase).filter(models.Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
        
    if purchase.estado == models.PurchaseStatus.PAGADO:
        raise HTTPException(status_code=400, detail="La compra ya se encuentra pagada")

    # Update Purchase
    purchase.estado = models.PurchaseStatus.PAGADO
    
    # Update Original Transaction(s)
    debt_txs = db.query(models.FinancialTransaction).filter(
        models.FinancialTransaction.compra_id == purchase_id,
        models.FinancialTransaction.tipo_movimiento == models.TransactionType.CUENTA_POR_PAGAR,
        models.FinancialTransaction.estado != models.TransactionStatus.PAGADO
    ).all()
    
    for d_tx in debt_txs:
        d_tx.estado = models.TransactionStatus.PAGADO
        
    # Create Pago Transaction
    pago_tx = models.FinancialTransaction(
        tipo_movimiento=models.TransactionType.PAGO,
        categoria=models.TransactionCategory.MERCADERIA,
        descripcion=f"Pago de Deuda - {purchase.descripcion}",
        monto=purchase.monto_total,
        moneda=purchase.moneda,
        fecha=_get_ar_time(),
        estado=models.TransactionStatus.PAGADO,
        proveedor_id=purchase.proveedor_id,
        compra_id=purchase.id
    )
    db.add(pago_tx)
    db.commit()
    return {"status": "ok", "message": "Compra pagada y registrada en el flujo de caja."}

# --- DASHBOARD METRICS ---

@router.get("/dashboard/finance")
def get_finance_dashboard(db: Session = Depends(get_db), current_user: models.User = Depends(require_roles("admin"))):
    _update_overdue_transactions(db)
    exchange_rate = _get_exchange_rate(db)
    
    txs = db.query(models.FinancialTransaction).all()
    
    ingresos = 0.0
    egresos = 0.0
    cuentas_por_pagar_pendientes = 0.0
    cuentas_por_pagar_vencidas = 0.0
    
    # Egresos desglose
    gastos_por_categoria = {}

    for tx in txs:
        monto_ars = float(tx.monto)
        if tx.moneda == "USD":
            monto_ars *= exchange_rate
            
        if tx.tipo_movimiento == models.TransactionType.INGRESO:
            ingresos += monto_ars
        elif tx.tipo_movimiento == models.TransactionType.EGRESO or tx.tipo_movimiento == models.TransactionType.PAGO:
            egresos += monto_ars
            cat = str(tx.categoria.value)
            gastos_por_categoria[cat] = gastos_por_categoria.get(cat, 0.0) + monto_ars
            
        elif tx.tipo_movimiento == models.TransactionType.CUENTA_POR_PAGAR:
            if tx.estado == models.TransactionStatus.PENDIENTE:
                cuentas_por_pagar_pendientes += monto_ars
            elif tx.estado == models.TransactionStatus.VENCIDO:
                cuentas_por_pagar_vencidas += monto_ars

    balance = ingresos - egresos

    gastos_list = [{"categoria": k, "monto_ars": v} for k, v in gastos_por_categoria.items()]
    gastos_list.sort(key=lambda x: x["monto_ars"], reverse=True)

    return {
        "ingresos_ars": ingresos,
        "egresos_ars": egresos,
        "balance_ars": balance,
        "cuentas_por_pagar_pendientes_ars": cuentas_por_pagar_pendientes,
        "cuentas_por_pagar_vencidas_ars": cuentas_por_pagar_vencidas,
        "gastos_por_categoria": gastos_list,
        "exchange_rate": exchange_rate
    }
