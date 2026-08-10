"""
Tests de las reglas de negocio incorporadas en 2026-08 (mejoras de ventas):

- Sin monto mínimo de compra (se eliminó el piso de $100.000); una orden vacía sigue
  siendo inválida (400).
- Vendedores pueden crear y editar productos y ajustar stock; archivar/borrar/batch
  siguen siendo solo-admin.
- Edición de cliente: un vendedor puede actualizar datos de contacto/facturación de
  SUS leads vía PATCH /leads/{id}; `seller` sigue vedado.
- Cotización: status NEGOTIATION editable por el vendedor dueño, y el listado de
  contactados (GET /leads/?status=CONTACTED) lo incluye.
- Reporte GET /analytics/lead-quality: solo admin; estructura y conteos básicos.

Mismo aislamiento que test_security_phase0a: SQLite en memoria, sin red.
Correr desde backend/:  python -m unittest tests.test_sales_features_2026_08 -v
"""

import os
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-sales-features")
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
from app.routers import leads as leads_router
from app.routers import sales as sales_router
from app.routers import products as products_router
from app.routers import analytics as analytics_router

ADMIN = "admin@unpo.com.ar"
VEND_A = "vendedora@unpo.com.ar"
VEND_B = "vendedorb@unpo.com.ar"
PASSWORD = "Secret*123"


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

    def post(self, url, **kwargs):
        return self._request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self._request("PUT", url, **kwargs)

    def patch(self, url, **kwargs):
        return self._request("PATCH", url, **kwargs)

    def delete(self, url, **kwargs):
        return self._request("DELETE", url, **kwargs)


class SalesFeatures2026Test(unittest.TestCase):
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
        app.include_router(leads_router.router)
        app.include_router(sales_router.router)
        app.include_router(products_router.router)
        app.include_router(analytics_router.router)

        def _get_test_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[database.get_db] = _get_test_db

        cls.client = _ASGIClient(app)
        cls.tok_admin = auth_utils.create_access_token({"sub": ADMIN})
        cls.tok_a = auth_utils.create_access_token({"sub": VEND_A})
        cls.tok_b = auth_utils.create_access_token({"sub": VEND_B})

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        db = self.Session()
        try:
            db.add_all([
                models.User(email=ADMIN, hashed_password=self.pw_hash, full_name="Admin", role="admin"),
                models.User(email=VEND_A, hashed_password=self.pw_hash, full_name="Vendedora", role="vendedor"),
                models.User(email=VEND_B, hashed_password=self.pw_hash, full_name="Vendedorb", role="vendedor"),
                models.Product(sku="TESTSKU", name="Producto Test", stock_quantity=100, price_usd=10, is_active=True),
                models.Lead(id=1, full_name="De A", email="a@x.com", phone="1",
                            status=models.LeadStatus.CONTACTED, seller=VEND_A, source="SELLER"),
                models.Lead(id=2, full_name="Cliente de A", email="c@x.com", phone="2",
                            status=models.LeadStatus.CLIENT, seller=VEND_A, source="SELLER",
                            locality="Córdoba"),
                models.Lead(id=3, full_name="De B", email="b@x.com", phone="3",
                            status=models.LeadStatus.CONTACTED, seller=VEND_B, source="SELLER"),
            ])
            db.commit()
        finally:
            db.close()

    def _h(self, token):
        return {"Authorization": f"Bearer {token}"}

    def _sale_body(self, lead_id, amount):
        return {
            "lead_id": lead_id,
            "total_amount": amount,
            "items": [{"product_sku": "TESTSKU", "quantity": 1, "unit_price": amount, "total_price": amount}],
        }

    # ------------------------- Sin monto mínimo de compra -------------------------
    def test_sale_below_old_minimum_succeeds(self):
        r = self.client.post("/sales/", json=self._sale_body(1, 50000), headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)

    def test_sale_tiny_amount_succeeds(self):
        r = self.client.post("/sales/", json=self._sale_body(1, 1000), headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)

    def test_sale_without_items_400(self):
        r = self.client.post("/sales/", json={"lead_id": 1, "total_amount": 1000, "items": []},
                             headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 400)

    # ------------------- Productos: permisos de vendedor ampliados -----------------
    def test_vendedor_creates_product(self):
        r = self.client.post("/products/", json={"sku": "NUEVO1", "name": "Nuevo Prod"},
                             headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)

    def test_vendedor_updates_product(self):
        r = self.client.put("/products/TESTSKU", json={"name": "Editado por vendedor"},
                            headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)

    def test_vendedor_adjusts_stock(self):
        r = self.client.patch("/products/TESTSKU/stock", json={"adjustment": 5},
                              headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)

    def test_vendedor_gets_next_sku(self):
        r = self.client.get("/products/next-sku", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)

    def test_vendedor_cannot_archive_product(self):
        r = self.client.delete("/products/TESTSKU", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    def test_vendedor_cannot_hard_delete_product(self):
        r = self.client.delete("/products/TESTSKU/hard", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    def test_vendedor_cannot_batch_update(self):
        r = self.client.post("/products/batch_update", json={"updates": []}, headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    # ----------------------------- Edición de cliente ------------------------------
    def test_vendedor_edits_own_client_contact_data(self):
        payload = {"full_name": "Nombre Editado", "phone": "555", "locality": "Rosario", "dni_cuit": "20-1-9"}
        r = self.client.patch("/leads/2", json=payload, headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["full_name"], "Nombre Editado")
        self.assertEqual(body["locality"], "Rosario")

    def test_vendedor_cannot_edit_foreign_client(self):
        r = self.client.patch("/leads/3", json={"full_name": "Hack"}, headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    def test_vendedor_still_cannot_touch_seller(self):
        r = self.client.patch("/leads/1", json={"seller": VEND_B}, headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    def test_admin_edits_any_client(self):
        r = self.client.patch("/leads/3", json={"email": "nuevo@x.com"}, headers=self._h(self.tok_admin))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["email"], "nuevo@x.com")

    # ------------------------ Cotización (NEGOTIATION) -----------------------------
    def test_vendedor_marks_own_lead_quoted(self):
        r = self.client.patch("/leads/1", json={"status": "NEGOTIATION"}, headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)

    def test_contacted_listing_includes_quoted(self):
        self.client.patch("/leads/1", json={"status": "NEGOTIATION"}, headers=self._h(self.tok_a))
        r = self.client.get("/leads/?status=CONTACTED", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)
        ids = [l["id"] for l in r.json()]
        self.assertIn(1, ids, "el lead cotizado debe seguir apareciendo en Contactados")

    # ------------------------- Reporte de calidad de leads -------------------------
    def test_lead_quality_seller_403(self):
        r = self.client.get("/analytics/lead-quality?year=2026&month=8", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    def test_lead_quality_admin_structure(self):
        from datetime import datetime
        now = datetime.now()
        r = self.client.get(f"/analytics/lead-quality?year={now.year}&month={now.month}",
                            headers=self._h(self.tok_admin))
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        for key in ("total_leads", "whatsapp_leads", "quality_distribution", "funnel", "top_cities"):
            self.assertIn(key, body)
        self.assertEqual(body["total_leads"], 3)
        dist = {d["key"]: d["count"] for d in body["quality_distribution"]}
        self.assertEqual(dist["cliente"], 1)
        self.assertEqual(dist["contactado"], 2)
        funnel = {f["stage"]: f["count"] for f in body["funnel"]}
        self.assertEqual(funnel["Leads Recibidos"], 3)
        self.assertEqual(funnel["Clientes"], 1)

    def test_lead_quality_counts_quoted_and_cities(self):
        # Cotizar el lead 1 y verificar distribución + ciudades
        self.client.patch("/leads/1", json={"status": "NEGOTIATION"}, headers=self._h(self.tok_a))
        from datetime import datetime
        now = datetime.now()
        r = self.client.get(f"/analytics/lead-quality?year={now.year}&month={now.month}",
                            headers=self._h(self.tok_admin))
        body = r.json()
        dist = {d["key"]: d["count"] for d in body["quality_distribution"]}
        self.assertEqual(dist["cotizado"], 1)
        # El cliente con locality Córdoba cuenta como cotizado+cliente en su ciudad
        cities = {c["city"]: c for c in body["top_cities"]}
        self.assertIn("Córdoba", cities)
        self.assertEqual(cities["Córdoba"]["clients"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
