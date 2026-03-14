from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
import shutil
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import crud, models, schemas, database
from PIL import Image as PILImage
import gc

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

@router.get("/fix-images")
def fix_all_images_endpoint(db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    import pathlib
    base_dir = pathlib.Path(__file__).parent.parent.parent
    img_dir = str(base_dir / "data" / "images")
    count = 0
    if not os.path.exists(img_dir):
        return {"status": "error", "message": "Image dir not found"}
    for p in products:
        sku_val = str(p.sku).strip()
        images = []
        for f in sorted(os.listdir(img_dir)):
            fname_lower = f.lower()
            if fname_lower.startswith(sku_val.lower()) and (len(fname_lower) == len(sku_val) or fname_lower[len(sku_val)] in ['.', '_', '-']):
                if os.path.splitext(f)[1].lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                    images.append(f"/static/images/{f}")
        images = list(dict.fromkeys(images))
        if images and (not p.images or set(p.images) != set(images)):
            p.images = images
            count += 1
    db.commit()
    return {"status": "success", "updated": count}

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

def optimize_all_images_bg():
    images_dir = "/app/data/images"
    if not os.path.exists(images_dir):
        return
        
    for filename in os.listdir(images_dir):
        if filename.startswith("."): 
            continue
        img_path = os.path.join(images_dir, filename)
        if os.path.isfile(img_path):
            try:
                PILImage.MAX_IMAGE_PIXELS = 25000000
                pil_img = PILImage.open(img_path)
                
                # If image is larger than 1000px, shrink to 1000px max (safe for PDF, small disk size)
                if max(pil_img.size) > 1000:
                    pil_img.thumbnail((1000, 1000))
                    
                    if pil_img.mode in ("RGBA", "CMYK", "LA", "P"):
                        background = PILImage.new('RGB', pil_img.size, (255, 255, 255))
                        if pil_img.mode in ('RGBA', 'LA'):
                            background.paste(pil_img, mask=pil_img.split()[-1])
                        else:
                            background.paste(pil_img)
                        pil_img.close()
                        pil_img = background
                    elif pil_img.mode != "RGB":
                        rgb_img = pil_img.convert("RGB")
                        pil_img.close()
                        pil_img = rgb_img
                        
                    pil_img.save(img_path, format='JPEG', quality=85, optimize=True)
                
                try:
                    pil_img.close()
                except:
                    pass
                    
                gc.collect()
            except Exception as e:
                print(f"Error optimizing {filename}: {e}")

@router.post("/optimize-images")
def trigger_image_optimization(
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No tiene permisos para optimizar imágenes")
    
    background_tasks.add_task(optimize_all_images_bg)
    return {"status": "success", "message": "Image optimization started in background"}

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
        
    db_product = crud.update_product(db, sku=sku, product_data=product.model_dump(exclude_unset=True))
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return db_product

@router.patch("/{sku}/stock", response_model=schemas.Product)
def adjust_stock(
    sku: str,
    adjustment_data: schemas.StockAdjustment,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "seller", "vendor", "vendedor"]:
        raise HTTPException(status_code=403, detail="No tiene permisos para modificar stock")
        
    db_product = crud.get_product(db, sku=sku)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
        
    db_product.stock_quantity += adjustment_data.adjustment
    if db_product.stock_quantity < 0:
        db_product.stock_quantity = 0
        
    db.commit()
    db.refresh(db_product)
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
