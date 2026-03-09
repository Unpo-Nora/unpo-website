from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List

from .. import crud, schemas, models
from ..database import get_db
from ..utils.pdf_generator import generate_remito_pdf

router = APIRouter(
    prefix="/sales",
    tags=["Sales & Orders"]
)

@router.post("/", response_model=schemas.SaleOrder)
def create_sale_endpoint(order: schemas.SaleOrderCreate, db: Session = Depends(get_db)):
    """
    Creates a new Sale Order, deducts stock, and changes the lead status to CLIENT.
    """
    if order.total_amount < 100000:
        raise HTTPException(status_code=400, detail="Minimum order amount must be at least $100,000")
        
    db_lead = db.query(models.Lead).filter(models.Lead.id == order.lead_id).first()
    if not db_lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
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
def get_remito_pdf(order_id: int, db: Session = Depends(get_db)):
    db_order = crud.get_sale_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    pdf_bytes = generate_remito_pdf(db_order)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=remito_{order_id}.pdf"}
    )
    
@router.post("/{order_id}/cancel", response_model=schemas.SaleOrder)
def cancel_sale_endpoint(order_id: int, db: Session = Depends(get_db)):
    """
    Cancels a sale and restores the stock.
    """
    db_order = crud.cancel_sale_order(db=db, order_id=order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found or already canceled")
    return db_order

@router.get("/lead/{lead_id}", response_model=List[schemas.SaleOrder])
def read_sales_by_lead(lead_id: int, db: Session = Depends(get_db)):
    """
    Get all sales orders for a specific lead/client.
    """
    return crud.get_sale_orders_by_lead(db=db, lead_id=lead_id)
