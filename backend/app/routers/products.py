from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
import shutil
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import crud, models, schemas, database
from PIL import Image as PILImage
import gc
import os
from supabase import create_client, Client

router = APIRouter(
    prefix="/products",
    tags=["products"]
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "products")

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    img_dir = "data/images"
    count = 0
    if not os.path.exists(img_dir):
        return {"status": "error", "message": "Image dir not found"}
        
    debug_files = os.listdir(img_dir)
    
    for p in products:
        sku_val = str(p.sku).strip()
        images = []
        for f in debug_files:
            fname_lower = f.lower()
            if fname_lower.startswith(sku_val.lower()) and (len(fname_lower) == len(sku_val) or fname_lower[len(sku_val)] in ['.', '_', '-']):
                if os.path.splitext(f)[1].lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                    images.append(f"/static/images/{f}")
        images = list(dict.fromkeys(images))
        if images and (not p.images or set(p.images) != set(images)):
            p.images = images
            count += 1
    db.commit()
    return {
        "status": "success", 
        "updated": count, 
        "debug_img_dir": img_dir,
        "debug_files_count": len(debug_files),
        "debug_files_sample": debug_files[:10]
    }

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
    
    # Obtener el tipo de cambio manual para los precios en ARS
    rate_setting = crud.get_setting(db, key="manual_exchange_rate")
    exchange_rate = float(rate_setting.value) if rate_setting else 1450.0
    
    pdf_bytes = generate_catalog_pdf(products, exchange_rate=exchange_rate)
    
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
    images_dir = "data/images"
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
    
    new_product = crud.create_product(db=db, product=product)
    crud.create_audit_log(db, schemas.InventoryAuditLogBase(
        user_email=current_user.email,
        action="NEW_PRODUCT",
        details=f"Producto creado: {new_product.sku} ({new_product.name})"
    ))
    return new_product

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
        
    crud.create_audit_log(db, schemas.InventoryAuditLogBase(
        user_email=current_user.email,
        action="PRODUCT_EDITED",
        details=f"Producto editado: {db_product.name} (SKU: {sku})"
    ))
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
    
    crud.create_audit_log(db, schemas.InventoryAuditLogBase(
        user_email=current_user.email,
        action="STOCK_ADJUSTMENT",
        details=f"Stock de {sku} ajustado: {adjustment_data.adjustment:+d}. Nuevo total: {db_product.stock_quantity}"
    ))
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
        
    crud.create_audit_log(db, schemas.InventoryAuditLogBase(
        user_email=current_user.email,
        action="ARCHIVE_PRODUCT",
        details=f"Producto archivado: {sku}"
    ))
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
    
    image_url = ""

    if supabase:
        try:
            # Subir a Supabase Storage
            file_bytes = await file.read()
            res = supabase.storage.from_(SUPABASE_BUCKET).upload(
                path=filename,
                file=file_bytes,
                file_options={"content-type": file.content_type}
            )
            # Obtener URL pública
            public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
            image_url = public_url
        except Exception as e:
            print(f"Error uploading to Supabase: {e}")
            raise HTTPException(status_code=500, detail="Error al subir la imagen a la nube")
    else:
        # Fallback local (Save file)
        images_dir = "data/images"
        os.makedirs(images_dir, exist_ok=True)
        file_path = os.path.join(images_dir, filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Public URL
        image_url = f"/static/images/{filename}"
    
    # Update product images in database. Must create a new list for SQLAlchemy to detect changes.
    current_images = list(db_product.images or [])
    current_images.append(image_url)
    
    crud.update_product(db, sku=sku, product_data={"images": current_images})
    
    return {"status": "success", "url": image_url, "images": current_images}

from pydantic import BaseModel
from typing import Dict, Any

class BatchUpdateRequest(BaseModel):
    stock_adjustments: Dict[str, int] = {}
    price_updates: Dict[str, float] = {}
    new_exchange_rate: Optional[str] = None
    new_products: List[schemas.ProductCreate] = []

@router.post("/batch_update")
def batch_update_inventory(
    request: BatchUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "seller", "vendor", "vendedor"]:
        raise HTTPException(status_code=403, detail="No tiene permisos")
    
    actions_taken = []
    
    if request.new_exchange_rate:
        crud.update_setting(db, "manual_exchange_rate", request.new_exchange_rate)
        actions_taken.append(f"Dólar actualizado a: ${request.new_exchange_rate}")
        crud.create_audit_log(db, schemas.InventoryAuditLogBase(
            user_email=current_user.email,
            action="EXCHANGE_RATE",
            details=f"Actualizó cotización del dólar a ${request.new_exchange_rate}"
        ))

    for sku, adjustment in request.stock_adjustments.items():
        if adjustment == 0: continue
        product = crud.get_product(db, sku)
        if product:
            product.stock_quantity = max(0, (product.stock_quantity or 0) + adjustment)
            crud.create_audit_log(db, schemas.InventoryAuditLogBase(
                user_email=current_user.email,
                action="STOCK_UPDATE",
                details=f"Stock de {product.name} (SKU: {sku}) ajustado en {adjustment} (Quedan: {product.stock_quantity})"
            ))
            actions_taken.append(f"Stock {sku}: {adjustment}")
            
    for sku, new_price in request.price_updates.items():
        product = crud.get_product(db, sku)
        if product and float(product.price_usd or 0) != float(new_price):
            product.price_usd = new_price
            crud.create_audit_log(db, schemas.InventoryAuditLogBase(
                user_email=current_user.email,
                action="PRICE_UPDATE",
                details=f"Precio USD de {product.name} (SKU: {sku}) actualizado a ${new_price}"
            ))
            actions_taken.append(f"Precio {sku} actualizado")

    for new_prod in request.new_products:
        existing = crud.get_product(db, sku=new_prod.sku)
        if not existing:
            # We don't use crud.create_product because it does db.commit itself, 
            # modifying state. Let's do it safely.
            db_product = models.Product(**new_prod.model_dump())
            db.add(db_product)
            crud.create_audit_log(db, schemas.InventoryAuditLogBase(
                user_email=current_user.email,
                action="NEW_PRODUCT",
                details=f"Producto nuevo creado: {new_prod.sku} ({new_prod.name})"
            ))
            actions_taken.append(f"Producto {new_prod.sku} creado")
            
    db.commit()
    return {"status": "success", "messages": actions_taken}

@router.get("/audit_logs")
def get_audit_logs(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "seller", "vendor", "vendedor"]:
        raise HTTPException(status_code=403, detail="No tiene permisos")
    try:
        logs = crud.get_recent_audit_logs(db, limit)
        return [
            {
                "id": log.id,
                "user_email": log.user_email,
                "action": log.action,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ]
    except Exception as e:
        return {"error": str(e), "data": "crashed"}
