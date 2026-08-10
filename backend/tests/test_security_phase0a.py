"""
Tests de seguridad — Etapa 0A (hardening de auth/authorization/ownership).

Aislado y sin tocar ninguna base real:
- Usa SQLite en memoria (StaticPool) y crea el esquema desde `Base.metadata`.
- NO importa `app.main` (evita `Base.metadata.create_all` contra el Postgres real).
- Construye una FastAPI mínima incluyendo solo los routers bajo prueba y sobrescribe
  las dependencias `get_db` (de `app.database` y del módulo `app.routers.auth`) para
  apuntar a la sesión SQLite de test.
- Autentica con JWT reales generados con `create_access_token` (mismo SECRET_KEY que
  usa `get_current_user`, fijado por env antes de importar).

Framework: `unittest` (stdlib) para poder correr con `python -m unittest` sin instalar
dependencias nuevas (pytest no está en requirements). Los TestCase también son
recolectables por pytest a futuro.

Correr desde backend/ (dentro del contenedor):
    python -m unittest tests.test_security_phase0a -v
"""

import os
import unittest

# Fijar secretos ANTES de importar la app, para que create_access_token (utils.auth) y
# get_current_user (routers.auth) usen la misma clave y los tokens validen.
os.environ.setdefault("SECRET_KEY", "test-secret-phase0a")
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
from app.routers import finance as finance_router
from app.routers import products as products_router
from app.dependencies.permissions import require_roles

ADMIN = "admin@unpo.com.ar"
VEND_A = "vendedora@unpo.com.ar"
VEND_B = "vendedorb@unpo.com.ar"
PASSWORD = "Secret*123"


class _ASGIClient:
    """
    Cliente HTTP síncrono mínimo sobre httpx.ASGITransport.

    Sustituye a starlette.TestClient porque la versión de httpx del entorno (>=0.28)
    quitó el atajo `app=` que el TestClient de starlette 0.36 todavía usa. Mantiene la
    misma interfaz sync (get/post/put/patch/delete) que consumen los tests.
    """

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


class SecurityPhase0ATest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

        # Hash de password una sola vez (bcrypt es lento); se reusa al sembrar.
        cls.pw_hash = auth_utils.get_password_hash(PASSWORD)

        app = FastAPI()
        app.include_router(auth_router.router)
        app.include_router(leads_router.router)
        app.include_router(sales_router.router)
        app.include_router(finance_router.router)
        app.include_router(products_router.router)

        def _get_test_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        # Los routers usan database.get_db; auth.py define su propio get_db local.
        app.dependency_overrides[database.get_db] = _get_test_db
        app.dependency_overrides[auth_router.get_db] = _get_test_db

        cls.app = app
        cls.client = _ASGIClient(app)

        cls.tok_admin = auth_utils.create_access_token({"sub": ADMIN})
        cls.tok_a = auth_utils.create_access_token({"sub": VEND_A})
        cls.tok_b = auth_utils.create_access_token({"sub": VEND_B})

    def setUp(self):
        # DB fresca por test → aislamiento total.
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        db = self.Session()
        try:
            db.add_all([
                models.User(email=ADMIN, hashed_password=self.pw_hash, full_name="Admin", role="admin"),
                models.User(email=VEND_A, hashed_password=self.pw_hash, full_name="Vendedora", role="vendedor"),
                models.User(email=VEND_B, hashed_password=self.pw_hash, full_name="Vendedorb", role="vendedor"),
                models.Product(sku="TESTSKU", name="Producto Test", stock_quantity=100, price_usd=10, is_active=True),
                # Lead 1: NEW sin vendedor (global). Lead 2: de A. Lead 3: de B.
                models.Lead(id=1, full_name="Nuevo", email="n@x.com", phone="1", status=models.LeadStatus.NEW, source="SELLER"),
                models.Lead(id=2, full_name="De A", email="a@x.com", phone="2", status=models.LeadStatus.CONTACTED, seller=VEND_A, source="SELLER"),
                models.Lead(id=3, full_name="De B", email="b@x.com", phone="3", status=models.LeadStatus.CONTACTED, seller=VEND_B, source="SELLER"),
            ])
            db.commit()

            order_a = models.SaleOrder(lead_id=2, total_amount=100000, status=models.SaleOrderStatus.COMPLETED)
            order_b = models.SaleOrder(lead_id=3, total_amount=100000, status=models.SaleOrderStatus.COMPLETED)
            db.add_all([order_a, order_b])
            db.commit()
            db.add_all([
                models.OrderItem(order_id=order_a.id, product_sku="TESTSKU", quantity=1, unit_price=100000, total_price=100000),
                models.OrderItem(order_id=order_b.id, product_sku="TESTSKU", quantity=1, unit_price=100000, total_price=100000),
            ])
            db.commit()
            self.order_a_id = order_a.id
            self.order_b_id = order_b.id
        finally:
            db.close()

    # --- helpers ---
    def _h(self, token):
        return {"Authorization": f"Bearer {token}"}

    def _sale_body(self, lead_id):
        return {
            "lead_id": lead_id,
            "total_amount": 100000,
            "items": [{"product_sku": "TESTSKU", "quantity": 1, "unit_price": 100000, "total_price": 100000}],
        }

    # ======================= require_roles: guardas de config =======================
    def test_require_roles_rejects_phantom_roles(self):
        with self.assertRaises(ValueError):
            require_roles("seller")
        with self.assertRaises(ValueError):
            require_roles("vendor")
        with self.assertRaises(ValueError):
            require_roles("admin", "seller")

    # ============================ Autenticación de ventas ===========================
    def test_sales_anonymous_create_401(self):
        r = self.client.post("/sales/", json=self._sale_body(2))
        self.assertEqual(r.status_code, 401)

    def test_sales_anonymous_cancel_401(self):
        r = self.client.post(f"/sales/{self.order_a_id}/cancel")
        self.assertEqual(r.status_code, 401)

    def test_sales_anonymous_pdf_401(self):
        r = self.client.get(f"/sales/{self.order_a_id}/pdf")
        self.assertEqual(r.status_code, 401)

    def test_sales_anonymous_by_lead_401(self):
        r = self.client.get("/sales/lead/2")
        self.assertEqual(r.status_code, 401)

    # ============================== Ownership de ventas =============================
    def test_admin_creates_sale_any_lead(self):
        r = self.client.post("/sales/", json=self._sale_body(3), headers=self._h(self.tok_admin))
        self.assertEqual(r.status_code, 200, r.text)

    def test_seller_creates_sale_own_lead(self):
        r = self.client.post("/sales/", json=self._sale_body(2), headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)

    def test_seller_creates_sale_foreign_lead_403(self):
        r = self.client.post("/sales/", json=self._sale_body(3), headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    def test_seller_creates_sale_untaken_new_lead_403(self):
        r = self.client.post("/sales/", json=self._sale_body(1), headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    def test_seller_reads_own_sales(self):
        r = self.client.get("/sales/lead/2", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)

    def test_seller_reads_foreign_sales_404(self):
        r = self.client.get("/sales/lead/3", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 404)

    def test_seller_downloads_own_remito(self):
        r = self.client.get(f"/sales/{self.order_a_id}/pdf", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.headers.get("content-type"), "application/pdf")

    def test_seller_downloads_foreign_remito_404(self):
        r = self.client.get(f"/sales/{self.order_b_id}/pdf", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 404)

    def test_seller_cancels_own_sale(self):
        r = self.client.post(f"/sales/{self.order_a_id}/cancel", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)

    def test_seller_cancels_foreign_sale_404(self):
        r = self.client.post(f"/sales/{self.order_b_id}/cancel", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 404)

    # ============================== Ownership de leads ==============================
    def test_seller_updates_own_lead(self):
        r = self.client.patch("/leads/2", json={"notes": "seguimiento"}, headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)

    def test_seller_updates_foreign_lead_403(self):
        r = self.client.patch("/leads/3", json={"notes": "hack"}, headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    def test_seller_cannot_reassign_seller_403(self):
        r = self.client.patch("/leads/2", json={"seller": VEND_A}, headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    def test_seller_cannot_null_seller_403(self):
        r = self.client.patch("/leads/2", json={"seller": None}, headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    def test_admin_can_reassign_seller(self):
        r = self.client.patch("/leads/2", json={"seller": VEND_B}, headers=self._h(self.tok_admin))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json().get("seller"), VEND_B)

    # ================================ Toma de lead =================================
    def test_seller_takes_free_new_lead(self):
        r = self.client.put("/leads/1/mark-contacted", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 200, r.text)

    def test_second_seller_cannot_take_claimed_lead(self):
        r1 = self.client.put("/leads/1/mark-contacted", headers=self._h(self.tok_a))
        self.assertEqual(r1.status_code, 200, r1.text)
        r2 = self.client.put("/leads/1/mark-contacted", headers=self._h(self.tok_b))
        self.assertIn(r2.status_code, (403, 409))

    def test_mark_contacted_is_idempotent_for_owner(self):
        r1 = self.client.put("/leads/1/mark-contacted", headers=self._h(self.tok_a))
        self.assertEqual(r1.status_code, 200, r1.text)
        r2 = self.client.put("/leads/1/mark-contacted", headers=self._h(self.tok_a))
        self.assertEqual(r2.status_code, 200, r2.text)

    def test_seller_cannot_claim_foreign_lead(self):
        # Lead 2 pertenece a A; B no puede reclamarlo.
        r = self.client.put("/leads/2/mark-contacted", headers=self._h(self.tok_b))
        self.assertIn(r.status_code, (403, 409))

    # ================================== Finanzas ===================================
    def test_finance_read_anonymous_401(self):
        r = self.client.get("/finance/suppliers")
        self.assertEqual(r.status_code, 401)

    def test_finance_read_seller_403(self):
        r = self.client.get("/finance/suppliers", headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    def test_finance_read_admin_ok(self):
        r = self.client.get("/finance/suppliers", headers=self._h(self.tok_admin))
        self.assertEqual(r.status_code, 200, r.text)

    def test_finance_write_anonymous_401(self):
        r = self.client.post("/finance/suppliers", json={"nombre": "Prov"})
        self.assertEqual(r.status_code, 401)

    def test_finance_write_seller_403(self):
        r = self.client.post("/finance/suppliers", json={"nombre": "Prov"}, headers=self._h(self.tok_a))
        self.assertEqual(r.status_code, 403)

    def test_finance_write_admin_ok(self):
        r = self.client.post("/finance/suppliers", json={"nombre": "Prov"}, headers=self._h(self.tok_admin))
        self.assertEqual(r.status_code, 200, r.text)

    # ============================ Backdoors eliminados =============================
    def test_backdoor_reset_nico_404(self):
        self.assertEqual(self.client.get("/auth/reset-nico").status_code, 404)

    def test_backdoor_fix_roles_404(self):
        self.assertEqual(self.client.get("/auth/fix-roles").status_code, 404)

    def test_backdoor_setup_admin_404(self):
        self.assertEqual(self.client.get("/auth/setup-admin").status_code, 404)

    # ================= Endpoints de mantenimiento/debug eliminados =================
    # fix-images / fix-valija ahora caen en GET /{sku} y devuelven 404 (producto inexistente);
    # las rutas debug_* ya no están registradas.
    def test_products_fix_images_removed(self):
        self.assertEqual(self.client.get("/products/fix-images", headers=self._h(self.tok_admin)).status_code, 404)

    def test_products_fix_valija_removed(self):
        self.assertEqual(self.client.get("/products/fix-valija", headers=self._h(self.tok_admin)).status_code, 404)

    def test_products_debug_post_removed(self):
        r = self.client.post("/products/debug_post", json={"name": "X"}, headers=self._h(self.tok_admin))
        self.assertIn(r.status_code, (404, 405))

    def test_products_debug_put_removed(self):
        r = self.client.put("/products/debug/TESTSKU", json={"name": "X"}, headers=self._h(self.tok_admin))
        self.assertIn(r.status_code, (404, 405))

    # ================================= Regresión ==================================
    def test_login_ok(self):
        r = self.client.post("/auth/login", data={"username": ADMIN, "password": PASSWORD})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("access_token", r.json())

    def test_me_ok(self):
        r = self.client.get("/auth/me", headers=self._h(self.tok_admin))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json().get("email"), ADMIN)

    def test_list_leads_authenticated_ok(self):
        r = self.client.get("/leads/", headers=self._h(self.tok_admin))
        self.assertEqual(r.status_code, 200, r.text)

    def test_public_lead_creation_unpo(self):
        r = self.client.post("/leads/", json={"full_name": "Pub UNPO", "email": "pubu@x.com", "phone": "9", "source": "WEB_UNPO"})
        self.assertEqual(r.status_code, 200, r.text)

    def test_public_lead_creation_nora(self):
        r = self.client.post("/leads/", json={"full_name": "Pub NORA", "email": "pubn@x.com", "phone": "8", "source": "WEB_NORA"})
        self.assertEqual(r.status_code, 200, r.text)
        # El vendedor NORA no debe cambiar (regresión de la restricción de no tocar NORA).
        self.assertEqual(r.json().get("assigned_seller_phone"), "1131488378")

    def test_public_product_listing_ok(self):
        r = self.client.get("/products/")
        self.assertEqual(r.status_code, 200, r.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
