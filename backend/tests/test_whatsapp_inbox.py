"""
Tests del inbox multiagente de WhatsApp — Etapa 1G (API autenticada).

Mismas convenciones que el resto de la suite del backend:
- `unittest` (stdlib), SQLite en memoria (StaticPool) con `PRAGMA foreign_keys=ON`,
  esquema desde `Base.metadata` (Alembic sigue siendo el único gestor del esquema PG).
- NO importa `app.main`: arma una FastAPI mínima con `routers/whatsapp_inbox` y
  sobrescribe `app.database.get_db` y `get_current_user` para inyectar la sesión y el
  usuario autenticado.

    python -m unittest tests.test_whatsapp_inbox -v
"""

import asyncio
import base64
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database, models
from app.database import Base
from app.routers import whatsapp_inbox
from app.routers.auth import get_current_user

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class _ASGIClient:
    """Cliente HTTP síncrono sobre httpx.ASGITransport (igual que la suite webhook)."""

    def __init__(self, app):
        self._app = app

    def _request(self, method, url, user=None, **kwargs):
        async def _do():
            transport = ASGITransport(app=self._app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
                return await ac.request(method, url, **kwargs)
        return asyncio.run(_do())

    def get(self, url, **kw):
        return self._request("GET", url, **kw)

    def post(self, url, **kw):
        return self._request("POST", url, **kw)

    def patch(self, url, **kw):
        return self._request("PATCH", url, **kw)


class InboxTestBase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _fk_on(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = self.Session()
        self._seed()

        self.app = FastAPI()
        self.app.include_router(whatsapp_inbox.router)
        self.app.dependency_overrides[database.get_db] = self._get_db
        self.client = _ASGIClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _get_db(self):
        try:
            yield self.db
        finally:
            pass

    def as_user(self, user):
        self.app.dependency_overrides[get_current_user] = lambda: user

    def _msg(self, conv, direction, body, minute, mtype="text"):
        m = models.WhatsAppMessage(
            conversation_id=conv.id, provider="meta", direction=direction,
            message_type=mtype, text_body=body,
            current_status="delivered" if direction == "inbound" else "sent",
            origin="cloud_api" if direction == "inbound" else "crm",
            created_at=T0 + timedelta(minutes=minute),
        )
        self.db.add(m)
        return m

    def _seed(self):
        db = self.db
        self.line1 = models.WhatsAppLine(
            provider="meta", phone_number_id="PNID1", waba_id="WABA1",
            display_number="+540000000001", label="Linea 1", is_active=True)
        self.line2 = models.WhatsAppLine(
            provider="meta", phone_number_id="PNID2", waba_id="WABA2",
            display_number="+540000000002", label="Linea 2", is_active=True)
        db.add_all([self.line1, self.line2])
        db.commit()

        self.admin = models.User(email="admin@test.local", hashed_password="x",
                                 full_name="Admin", role="admin")
        self.v1 = models.User(email="v1@test.local", hashed_password="x",
                              full_name="Vendedor Uno", role="vendedor")
        self.v2 = models.User(email="v2@test.local", hashed_password="x",
                              full_name="Vendedor Dos", role="vendedor")
        db.add_all([self.admin, self.v1, self.v2])
        db.commit()

        db.add_all([
            models.WhatsAppLineUserAccess(line_id=self.line1.id, user_id=self.v1.id,
                                          can_view=True, can_send=True),
            models.WhatsAppLineUserAccess(line_id=self.line2.id, user_id=self.v2.id,
                                          can_view=True, can_send=False),
        ])
        db.commit()

        self.c1 = models.WhatsAppContact(display_name="Cliente Uno")
        self.c2 = models.WhatsAppContact(display_name="Cliente Dos")
        self.c3 = models.WhatsAppContact(display_name="Cliente Tres")
        db.add_all([self.c1, self.c2, self.c3])
        db.commit()
        db.add_all([
            models.WhatsAppContactIdentifier(contact_id=self.c1.id, provider="meta",
                identifier_type="wa_id", identifier_value="5491111111111", is_primary=True),
            models.WhatsAppContactIdentifier(contact_id=self.c1.id, provider="meta",
                identifier_type="phone_e164", identifier_value="+5491111111111"),
            models.WhatsAppContactIdentifier(contact_id=self.c2.id, provider="meta",
                identifier_type="wa_id", identifier_value="5492222222222", is_primary=True),
            models.WhatsAppContactIdentifier(contact_id=self.c3.id, provider="meta",
                identifier_type="wa_id", identifier_value="5493333333333", is_primary=True),
        ])
        db.commit()

        self.conv1 = models.WhatsAppConversation(
            line_id=self.line1.id, contact_id=self.c1.id, assigned_user_id=self.v1.id,
            status="open", last_message_at=T0 + timedelta(minutes=30))
        self.conv2 = models.WhatsAppConversation(
            line_id=self.line1.id, contact_id=self.c2.id, assigned_user_id=None,
            status="open", last_message_at=T0 + timedelta(minutes=20))
        self.conv3 = models.WhatsAppConversation(
            line_id=self.line2.id, contact_id=self.c3.id, assigned_user_id=self.v2.id,
            status="open", last_message_at=T0 + timedelta(minutes=10))
        db.add_all([self.conv1, self.conv2, self.conv3])
        db.commit()

        self.m1 = self._msg(self.conv1, "inbound", "hola uno", 1)
        self.m2 = self._msg(self.conv1, "inbound", "hola dos", 2)
        self.m3 = self._msg(self.conv1, "outbound", "respuesta staff", 3)
        self.m4 = self._msg(self.conv2, "inbound", "consulta a", 1)
        self.m5 = self._msg(self.conv2, "inbound", "consulta b", 2)
        self.m6 = self._msg(self.conv3, "inbound", "hola tres", 1)
        db.commit()
        for m in (self.m1, self.m2, self.m3, self.m4, self.m5, self.m6):
            db.refresh(m)


# =============================================================================== #
# Autenticación
# =============================================================================== #
class AuthTest(InboxTestBase):
    def _client_real_auth(self):
        app = FastAPI()
        app.include_router(whatsapp_inbox.router)
        app.dependency_overrides[database.get_db] = self._get_db
        return _ASGIClient(app)

    def test_all_routes_without_token_401(self):
        client = self._client_real_auth()
        routes = [
            ("get", "/whatsapp/lines"),
            ("get", "/whatsapp/conversations"),
            ("get", f"/whatsapp/conversations/{self.conv1.id}"),
            ("get", f"/whatsapp/conversations/{self.conv1.id}/messages"),
            ("get", "/whatsapp/unread-counts"),
            ("post", f"/whatsapp/conversations/{self.conv1.id}/read"),
            ("get", f"/whatsapp/conversations/{self.conv1.id}/assignments"),
        ]
        for method, url in routes:
            resp = getattr(client, method)(url)
            self.assertEqual(resp.status_code, 401, f"{method} {url} => {resp.status_code}")

    def test_patch_assignment_without_token_401(self):
        client = self._client_real_auth()
        resp = client.patch(f"/whatsapp/conversations/{self.conv1.id}/assignment",
                            json={"assigned_user_id": self.v1.id})
        self.assertEqual(resp.status_code, 401)

    def test_invalid_token_rejected(self):
        client = self._client_real_auth()
        resp = client.get("/whatsapp/lines",
                          headers={"Authorization": "Bearer not-a-real-jwt"})
        self.assertEqual(resp.status_code, 401)


# =============================================================================== #
# Admin
# =============================================================================== #
class AdminTest(InboxTestBase):
    def test_admin_sees_all_lines(self):
        self.as_user(self.admin)
        resp = self.client.get("/whatsapp/lines")
        self.assertEqual(resp.status_code, 200)
        ids = {l["id"] for l in resp.json()}
        self.assertEqual(ids, {self.line1.id, self.line2.id})
        self.assertTrue(all(l["can_view"] and l["can_send"] for l in resp.json()))

    def test_admin_sees_unassigned_conversation(self):
        self.as_user(self.admin)
        resp = self.client.get("/whatsapp/conversations")
        self.assertEqual(resp.status_code, 200)
        ids = {c["conversation_id"] for c in resp.json()["items"]}
        self.assertEqual(ids, {self.conv1.id, self.conv2.id, self.conv3.id})
        detail = self.client.get(f"/whatsapp/conversations/{self.conv2.id}")
        self.assertEqual(detail.status_code, 200)

    def test_admin_reads_messages(self):
        self.as_user(self.admin)
        resp = self.client.get(f"/whatsapp/conversations/{self.conv1.id}/messages")
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["items"]
        self.assertEqual([m["id"] for m in items], [self.m1.id, self.m2.id, self.m3.id])

    def test_admin_marks_read(self):
        self.as_user(self.admin)
        resp = self.client.post(f"/whatsapp/conversations/{self.conv2.id}/read")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["unread_count"], 0)

    def test_admin_assigns_and_history(self):
        self.as_user(self.admin)
        resp = self.client.patch(
            f"/whatsapp/conversations/{self.conv2.id}/assignment",
            json={"assigned_user_id": self.v1.id, "reason": "carga inicial"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["changed"])
        self.assertEqual(body["assigned_user_id"], self.v1.id)
        self.assertEqual(body["assignment"]["from_user_id"], None)
        self.assertEqual(body["assignment"]["to_user_id"], self.v1.id)
        self.assertEqual(body["assignment"]["assigned_by_user_id"], self.admin.id)

        hist = self.client.get(f"/whatsapp/conversations/{self.conv2.id}/assignments")
        self.assertEqual(hist.status_code, 200)
        self.assertEqual(len(hist.json()["items"]), 1)

    def test_admin_reassign_records_from_and_to(self):
        self.as_user(self.admin)
        # conv1 ya está asignada a v1 -> reasignar a admin (admin tiene acceso implícito)
        resp = self.client.patch(
            f"/whatsapp/conversations/{self.conv1.id}/assignment",
            json={"assigned_user_id": self.admin.id})
        self.assertEqual(resp.status_code, 200)
        a = resp.json()["assignment"]
        self.assertEqual(a["from_user_id"], self.v1.id)
        self.assertEqual(a["to_user_id"], self.admin.id)


# =============================================================================== #
# Vendedor autorizado
# =============================================================================== #
class SellerAuthorizedTest(InboxTestBase):
    def test_seller_sees_only_authorized_lines(self):
        self.as_user(self.v1)
        resp = self.client.get("/whatsapp/lines")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual({l["id"] for l in resp.json()}, {self.line1.id})

    def test_seller_sees_assigned_and_line_conversations(self):
        self.as_user(self.v1)
        resp = self.client.get("/whatsapp/conversations")
        ids = {c["conversation_id"] for c in resp.json()["items"]}
        # conv1 (asignada) y conv2 (línea 1) sí; conv3 (línea 2) no
        self.assertEqual(ids, {self.conv1.id, self.conv2.id})

    def test_seller_cannot_view_other_line_conversation(self):
        self.as_user(self.v1)
        resp = self.client.get(f"/whatsapp/conversations/{self.conv3.id}")
        self.assertEqual(resp.status_code, 404)

    def test_seller_unread_isolated_from_admin(self):
        # admin marca conv1 como leída; el unread de v1 NO debe cambiar.
        self.as_user(self.admin)
        self.client.post(f"/whatsapp/conversations/{self.conv1.id}/read")
        self.as_user(self.v1)
        detail = self.client.get(f"/whatsapp/conversations/{self.conv1.id}")
        self.assertEqual(detail.json()["unread_count"], 2)


# =============================================================================== #
# Vendedor NO autorizado
# =============================================================================== #
class SellerUnauthorizedTest(InboxTestBase):
    def test_cannot_enumerate_other_conversation(self):
        self.as_user(self.v2)  # v2 solo tiene línea 2
        resp = self.client.get(f"/whatsapp/conversations/{self.conv1.id}")
        self.assertEqual(resp.status_code, 404)

    def test_cannot_read_messages(self):
        self.as_user(self.v2)
        resp = self.client.get(f"/whatsapp/conversations/{self.conv1.id}/messages")
        self.assertEqual(resp.status_code, 404)

    def test_cannot_mark_read(self):
        self.as_user(self.v2)
        resp = self.client.post(f"/whatsapp/conversations/{self.conv1.id}/read")
        self.assertEqual(resp.status_code, 404)

    def test_cannot_assign(self):
        self.as_user(self.v2)
        resp = self.client.patch(
            f"/whatsapp/conversations/{self.conv1.id}/assignment",
            json={"assigned_user_id": self.v2.id})
        self.assertEqual(resp.status_code, 403)

    def test_list_does_not_leak_other_lines(self):
        self.as_user(self.v2)
        resp = self.client.get("/whatsapp/conversations")
        ids = {c["conversation_id"] for c in resp.json()["items"]}
        self.assertEqual(ids, {self.conv3.id})


# =============================================================================== #
# Unread por usuario
# =============================================================================== #
class UnreadTest(InboxTestBase):
    def test_no_read_row_all_inbound_unread(self):
        self.as_user(self.v1)
        detail = self.client.get(f"/whatsapp/conversations/{self.conv1.id}")
        self.assertEqual(detail.json()["unread_count"], 2)  # m1, m2 (m3 outbound no cuenta)

    def test_partial_read(self):
        self.as_user(self.v1)
        resp = self.client.post(f"/whatsapp/conversations/{self.conv1.id}/read",
                               json={"last_read_message_id": self.m1.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["unread_count"], 1)  # queda m2

    def test_full_read(self):
        self.as_user(self.v1)
        resp = self.client.post(f"/whatsapp/conversations/{self.conv1.id}/read",
                               json={"last_read_message_id": self.m2.id})
        self.assertEqual(resp.json()["unread_count"], 0)

    def test_read_never_moves_backward(self):
        self.as_user(self.v1)
        self.client.post(f"/whatsapp/conversations/{self.conv1.id}/read",
                        json={"last_read_message_id": self.m2.id})
        resp = self.client.post(f"/whatsapp/conversations/{self.conv1.id}/read",
                               json={"last_read_message_id": self.m1.id})
        self.assertEqual(resp.json()["last_read_message_id"], self.m2.id)
        self.assertEqual(resp.json()["unread_count"], 0)

    def test_two_users_independent(self):
        # v1 lee todo conv1; admin sigue con 2 no leídos
        self.as_user(self.v1)
        self.client.post(f"/whatsapp/conversations/{self.conv1.id}/read")
        self.as_user(self.admin)
        detail = self.client.get(f"/whatsapp/conversations/{self.conv1.id}")
        self.assertEqual(detail.json()["unread_count"], 2)

    def test_outbound_does_not_count(self):
        # conv1 tiene 1 outbound; unread nunca lo incluye
        self.as_user(self.v1)
        detail = self.client.get(f"/whatsapp/conversations/{self.conv1.id}")
        self.assertEqual(detail.json()["unread_count"], 2)

    def test_unread_counts_endpoint(self):
        self.as_user(self.v1)
        resp = self.client.get("/whatsapp/unread-counts")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # v1 ve línea1: conv1(2) + conv2(2) = 4
        self.assertEqual(body["total_unread"], 4)
        line1 = [l for l in body["lines"] if l["line_id"] == self.line1.id][0]
        self.assertEqual(line1["unread_count"], 4)


# =============================================================================== #
# Idempotencia y paginación
# =============================================================================== #
class IdempotencyTest(InboxTestBase):
    def test_repeated_read_idempotent(self):
        self.as_user(self.v1)
        r1 = self.client.post(f"/whatsapp/conversations/{self.conv1.id}/read")
        r2 = self.client.post(f"/whatsapp/conversations/{self.conv1.id}/read")
        self.assertEqual(r1.json(), r2.json())
        self.assertEqual(r2.json()["unread_count"], 0)

    def test_assignment_same_user_no_duplicate_history(self):
        self.as_user(self.admin)
        # conv1 ya asignada a v1; reasignar a v1 no cambia ni agrega historial
        resp = self.client.patch(
            f"/whatsapp/conversations/{self.conv1.id}/assignment",
            json={"assigned_user_id": self.v1.id})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["changed"])
        hist = self.client.get(f"/whatsapp/conversations/{self.conv1.id}/assignments")
        self.assertEqual(len(hist.json()["items"]), 0)

    def test_pagination_stable_no_duplicates(self):
        self.as_user(self.admin)
        seen = []
        for offset in range(3):
            resp = self.client.get(
                f"/whatsapp/conversations/{self.conv1.id}/messages?limit=1&offset={offset}")
            self.assertEqual(resp.status_code, 200)
            items = resp.json()["items"]
            if items:
                seen.append(items[0]["id"])
        self.assertEqual(seen, [self.m1.id, self.m2.id, self.m3.id])
        self.assertEqual(len(set(seen)), len(seen))


# =============================================================================== #
# Asignaciones — validaciones
# =============================================================================== #
class AssignmentValidationTest(InboxTestBase):
    def test_target_without_line_access_rejected(self):
        self.as_user(self.admin)
        # v2 no tiene acceso a línea1 (conv2 es de línea1)
        resp = self.client.patch(
            f"/whatsapp/conversations/{self.conv2.id}/assignment",
            json={"assigned_user_id": self.v2.id})
        self.assertEqual(resp.status_code, 400)

    def test_nonexistent_target_rejected(self):
        self.as_user(self.admin)
        resp = self.client.patch(
            f"/whatsapp/conversations/{self.conv2.id}/assignment",
            json={"assigned_user_id": 999999})
        self.assertEqual(resp.status_code, 400)

    def test_transaction_atomic_no_partial_history(self):
        # target inválido -> ni se asigna ni se agrega historial
        self.as_user(self.admin)
        before = self.db.query(models.WhatsAppConversationAssignment).count()
        self.client.patch(f"/whatsapp/conversations/{self.conv2.id}/assignment",
                         json={"assigned_user_id": 999999})
        after = self.db.query(models.WhatsAppConversationAssignment).count()
        self.assertEqual(before, after)
        self.db.refresh(self.conv2)
        self.assertIsNone(self.conv2.assigned_user_id)

    def test_test_conversation_can_stay_unassigned(self):
        # conv2 sin asignar sigue accesible y sin asignación forzada
        self.as_user(self.admin)
        detail = self.client.get(f"/whatsapp/conversations/{self.conv2.id}")
        self.assertIsNone(detail.json()["assigned_user"])


# =============================================================================== #
# Seguridad
# =============================================================================== #
class SecurityTest(InboxTestBase):
    def test_no_raw_payload_or_internal_fields(self):
        self.as_user(self.admin)
        blobs = [
            self.client.get("/whatsapp/conversations").text,
            self.client.get(f"/whatsapp/conversations/{self.conv1.id}").text,
            self.client.get(f"/whatsapp/conversations/{self.conv1.id}/messages").text,
            self.client.get("/whatsapp/lines").text,
        ]
        for blob in blobs:
            for forbidden in ("raw_payload", "payload_hash", "event_key",
                              "phone_number_id", "waba_id", "hashed_password"):
                self.assertNotIn(forbidden, blob)

    def test_contact_phone_is_masked(self):
        self.as_user(self.admin)
        resp = self.client.get(f"/whatsapp/conversations/{self.conv1.id}")
        contact = resp.json()["contact"]
        # el teléfono va enmascarado; el valor completo no aparece
        self.assertNotIn("5491111111111", resp.text)
        self.assertTrue(contact["phone_masked"].startswith("***"))

    def test_pagination_limit_bounds(self):
        self.as_user(self.admin)
        self.assertEqual(self.client.get("/whatsapp/conversations?limit=0").status_code, 422)
        self.assertEqual(self.client.get("/whatsapp/conversations?limit=1000").status_code, 422)
        self.assertEqual(self.client.get("/whatsapp/conversations?offset=-1").status_code, 422)
        self.assertEqual(
            self.client.get(f"/whatsapp/conversations/{self.conv1.id}/messages?limit=1000")
            .status_code, 422)

    def test_search_injection_treated_as_literal(self):
        self.as_user(self.admin)
        resp = self.client.get(
            "/whatsapp/conversations",
            params={"search": "'; DROP TABLE whatsapp_conversations; --"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["items"], [])
        # la tabla sigue existiendo: una consulta normal sigue funcionando
        ok = self.client.get("/whatsapp/conversations")
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(len(ok.json()["items"]) >= 1)

    def test_search_finds_by_name_within_scope(self):
        self.as_user(self.v1)
        resp = self.client.get("/whatsapp/conversations", params={"search": "Cliente Uno"})
        ids = {c["conversation_id"] for c in resp.json()["items"]}
        self.assertEqual(ids, {self.conv1.id})

    def test_search_does_not_cross_authorization(self):
        # v1 busca "Cliente Tres" (contacto de conv3, línea2) -> no debe aparecer
        self.as_user(self.v1)
        resp = self.client.get("/whatsapp/conversations", params={"search": "Cliente Tres"})
        self.assertEqual(resp.json()["items"], [])


# =============================================================================== #
# Filtros del listado
# =============================================================================== #
class FilterTest(InboxTestBase):
    def test_filter_unassigned(self):
        self.as_user(self.admin)
        resp = self.client.get("/whatsapp/conversations", params={"unassigned": "true"})
        ids = {c["conversation_id"] for c in resp.json()["items"]}
        self.assertEqual(ids, {self.conv2.id})

    def test_filter_assigned_to_me(self):
        self.as_user(self.v1)
        resp = self.client.get("/whatsapp/conversations", params={"assigned_to_me": "true"})
        ids = {c["conversation_id"] for c in resp.json()["items"]}
        self.assertEqual(ids, {self.conv1.id})

    def test_filter_unread_only(self):
        self.as_user(self.admin)
        # admin marca conv1 leída; unread_only ya no la incluye
        self.client.post(f"/whatsapp/conversations/{self.conv1.id}/read")
        resp = self.client.get("/whatsapp/conversations", params={"unread_only": "true"})
        ids = {c["conversation_id"] for c in resp.json()["items"]}
        self.assertNotIn(self.conv1.id, ids)
        self.assertIn(self.conv2.id, ids)

    def test_filter_by_line(self):
        self.as_user(self.admin)
        resp = self.client.get("/whatsapp/conversations",
                              params={"line_id": self.line2.id})
        ids = {c["conversation_id"] for c in resp.json()["items"]}
        self.assertEqual(ids, {self.conv3.id})


# =============================================================================== #
# §2 — lead_id condicionado por la política de lectura de leads
# =============================================================================== #
class LeadIdAuthorizationTest(InboxTestBase):
    def setUp(self):
        super().setUp()
        self._n = 100
        db = self.db
        self.lead_v1 = models.Lead(full_name="Lead de V1", seller=self.v1.email,
                                   status=models.LeadStatus.CONTACTED)
        self.lead_v2 = models.Lead(full_name="Lead de V2", seller=self.v2.email,
                                   status=models.LeadStatus.CONTACTED)
        self.lead_new = models.Lead(full_name="Lead NEW", status=models.LeadStatus.NEW)
        db.add_all([self.lead_v1, self.lead_v2, self.lead_new])
        db.commit()

    def _conv_with_lead(self, line, assigned, lead):
        c = models.WhatsAppContact(display_name=f"LC{self._n}")
        self._n += 1
        self.db.add(c)
        self.db.commit()
        conv = models.WhatsAppConversation(
            line_id=line.id, contact_id=c.id,
            assigned_user_id=(assigned.id if assigned else None), status="open",
            lead_id=(lead.id if lead else None), last_message_at=T0)
        self.db.add(conv)
        self.db.commit()
        return conv

    def test_admin_sees_lead_id(self):
        conv = self._conv_with_lead(self.line1, self.v1, self.lead_v2)
        self.as_user(self.admin)
        r = self.client.get(f"/whatsapp/conversations/{conv.id}")
        self.assertEqual(r.json()["lead_id"], self.lead_v2.id)

    def test_owner_seller_sees_lead_id(self):
        conv = self._conv_with_lead(self.line1, None, self.lead_v1)
        self.as_user(self.v1)
        r = self.client.get(f"/whatsapp/conversations/{conv.id}")
        self.assertEqual(r.json()["lead_id"], self.lead_v1.id)

    def test_line_access_but_foreign_lead_null(self):
        conv = self._conv_with_lead(self.line1, None, self.lead_v2)
        self.as_user(self.v1)
        r = self.client.get(f"/whatsapp/conversations/{conv.id}")
        self.assertIsNone(r.json()["lead_id"])

    def test_assigned_but_foreign_lead_null(self):
        conv = self._conv_with_lead(self.line1, self.v1, self.lead_v2)
        self.as_user(self.v1)
        r = self.client.get(f"/whatsapp/conversations/{conv.id}")
        self.assertIsNone(r.json()["lead_id"])

    def test_no_lead_null(self):
        conv = self._conv_with_lead(self.line1, self.v1, None)
        self.as_user(self.v1)
        r = self.client.get(f"/whatsapp/conversations/{conv.id}")
        self.assertIsNone(r.json()["lead_id"])

    def test_new_lead_visible_to_seller(self):
        conv = self._conv_with_lead(self.line1, None, self.lead_new)
        self.as_user(self.v1)
        r = self.client.get(f"/whatsapp/conversations/{conv.id}")
        self.assertEqual(r.json()["lead_id"], self.lead_new.id)


# =============================================================================== #
# §7 — último mensaje por (created_at, id), no por max(id)
# =============================================================================== #
class LastMessageOrderingTest(InboxTestBase):
    def test_last_message_by_created_at_not_max_id(self):
        db = self.db
        c = models.WhatsAppContact(display_name="LMO")
        db.add(c)
        db.commit()
        # conversation.last_message_at CONTRADICTORIO a propósito (12:59): el ítem debe
        # derivar todos los campos del "último mensaje" del mensaje seleccionado (B, 12:10).
        conv = models.WhatsAppConversation(
            line_id=self.line1.id, contact_id=c.id, assigned_user_id=self.v1.id,
            status="open", last_message_at=T0 + timedelta(minutes=59))
        db.add(conv)
        db.commit()
        self._msg(conv, "inbound", "temprano", 5)                 # A: 12:05
        m_late = self._msg(conv, "outbound", "ultimo real", 10)   # B: 12:10 (el último real)
        db.commit()
        # C: id MAYOR pero created_at ANTERIOR (12:01): no debe ser el "último".
        m_higher_id = self._msg(conv, "inbound", "id mayor viejo", 1)
        db.commit()
        db.refresh(m_late)
        db.refresh(m_higher_id)
        self.assertGreater(m_higher_id.id, m_late.id)

        self.as_user(self.admin)
        r = self.client.get("/whatsapp/conversations")
        item = [x for x in r.json()["items"] if x["conversation_id"] == conv.id][0]
        self.assertEqual(item["last_message_preview"], "ultimo real")
        self.assertEqual(item["last_message_direction"], "outbound")
        self.assertEqual(item["last_message_type"], "text")
        # last_message_at debe reflejar B (12:10), NO conversation.last_message_at (12:59).
        parsed = datetime.fromisoformat(item["last_message_at"].replace("Z", "+00:00"))
        self.assertEqual((parsed.hour, parsed.minute), (12, 10))


# =============================================================================== #
# §8 — alcance efectivo de líneas por asignación
# =============================================================================== #
class AssignedOnlyLineScopeTest(InboxTestBase):
    def setUp(self):
        super().setUp()
        db = self.db
        self.v3 = models.User(email="v3@test.local", hashed_password="x",
                              full_name="Vend Tres", role="vendedor")
        db.add(self.v3)
        db.commit()
        # v3 SIN line_user_access, pero asignado a una conversación de line1.
        c = models.WhatsAppContact(display_name="C-v3")
        db.add(c)
        db.commit()
        self.conv_v3 = models.WhatsAppConversation(
            line_id=self.line1.id, contact_id=c.id, assigned_user_id=self.v3.id,
            status="open", last_message_at=T0 + timedelta(minutes=5))
        db.add(self.conv_v3)
        db.commit()
        self._msg(self.conv_v3, "inbound", "hola v3", 1)
        db.commit()

    def test_v3_sees_only_assigned_conversation(self):
        self.as_user(self.v3)
        r = self.client.get("/whatsapp/conversations")
        ids = {c["conversation_id"] for c in r.json()["items"]}
        self.assertEqual(ids, {self.conv_v3.id})

    def test_v3_line_in_lines_can_view_true_can_send_false(self):
        self.as_user(self.v3)
        r = self.client.get("/whatsapp/lines")
        lines = {l["id"]: l for l in r.json()}
        self.assertIn(self.line1.id, lines)
        self.assertTrue(lines[self.line1.id]["can_view"])
        self.assertFalse(lines[self.line1.id]["can_send"])

    def test_v3_unread_totals_match(self):
        self.as_user(self.v3)
        conv_unread = self.client.get(
            f"/whatsapp/conversations/{self.conv_v3.id}").json()["unread_count"]
        uc = self.client.get("/whatsapp/unread-counts").json()
        self.assertEqual(uc["total_unread"], conv_unread)
        line1 = [l for l in uc["lines"] if l["line_id"] == self.line1.id][0]
        self.assertEqual(line1["unread_count"], conv_unread)

    def test_v3_does_not_see_other_unassigned_on_that_line(self):
        # conv2 (line1, sin asignar) NO debe verse solo por tener conv_v3 asignada.
        self.as_user(self.v3)
        self.assertEqual(
            self.client.get(f"/whatsapp/conversations/{self.conv2.id}").status_code, 404)


# =============================================================================== #
# §6 — cursor pagination del historial
# =============================================================================== #
class CursorPaginationTest(InboxTestBase):
    def _conv_with_messages(self, minutes):
        db = self.db
        c = models.WhatsAppContact(display_name=f"CUR-{self._nonce()}")
        db.add(c)
        db.commit()
        conv = models.WhatsAppConversation(
            line_id=self.line1.id, contact_id=c.id, assigned_user_id=self.v1.id,
            status="open", last_message_at=T0)
        db.add(conv)
        db.commit()
        msgs = []
        for i, minute in enumerate(minutes):
            m = models.WhatsAppMessage(
                conversation_id=conv.id, provider="meta", direction="inbound",
                message_type="text", text_body=f"m{i}", current_status="delivered",
                origin="cloud_api", created_at=T0 + timedelta(minutes=minute))
            db.add(m)
            msgs.append(m)
        db.commit()
        for m in msgs:
            db.refresh(m)
        return conv, msgs

    _counter = 0

    def _nonce(self):
        CursorPaginationTest._counter += 1
        return CursorPaginationTest._counter

    def test_same_created_at_ordered_by_id(self):
        conv, msgs = self._conv_with_messages([5, 5])
        self.as_user(self.admin)
        r1 = self.client.get(f"/whatsapp/conversations/{conv.id}/messages?limit=1")
        self.assertEqual([m["id"] for m in r1.json()["items"]], [msgs[0].id])
        self.assertTrue(r1.json()["has_more"])
        cur = r1.json()["next_cursor"]
        r2 = self.client.get(
            f"/whatsapp/conversations/{conv.id}/messages?limit=1&cursor={cur}")
        self.assertEqual([m["id"] for m in r2.json()["items"]], [msgs[1].id])

    def test_page1_insert_page2_no_dup_no_skip(self):
        conv, msgs = self._conv_with_messages([1, 2, 3])
        self.as_user(self.admin)
        r1 = self.client.get(f"/whatsapp/conversations/{conv.id}/messages?limit=2")
        self.assertEqual([m["id"] for m in r1.json()["items"]], [msgs[0].id, msgs[1].id])
        cur = r1.json()["next_cursor"]
        newm = models.WhatsAppMessage(
            conversation_id=conv.id, provider="meta", direction="inbound",
            message_type="text", text_body="nuevo", current_status="delivered",
            origin="cloud_api", created_at=T0 + timedelta(minutes=4))
        self.db.add(newm)
        self.db.commit()
        self.db.refresh(newm)
        r2 = self.client.get(
            f"/whatsapp/conversations/{conv.id}/messages?limit=10&cursor={cur}")
        ids2 = [m["id"] for m in r2.json()["items"]]
        self.assertEqual(ids2, [msgs[2].id, newm.id])
        self.assertNotIn(msgs[0].id, ids2)
        self.assertNotIn(msgs[1].id, ids2)

    def test_invalid_cursor_422(self):
        conv, _ = self._conv_with_messages([1])
        self.as_user(self.admin)
        bad = base64.urlsafe_b64encode(b"sin-separador").decode("ascii")
        r = self.client.get(f"/whatsapp/conversations/{conv.id}/messages?cursor={bad}")
        self.assertEqual(r.status_code, 422)

    def test_cursor_from_other_conversation_stays_scoped(self):
        conv_a, _ = self._conv_with_messages([1, 2])
        conv_b, msgs_b = self._conv_with_messages([1, 2, 3])
        self.as_user(self.admin)
        cur_a = self.client.get(
            f"/whatsapp/conversations/{conv_a.id}/messages?limit=1").json()["next_cursor"]
        rb = self.client.get(
            f"/whatsapp/conversations/{conv_b.id}/messages?cursor={cur_a}")
        conv_ids = {m["conversation_id"] for m in rb.json()["items"]}
        self.assertEqual(conv_ids, {conv_b.id})
        b_ids = {m.id for m in msgs_b}
        for m in rb.json()["items"]:
            self.assertIn(m["id"], b_ids)


# =============================================================================== #
# §5 — redacción de errores en logs
# =============================================================================== #
class LogRedactionTest(InboxTestBase):
    def test_assignment_error_redacts_sensitive(self):
        self.as_user(self.admin)
        err = IntegrityError(
            "INSERT INTO whatsapp_conversation_assignments (reason) VALUES (?)",
            {"reason": "SECRET-MARKER-1G"},
            Exception("constraint"))
        with mock.patch.object(self.db, "commit", side_effect=err):
            with self.assertLogs("uvicorn.error", level="ERROR") as cm:
                r = self.client.patch(
                    f"/whatsapp/conversations/{self.conv2.id}/assignment",
                    json={"assigned_user_id": self.v1.id, "reason": "SECRET-MARKER-1G"})
        self.assertEqual(r.status_code, 500)
        logtext = "\n".join(cm.output)
        self.assertNotIn("SECRET-MARKER-1G", logtext)
        self.assertNotIn("[SQL:", logtext)
        self.assertNotIn("[parameters:", logtext)
        self.assertNotIn("Traceback", logtext)


# =============================================================================== #
# §3 (1H) — paginación bidireccional de mensajes (direction=forward|backward)
# =============================================================================== #
class BidirectionalPaginationTest(InboxTestBase):
    _n = 0

    def _mk(self, minutes):
        BidirectionalPaginationTest._n += 1
        c = models.WhatsAppContact(display_name=f"BP{BidirectionalPaginationTest._n}")
        self.db.add(c)
        self.db.commit()
        conv = models.WhatsAppConversation(
            line_id=self.line1.id, contact_id=c.id, assigned_user_id=self.v1.id,
            status="open", last_message_at=T0)
        self.db.add(conv)
        self.db.commit()
        msgs = []
        for i, mnt in enumerate(minutes):
            m = models.WhatsAppMessage(
                conversation_id=conv.id, provider="meta", direction="inbound",
                message_type="text", text_body=f"m{i}", current_status="delivered",
                origin="cloud_api", created_at=T0 + timedelta(minutes=mnt))
            self.db.add(m)
            msgs.append(m)
        self.db.commit()
        for m in msgs:
            self.db.refresh(m)
        return conv, msgs

    def _get(self, conv_id, **params):
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return self.client.get(f"/whatsapp/conversations/{conv_id}/messages?{qs}")

    def test_backward_no_cursor_returns_last_n(self):
        conv, m = self._mk(list(range(1, 11)))  # m0..m9
        self.as_user(self.admin)
        b = self._get(conv.id, direction="backward", limit=3).json()
        self.assertEqual([x["id"] for x in b["items"]], [m[7].id, m[8].id, m[9].id])  # ASC
        self.assertEqual(b["direction"], "backward")
        self.assertTrue(b["has_more"])            # existen más antiguos
        self.assertIsNotNone(b["older_cursor"])
        self.assertIsNotNone(b["newer_cursor"])

    def test_backward_with_cursor_loads_older(self):
        conv, m = self._mk(list(range(1, 11)))
        self.as_user(self.admin)
        p1 = self._get(conv.id, direction="backward", limit=3).json()
        p2 = self._get(conv.id, direction="backward", limit=3, cursor=p1["older_cursor"]).json()
        self.assertEqual([x["id"] for x in p2["items"]], [m[4].id, m[5].id, m[6].id])
        ids1 = {x["id"] for x in p1["items"]}
        ids2 = {x["id"] for x in p2["items"]}
        self.assertEqual(ids1 & ids2, set())      # sin solapamiento

    def test_forward_newer_cursor_gets_new(self):
        conv, m = self._mk([1, 2, 3, 4, 5])
        self.as_user(self.admin)
        last = self._get(conv.id, direction="backward", limit=5).json()
        newer = last["newer_cursor"]
        newm = models.WhatsAppMessage(
            conversation_id=conv.id, provider="meta", direction="inbound",
            message_type="text", text_body="nuevo", current_status="delivered",
            origin="cloud_api", created_at=T0 + timedelta(minutes=6))
        self.db.add(newm)
        self.db.commit()
        self.db.refresh(newm)
        f = self._get(conv.id, direction="forward", cursor=newer).json()
        self.assertEqual([x["id"] for x in f["items"]], [newm.id])

    def test_created_at_tie_broken_by_id_backward(self):
        conv, m = self._mk([5, 5])  # mismo created_at, ids distintos
        self.as_user(self.admin)
        p1 = self._get(conv.id, direction="backward", limit=1).json()
        self.assertEqual([x["id"] for x in p1["items"]], [m[1].id])  # id mayor primero
        p2 = self._get(conv.id, direction="backward", limit=1, cursor=p1["older_cursor"]).json()
        self.assertEqual([x["id"] for x in p2["items"]], [m[0].id])

    def test_no_duplicates_paging_backward(self):
        conv, m = self._mk(list(range(1, 8)))  # 7 mensajes
        self.as_user(self.admin)
        seen = []
        cursor = None
        for _ in range(10):
            params = {"direction": "backward", "limit": 2}
            if cursor:
                params["cursor"] = cursor
            pg = self._get(conv.id, **params).json()
            seen = [x["id"] for x in pg["items"]] + seen  # prepend (páginas más antiguas)
            if not pg["has_more"]:
                break
            cursor = pg["older_cursor"]
        self.assertEqual(seen, [x.id for x in m])          # cobertura completa, en orden
        self.assertEqual(len(seen), len(set(seen)))        # sin duplicados

    def test_invalid_cursor_422_backward(self):
        conv, _ = self._mk([1])
        self.as_user(self.admin)
        bad = base64.urlsafe_b64encode(b"sin-separador").decode("ascii")
        self.assertEqual(
            self._get(conv.id, direction="backward", cursor=bad).status_code, 422)

    def test_unauthorized_conversation_404_backward(self):
        conv, _ = self._mk([1, 2])
        self.as_user(self.v2)  # v2 no tiene acceso a line1
        self.assertEqual(self._get(conv.id, direction="backward").status_code, 404)

    def test_response_without_direction_still_forward(self):
        conv, m = self._mk([1, 2, 3, 4, 5])
        self.as_user(self.admin)
        r = self._get(conv.id, limit=2).json()             # sin direction
        self.assertEqual(r["direction"], "forward")
        self.assertEqual([x["id"] for x in r["items"]], [m[0].id, m[1].id])  # primeros, ASC
        self.assertTrue(r["has_more"])

    def test_invalid_direction_422(self):
        conv, _ = self._mk([1])
        self.as_user(self.admin)
        self.assertEqual(self._get(conv.id, direction="sideways").status_code, 422)


# =============================================================================== #
# §5 (1H.1) — GET /whatsapp/assignable-users + validación de rol destino
# =============================================================================== #
class AssignableUsersTest(InboxTestBase):
    def setUp(self):
        super().setUp()
        self.other = models.User(
            email="otro@test.local", hashed_password="x", full_name="Otro Rol",
            role="supervisor")
        self.db.add(self.other)
        self.db.commit()

    def test_admin_gets_assignable_users(self):
        self.as_user(self.admin)
        r = self.client.get("/whatsapp/assignable-users")
        self.assertEqual(r.status_code, 200)
        roles = {u["role"] for u in r.json()}
        self.assertTrue(roles <= {"admin", "vendedor"})
        ids = {u["id"] for u in r.json()}
        self.assertIn(self.admin.id, ids)
        self.assertIn(self.v1.id, ids)
        self.assertIn(self.v2.id, ids)
        # Un rol no asignable NO aparece.
        self.assertNotIn(self.other.id, ids)

    def test_seller_forbidden(self):
        self.as_user(self.v1)
        self.assertEqual(self.client.get("/whatsapp/assignable-users").status_code, 403)

    def test_no_email_in_response(self):
        self.as_user(self.admin)
        blob = self.client.get("/whatsapp/assignable-users").text
        self.assertNotIn("@test.local", blob)
        self.assertNotIn("email", blob)
        self.assertNotIn("hashed_password", blob)

    def test_assign_invalid_role_rejected(self):
        self.as_user(self.admin)
        r = self.client.patch(
            f"/whatsapp/conversations/{self.conv2.id}/assignment",
            json={"assigned_user_id": self.other.id})
        self.assertEqual(r.status_code, 400)

    def test_assign_valid_still_works(self):
        self.as_user(self.admin)
        r = self.client.patch(
            f"/whatsapp/conversations/{self.conv2.id}/assignment",
            json={"assigned_user_id": self.v1.id})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["changed"])


if __name__ == "__main__":
    unittest.main()
