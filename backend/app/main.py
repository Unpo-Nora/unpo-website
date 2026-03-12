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

app.include_router(products.router)
app.include_router(leads.router)
app.include_router(auth.router)
app.include_router(analytics.router)
app.include_router(sales.router)
app.include_router(settings.router)
from .routers import users
app.include_router(users.router)

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
