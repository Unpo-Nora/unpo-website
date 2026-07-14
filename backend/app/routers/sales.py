from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List

from .. import crud, schemas, models
from ..database import get_db
from ..dependencies.permissions import require_roles
from ..utils.pdf_generator import generate_remito_pdf

router = APIRouter(
    prefix="/sales",
    tags=["Sales & Orders"]
)


def _assert_can_access_order(db_order: models.SaleOrder, current_user: models.User) -> None:
    """
    Ownership para recursos identificados por order_id (lectura de remito y cancelación).

    El vendedor solo puede operar sobre órdenes cuyo lead le pertenece
    (`lead.seller == current_user.email`). Si la orden es de otro vendedor se responde
    404 (no 403) para NO revelar la existencia de recursos ajenos accedidos por id
    opaco. El admin tiene acceso global.
    """
    if current_user.role == "admin":
        return
    lead = db_order.lead
    if lead is None or lead.seller != current_user.email:
        raise HTTPException(status_code=404, detail="Order not found")


@router.post("/", response_model=schemas.SaleOrder)
def create_sale_endpoint(
    order: schemas.SaleOrderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin", "vendedor")),
):
    """
    Creates a new Sale Order, deducts stock, and changes the lead status to CLIENT.

    Requiere autenticación (admin o vendedor). Un vendedor solo puede cerrar ventas
    sobre leads que le pertenecen; el ownership se valida ANTES de verificar o modificar
    stock. Las reglas comerciales (mínimo, validación/descuento de stock, cambio a
    CLIENT, remito) no se modifican.
    """
    if order.total_amount < 100000:
        raise HTTPException(status_code=400, detail="Minimum order amount must be at least $100,000")

    db_lead = db.query(models.Lead).filter(models.Lead.id == order.lead_id).first()
    if not db_lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Ownership: se valida antes de tocar stock o el lead.
    if current_user.role != "admin":
        if not db_lead.seller:
            # Lead global/NEW sin tomar: debe pasar primero por el flujo oficial de toma
            # (PUT /leads/{id}/mark-contacted). No se permite cerrarlo directamente.
            raise HTTPException(
                status_code=403,
                detail="El lead está sin asignar. Tomalo primero (marcar contactado) antes de cerrar la venta.",
            )
        if db_lead.seller != current_user.email:
            raise HTTPException(
                status_code=403,
                detail="No podés cerrar una venta sobre un lead de otro vendedor.",
            )

    # Verify stock before proceeding
    for item in order.items:
        db_product = crud.get_product(db, item.product_sku)
        if not db_product:
            raise HTTPException(status_code=404, detail=f"Product SKU {item.product_sku} not found")
        if db_product.stock_quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for SKU {item.product_sku}. Requested: {item.quantity}, Available: {db_product.stock_quantity}")

    # Modify lead info with new details if present (billing address, etc.)
    if order.dni_cuit:
        db_lead.dni_cuit = order.dni_cuit
    if order.address:
        db_lead.address = order.address
    if order.locality:
        db_lead.locality = order.locality
    if order.province:
        db_lead.province = order.province
    if order.zip_code:
        db_lead.zip_code = order.zip_code

    # Change lead status to CLIENT
    db_lead.status = models.LeadStatus.CLIENT
    db.commit()

    # Create the sale order
    new_order = crud.create_sale_order(db=db, order=order)
    return new_order

@router.get("/{order_id}/pdf")
def get_remito_pdf(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin", "vendedor")),
):
    db_order = crud.get_sale_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Ownership antes de generar el PDF (el remito contiene datos personales del cliente).
    _assert_can_access_order(db_order, current_user)

    pdf_bytes = generate_remito_pdf(db_order)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=remito_{order_id}.pdf"}
    )

@router.post("/{order_id}/cancel", response_model=schemas.SaleOrder)
def cancel_sale_endpoint(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin", "vendedor")),
):
    """
    Cancels a sale and restores the stock. Requiere ownership (o admin).
    """
    db_order = crud.get_sale_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Ownership antes de cancelar / restaurar stock.
    _assert_can_access_order(db_order, current_user)

    canceled = crud.cancel_sale_order(db=db, order_id=order_id)
    if not canceled:
        raise HTTPException(status_code=404, detail="Order not found or already canceled")
    return canceled

@router.get("/lead/{lead_id}", response_model=List[schemas.SaleOrder])
def read_sales_by_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin", "vendedor")),
):
    """
    Get all sales orders for a specific lead/client. Un vendedor solo puede consultar
    las ventas de leads que le pertenecen; si el lead es ajeno se responde 404.
    """
    db_lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not db_lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if current_user.role != "admin" and db_lead.seller != current_user.email:
        raise HTTPException(status_code=404, detail="Lead not found")

    return crud.get_sale_orders_by_lead(db=db, lead_id=lead_id)
