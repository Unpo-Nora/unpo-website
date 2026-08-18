"""
Tests del mapeo de leads de Meta Lead Ads y de la asignación de vendedor web (2026-08).

Contexto: diagnóstico 2026-08-18 — el 100 % de los leads de Instagram/Facebook llegaba
sin teléfono porque el formulario de la agencia pide el teléfono como pregunta
PERSONALIZADA (nombre generado por Meta a partir del texto) y el transformador solo
reconocía los nombres estándar `phone_number`/`phone`. Además, el formulario web UNPO
rotaba entre dos vendedores y la decisión de negocio es que TODO vaya a uno solo.

Sin red y sin DB real (SQLite en memoria para la parte de crud). Datos 100 % ficticios.
Correr desde backend/:  python -m unittest tests.test_meta_lead_mapping -v
"""

import os
import unittest
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import crud, models, schemas
from app.database import Base
from app.meta_api import transform_meta_lead_to_schemas


def _lead(fields, platform="ig", **extra):
    data = {
        "id": "LEADGEN_TEST_1",
        "created_time": "2026-08-18T12:00:00+0000",
        "platform": platform,
        "field_data": [{"name": n, "values": [v]} for (n, v) in fields],
    }
    data.update(extra)
    return data


FAKE_PHONE = "+5490000000000"


class MetaPhoneMappingTest(unittest.TestCase):
    """El teléfono debe reconocerse por nombre estándar Y por pregunta personalizada."""

    def test_standard_phone_number_field(self):
        out = transform_meta_lead_to_schemas(_lead([("full_name", "Test"), ("phone_number", FAKE_PHONE)]))
        self.assertEqual(out["phone"], FAKE_PHONE)

    def test_standard_phone_field(self):
        out = transform_meta_lead_to_schemas(_lead([("phone", FAKE_PHONE)]))
        self.assertEqual(out["phone"], FAKE_PHONE)

    def test_custom_question_whatsapp_with_accents_and_marks(self):
        # Nombre generado por Meta para una pregunta personalizada (el caso real).
        out = transform_meta_lead_to_schemas(_lead([("¿cuál_es_tu_número_de_whatsapp?", FAKE_PHONE)]))
        self.assertEqual(out["phone"], FAKE_PHONE)

    def test_custom_question_telefono(self):
        for name in ("teléfono", "telefono_de_contacto", "¿tu_teléfono?", "celular", "número_de_celular"):
            with self.subTest(name=name):
                out = transform_meta_lead_to_schemas(_lead([(name, FAKE_PHONE)]))
                self.assertEqual(out["phone"], FAKE_PHONE)

    def test_first_phone_wins_when_two_contact_questions(self):
        out = transform_meta_lead_to_schemas(_lead([("phone_number", FAKE_PHONE), ("whatsapp", "+5491111111111")]))
        self.assertEqual(out["phone"], FAKE_PHONE)

    def test_phone_is_stripped_and_empty_becomes_none(self):
        out = transform_meta_lead_to_schemas(_lead([("phone_number", f"  {FAKE_PHONE}  ")]))
        self.assertEqual(out["phone"], FAKE_PHONE)
        out2 = transform_meta_lead_to_schemas(_lead([("phone_number", "   ")]))
        self.assertIsNone(out2["phone"])

    def test_no_phone_field_leaves_none_and_logs_names_only(self):
        with self.assertLogs("uvicorn.error", level="WARNING") as captured:
            out = transform_meta_lead_to_schemas(_lead([("full_name", "Persona Test"), ("email", "t@example.com")]))
        self.assertIsNone(out["phone"])
        joined = "\n".join(captured.output)
        self.assertIn("sin teléfono", joined)
        # Solo nombres de campo, jamás valores (datos personales).
        self.assertNotIn("Persona Test", joined)
        self.assertNotIn("t@example.com", joined)

    def test_unrecognized_fields_logged_by_name_only(self):
        with self.assertLogs("uvicorn.error", level="WARNING") as captured:
            transform_meta_lead_to_schemas(_lead([("pregunta_rara", "valor secreto"), ("phone_number", FAKE_PHONE)]))
        joined = "\n".join(captured.output)
        self.assertIn("pregunta_rara", joined)
        self.assertNotIn("valor secreto", joined)


class MetaOtherFieldsTest(unittest.TestCase):
    """El resto del mapeo histórico se conserva intacto."""

    def test_custom_business_questions_still_map(self):
        out = transform_meta_lead_to_schemas(_lead([
            ("¿qué_tipo_de_negocio_tenés?", "Bazar"),
            ("selecciona_tu_volumen_de_compra", "Alto"),
            ("¿por_cuál_categoría_estár_más_interesado?", "Juguetes"),
            ("¿hace_cuántos_años_estás_en_el_mercado?", "5"),
            ("¿en_qué_producto_estabas_interesado/a?", "Aceitero"),
        ]))
        self.assertEqual(out["business_type"], "Bazar")
        self.assertEqual(out["purchase_volume"], "Alto")
        self.assertEqual(out["category_interest"], "Juguetes")
        self.assertEqual(out["experience_level"], "5")
        self.assertEqual(out["product_interest"], "Aceitero")

    def test_first_and_last_name_concatenate(self):
        out = transform_meta_lead_to_schemas(_lead([("first_name", "Ana"), ("last_name", "Test")]))
        self.assertEqual(out["full_name"], "Ana Test")

    def test_full_name_and_email(self):
        out = transform_meta_lead_to_schemas(_lead([("full_name", "Ana Test"), ("email", "a@example.com")]))
        self.assertEqual(out["full_name"], "Ana Test")
        self.assertEqual(out["email"], "a@example.com")

    def test_platform_and_source(self):
        self.assertEqual(transform_meta_lead_to_schemas(_lead([], platform="fb"))["source"], "FACEBOOK_ADS")
        self.assertEqual(transform_meta_lead_to_schemas(_lead([], platform="ig"))["source"], "INSTAGRAM_ADS")
        self.assertEqual(transform_meta_lead_to_schemas(_lead([], platform="fb"), brand="nora")["source"], "FACEBOOK_NORA")

    def test_campaign_tracking(self):
        out = transform_meta_lead_to_schemas(_lead([], campaign_name="Camp", ad_name="Ad"))
        self.assertEqual(out["campaign"], "Camp")
        self.assertEqual(out["ad_name"], "Ad")

    def test_defaults_when_empty(self):
        out = transform_meta_lead_to_schemas(_lead([]))
        self.assertEqual(out["full_name"], "Unknown")
        self.assertEqual(out["email"], "unknown@example.com")
        self.assertIsNone(out["phone"])


class WebLeadSellerAssignmentTest(unittest.TestCase):
    """Todos los leads WEB_UNPO van al mismo vendedor (sin rotación); NORA intacto."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def _create(self, source, i):
        return crud.create_lead(self.db, schemas.LeadCreate(
            full_name=f"Lead {i}", email=f"lead{i}@example.com", phone=f"+54900000000{i}", source=source,
        ))

    def test_all_web_unpo_leads_go_to_single_seller(self):
        phones = {self._create("WEB_UNPO", i).assigned_seller_phone for i in range(6)}
        self.assertEqual(phones, {crud.WEB_UNPO_SELLER_PHONE})

    def test_web_unpo_default_seller_is_martin(self):
        # Sin override de entorno, el default es el número de Martín Trojavcich.
        self.assertEqual(crud.WEB_UNPO_SELLER_PHONE, "1144227969")

    def test_nora_assignment_untouched(self):
        for src in ("WEB_NORA", "FACEBOOK_NORA", "INSTAGRAM_NORA"):
            with self.subTest(src=src):
                self.assertEqual(self._create(src, 1).assigned_seller_phone, crud.NORA_SELLER_PHONE)

    def test_meta_unpo_leads_get_no_seller_phone(self):
        # Los leads de Meta UNPO no llevan assigned_seller_phone (los contacta el CRM).
        self.assertIsNone(self._create("INSTAGRAM_ADS", 1).assigned_seller_phone)


if __name__ == "__main__":
    unittest.main(verbosity=2)
