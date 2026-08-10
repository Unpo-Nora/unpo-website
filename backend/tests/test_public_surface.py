"""
Tests de la superficie pública de la API (products/settings).

Cubre el hardening aplicado tras la auditoría 2026-08:
- GET /products/ y GET /products/{sku} sirven la vista pública (`ProductPublic`,
  sin cost_price / provider_name / precios internos) a visitantes anónimos, y el
  producto completo (`Product`) al staff autenticado.
- GET /settings/{key} exige autenticación: `manual_exchange_rate` es legible por
  cualquier staff; el resto de claves, solo por admin.
- GET /settings/capital_ivas/list es solo admin (igual que sus hermanos POST/DELETE).

Mismo aislamiento que test_security_phase0a: SQLite en memoria (StaticPool),
esquema desde Base.metadata, sin importar app.main, unittest de stdlib.

Correr desde backend/:
    python -m unittest tests.test_public_surface -v
"""

import os
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-public-surface")
os.environ.setdefault("ALGORITHM", "HS256")

import asyncio

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app import models, database
from app.utils import auth as auth_utils
from app.routers import auth as auth_router
from app.routers import products as products_router
from app.routers import settings as settings_router

ADMIN = "admin@unpo.com.ar"
VENDEDOR = "vendedora@unpo.com.ar"
PASSWORD = "Secret*123"

SENSITIVE_PRODUCT_FIELDS = (
    "cost_price", "provider_name", "price_breakdown",
    "price_wholesale", "price_retail", "price_usd", "iva_percent",
)


class _ASGIClient:
    def __init__(self, app):
        self._app = app

    def _request(self, method, url, **kwargs):
        async def _do():
            transport = ASGITransport(app=self._app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                return await ac.request(method, url, **kwargs)
        return asyncio.run(_do())

    def get(self, url, **kwargs):
        return self._request("GET", url, **kwargs)


class PublicSurfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)
        cls.pw_hash = auth_utils.get_password_hash(PASSWORD)

        app = FastAPI()
        app.include_router(auth_router.router)
        app.include_router(products_router.router)
        app.include_router(settings_router.router)

        def _get_test_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[database.get_db] = _get_test_db

        cls.client = _ASGIClient(app)
        cls.tok_admin = auth_utils.create_access_token({"sub": ADMIN})
        cls.tok_vend = auth_utils.create_access_token({"sub": VENDEDOR})

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        db = self.Session()
        try:
            db.add_all([
                models.User(email=ADMIN, hashed_password=self.pw_hash, full_name="Admin", role="admin"),
                models.User(email=VENDEDOR, hashed_password=self.pw_hash, full_name="Vendedora", role="vendedor"),
                models.Product(
                    sku="TESTSKU", name="Producto Test", stock_quantity=5, is_active=True,
                    cost_price=100, price_wholesale=200, price_usd=1,
                    provider_name="Proveedor Secreto",
                ),
                models.Settings(key="manual_exchange_rate", value="1500"),
                models.Settings(key="clave_privada", value="interno"),
            ])
            db.commit()
        finally:
            db.close()

    def _h(self, token):
        return {"Authorization": f"Bearer {token}"}

    # ------------------------------- Products ---------------------------------
    def test_public_listing_hides_sensitive_fields(self):
        r = self.client.get("/products/")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(len(data), 1)
        for field in SENSITIVE_PRODUCT_FIELDS:
            self.assertNotIn(field, data[0], f"campo sensible expuesto: {field}")
        self.assertEqual(data[0]["sku"], "TESTSKU")
        self.assertEqual(data[0]["stock_quantity"], 5)

    def test_public_detail_hides_sensitive_fields(self):
        r = self.client.get("/products/TESTSKU")
        self.assertEqual(r.status_code, 200, r.text)
        for field in SENSITIVE_PRODUCT_FIELDS:
            self.assertNotIn(field, r.json(), f"campo sensible expuesto: {field}")

    def test_staff_listing_includes_full_fields(self):
        for token in (self.tok_admin, self.tok_vend):
            r = self.client.get("/products/", headers=self._h(token))
            self.assertEqual(r.status_code, 200, r.text)
            prod = r.json()[0]
            self.assertEqual(float(prod["cost_price"]), 100.0)
            self.assertEqual(prod["provider_name"], "Proveedor Secreto")

    def test_invalid_token_gets_public_view(self):
        r = self.client.get("/products/", headers=self._h("token-invalido"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("cost_price", r.json()[0])

    # ------------------------------- Settings ---------------------------------
    def test_setting_anonymous_401(self):
        r = self.client.get("/settings/manual_exchange_rate")
        self.assertEqual(r.status_code, 401)

    def test_exchange_rate_readable_by_staff(self):
        for token in (self.tok_admin, self.tok_vend):
            r = self.client.get("/settings/manual_exchange_rate", headers=self._h(token))
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json()["value"], "1500")

    def test_private_setting_seller_403(self):
        r = self.client.get("/settings/clave_privada", headers=self._h(self.tok_vend))
        self.assertEqual(r.status_code, 403)

    def test_private_setting_admin_ok(self):
        r = self.client.get("/settings/clave_privada", headers=self._h(self.tok_admin))
        self.assertEqual(r.status_code, 200, r.text)

    def test_capital_ivas_seller_403(self):
        r = self.client.get("/settings/capital_ivas/list", headers=self._h(self.tok_vend))
        self.assertEqual(r.status_code, 403)

    def test_capital_ivas_admin_ok(self):
        r = self.client.get("/settings/capital_ivas/list", headers=self._h(self.tok_admin))
        self.assertEqual(r.status_code, 200, r.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
