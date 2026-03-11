from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
import shutil
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import crud, models, schemas, database

router = APIRouter(
    prefix="/products",
    tags=["products"]
)

# Dependency
get_db = database.get_db

from .auth import get_current_user
from ..utils.product_importer import sync_products_from_excel
from ..utils.pdf_generator import generate_catalog_pdf
from fastapi.responses import Response
import os

@router.get("/catalog/pdf")
def download_catalog_pdf(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Genera y descarga un PDF del catálogo con productos en stock. Solo Staff.
    """
    if current_user.role not in ["admin", "seller", "vendor", "vendedor"]:
        raise HTTPException(status_code=403, detail="No tiene permisos para descargar el catálogo")
        
    products = crud.get_products(db, in_stock=True, limit=1000)
    
    pdf_bytes = generate_catalog_pdf(products)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Catalogo_UNPO_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )

@router.post("/sync")
def sync_products(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Sincroniza el catálogo de productos con el archivo Excel maestro. Solo Admins.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tiene permisos para realizar esta acción")
        
    excel_path = "/app/data/Panel_control_UNPO.xlsm"
    
    if not os.path.exists(excel_path):
        # Fallback for local dev without docker
        excel_path = os.path.join("backend", "data", "Panel_control_UNPO.xlsm")
        
    result = sync_products_from_excel(db, excel_path)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result

@router.get("/categories", response_model=List[schemas.Category])
def read_categories(db: Session = Depends(get_db)):
    return crud.get_categories(db)

@router.post("/categories", response_model=schemas.Category)
def create_category(
    category: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tiene permisos para crear categorías")
        
    db_cat = models.Category(name=category.name)
    db.add(db_cat)
    db.commit()
    db.refresh(db_cat)
    return db_cat

@router.get("/", response_model=List[schemas.Product])
def read_products(
    skip: int = 0, 
    limit: int = 200, 
    brand: Optional[str] = None, 
    category_id: Optional[int] = None,
    in_stock: bool = False,
    db: Session = Depends(get_db)
):
    products = crud.get_products(db, skip=skip, limit=limit, brand_slug=brand, category_id=category_id, in_stock=in_stock)
    return products

@router.get("/{sku}", response_model=schemas.Product)
def read_product(sku: str, db: Session = Depends(get_db)):
    db_product = crud.get_product(db, sku=sku)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@router.post("/", response_model=schemas.Product)
def create_product(
    product: schemas.ProductCreate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tiene permisos para crear productos")
        
    db_product = crud.get_product(db, sku=product.sku)
    if db_product:
        raise HTTPException(status_code=400, detail="Product already exists")
    return crud.create_product(db=db, product=product)

@router.put("/{sku}", response_model=schemas.Product)
def update_product(
    sku: str,
    product: schemas.ProductCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tiene permisos para editar productos")
        
    db_product = crud.update_product(db, sku=sku, product_data=product.model_dump())
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@router.delete("/{sku}", response_model=schemas.Product)
def archive_product(
    sku: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tiene permisos para archivar productos")
        
    db_product = crud.archive_product(db, sku=sku)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@router.delete("/{sku}/hard")
def hard_delete_product(
    sku: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tiene permisos para eliminar productos")
        
    db_product = crud.get_product(db, sku=sku)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
        
    db.delete(db_product)
    db.commit()
    return {"status": "success", "message": "Product permanently deleted"}

@router.post("/{sku}/images")
async def upload_product_image(
    sku: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tiene permisos para subir imágenes")
    
    db_product = crud.get_product(db, sku=sku)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # Generate unique filename
    ext = file.filename.split('.')[-1]
    filename = f"{sku}_{uuid.uuid4().hex[:8]}.{ext}"
    
    # Save file
    images_dir = "/app/data/images"
    os.makedirs(images_dir, exist_ok=True)
    file_path = os.path.join(images_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Public URL
    image_url = f"/static/images/{filename}"
    
    # Update product images in database
    current_images = db_product.images or []
    current_images.append(image_url)
    
    crud.update_product(db, sku=sku, product_data={"images": current_images})
    
    return {"status": "success", "url": image_url, "images": current_images}
