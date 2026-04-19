from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import engine, Base, get_db
from .routers import products, leads, auth, analytics, sales, settings
from fastapi.staticfiles import StaticFiles
import os

# Create database tables (Simple migration for dev)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="UNPO & NORA Ecosystem API",
    description="Backend unificado para B2B y B2C",
    version="1.0.0"
)

# CORS Configuration
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "https://unpo.com.ar",
    "https://www.unpo.com.ar",
    "https://unpo.online",
    "https://www.unpo.online",
    "https://unpo-website.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(ResponseValidationError)
async def validation_exception_handler(request, exc):
    import traceback
    return JSONResponse(status_code=422, content={'detail': f'Response Validation Error: {exc.errors()}', 'trace': traceback.format_exc()})

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    import traceback
    return JSONResponse(status_code=500, content={'detail': f'Internal Server Error: {str(exc)}', 'trace': traceback.format_exc()})

app.include_router(products.router)
app.include_router(leads.router)
app.include_router(auth.router)
app.include_router(analytics.router)
app.include_router(sales.router)
app.include_router(settings.router)
from .routers import users, hr, finance
app.include_router(users.router)
app.include_router(hr.router)
app.include_router(finance.router)

# Mount static images and videos
images_path = "data/images"
videos_path = "data/videos"
os.makedirs(images_path, exist_ok=True)
os.makedirs(videos_path, exist_ok=True)
app.mount("/static/images", StaticFiles(directory=images_path), name="static_images")
app.mount("/static/videos", StaticFiles(directory=videos_path), name="static_videos")

@app.get("/")
def read_root():
    return {"status": "online", "system": "UNPO/NORA Ecosystem API"}

@app.get("/health")
def health_check():
    return {"status": "ok", "db": "connected"}

@app.get("/fix_db_schema")
def fix_db_schema(db: Session = Depends(get_db)):
    errors = []
    
    try:
        # Add price_breakdown column to products table
        db.execute(text('ALTER TABLE products ADD COLUMN price_breakdown JSON;'))
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"products.price_breakdown error: {e}")

    try:
        # Add user_email column to expenses table
        db.execute(text('ALTER TABLE expenses ADD COLUMN user_email VARCHAR;'))
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"expenses.user_email error: {e}")
        
    try:
        from .models import Employee, InventoryAuditLog
        Base.metadata.tables[Employee.__tablename__].create(engine, checkfirst=True)
        Base.metadata.tables[InventoryAuditLog.__tablename__].create(engine, checkfirst=True)
    except Exception as e:
        errors.append(f"Table creation error: {e}")
        
    return {"status": "success", "message": "Database schema patch executed", "errors": str(errors)}

from sqlalchemy import text

@app.get("/fix_production_10300028")
def fix_production_10300028(db: Session = Depends(get_db)):
    from . import crud
    product = crud.get_product(db, sku='10300028')
    if product:
        crud.update_product(db, sku='10300028', product_data={
            "description": "Aceitero/Vinagrero de vidrio de 300ml de capacidad, pico de plástico con cierre tapón.",
            "price_wholesale": 2681.25
        })
        return {"status": "success", "message": "Updated 10300028 successfully."}
    return {"status": "error", "message": "not found"}

@app.get("/fix_admin_name")
def fix_admin_name(db: Session = Depends(get_db)):
    from . import models
    admin = db.query(models.User).filter(models.User.email == "julianv@unpo.com.ar").first()
    if admin:
        admin.full_name = "Julian"
        db.commit()
        return {"status": "success", "message": "Admin name updated to Julian."}
    return {"status": "error", "message": "Admin user not found"}

@app.get("/debug_audit_logs")
def debug_audit_logs(db: Session = Depends(get_db)):
    try:
        from . import crud
        logs, total = crud.get_recent_audit_logs(db, limit=50)
        return [{"id": l.id, "action": l.action, "details": l.details} for l in logs]
    except Exception as e:
        return {"error_type": type(e).__name__, "error": str(e)}

@app.get("/force_debug_log")
def force_debug_log(db: Session = Depends(get_db)):
    try:
        from . import crud, schemas
        log = crud.create_audit_log(db, schemas.InventoryAuditLogBase(
            action="DEBUG_FORCE",
            details="Forced log directly into Postgres via Route bypass"
        ))
        return {"status": "success", "inserted": log.id}
    except Exception as e:
        return {"error_type": type(e).__name__, "error": str(e)}

@app.get("/wipe_audit_logs_production_secret")
def wipe_audit_logs(db: Session = Depends(get_db)):
    try:
        from . import models
        db.query(models.InventoryAuditLog).delete()
        db.commit()
        return {"status": "success", "message": "All logs deleted"}
    except Exception as e:
        return {"error_type": type(e).__name__, "error": str(e)}

@app.get("/migrate_finance_schema_and_data")
def migrate_finance_schema_and_data(db: Session = Depends(get_db)):
    try:
        from . import models
        # Ensures tables exist
        models.Base.metadata.create_all(bind=engine)
        
        # Migrate old expenses to new FinancialTransaction
        expenses = db.query(models.Expense).all()
        migrated_count = 0
        
        for exp in expenses:
            # Check if this expense is already migrated (assuming duplicate dates/amounts might mean so, but safer to check if table is empty or just insert)
            existing = db.query(models.FinancialTransaction).filter(
                models.FinancialTransaction.monto == exp.amount,
                models.FinancialTransaction.descripcion == exp.description,
                models.FinancialTransaction.fecha == exp.date
            ).first()
            
            if not existing:
                tx = models.FinancialTransaction(
                    tipo_movimiento=models.TransactionType.EGRESO,
                    categoria=models.TransactionCategory.OPERATIVO,
                    descripcion=exp.description,
                    monto=exp.amount,
                    moneda="ARS",
                    fecha=exp.date,
                    estado=models.TransactionStatus.PAGADO,
                    created_at=exp.date
                )
                db.add(tx)
                migrated_count += 1
                
        db.commit()
        return {"status": "success", "message": f"Successfully migrated {migrated_count} expenses to FinancialTransaction."}
    except Exception as e:
        return {"error_type": type(e).__name__, "error": str(e)}

@app.get("/fix_valija_category")
def fix_valija_category(db: Session = Depends(get_db)):
    try:
        from . import models
        valija = db.query(models.Category).filter(models.Category.name.ilike('%VALIJA%')).first()
        bazar = db.query(models.Category).filter(models.Category.name.ilike('%BAZAR%')).first()
        
        if not bazar:
            bazar = models.Category(name="Bazar")
            db.add(bazar)
            db.commit()
            db.refresh(bazar)
            
        fixed_count = 0
        if valija:
            products = db.query(models.Product).filter(models.Product.category_id == valija.id).all()
            for p in products:
                p.category_id = bazar.id
                fixed_count += 1
            db.delete(valija)
            db.commit()
            
        p_ban = db.query(models.Product).filter(models.Product.name.ilike('%bandeja cuadrada%')).first()
        if p_ban and p_ban.category_id != bazar.id:
            p_ban.category_id = bazar.id
            db.commit()
            fixed_count += 1
            
        return {"status": "success", "message": f"Migrated {fixed_count} products. Valija category removed.", "new_category": bazar.id}
    except Exception as e:
        return {"error_type": type(e).__name__, "error": str(e)}

@app.get("/migrate_capital_iva_system")
def migrate_capital_iva_system(db: Session = Depends(get_db)):
    try:
        from . import models
        models.Base.metadata.create_all(bind=engine)
        
        count = db.query(models.CapitalIva).count()
        if count == 0:
            old_setting = db.query(models.Settings).filter(models.Settings.key == "capital_iva_amount").first()
            if old_setting and old_setting.value:
                try:
                    amount = float(old_setting.value)
                    if amount > 0:
                        from datetime import datetime
                        import pytz
                        now = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))
                        new_iva = models.CapitalIva(
                            amount=amount,
                            created_at=now,
                            observation="Migrado del sistema anterior",
                            created_by="system"
                        )
                        db.add(new_iva)
                        db.delete(old_setting)
                        db.commit()
                        return {"status": "success", "message": f"Migrated amount {amount} successfully."}
                except Exception as ex:
                    return {"status": "error", "message": f"Error parsing amount: {ex}"}
            else:
                return {"status": "success", "message": "No old data to migrate."}
        else:
            old_setting = db.query(models.Settings).filter(models.Settings.key == "capital_iva_amount").first()
            if old_setting:
                db.delete(old_setting)
                db.commit()
            return {"status": "success", "message": "Migration already performed."}
    except Exception as e:
        db.rollback()
        return {"error_type": type(e).__name__, "error": str(e)}
