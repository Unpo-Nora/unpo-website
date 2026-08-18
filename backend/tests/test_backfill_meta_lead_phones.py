"""
Tests del backfill de teléfonos históricos de Meta (scripts/maintenance/backfill_meta_lead_phones).

Sin red: se simula el índice de Meta. SQLite en memoria. Datos ficticios.
Correr desde backend/:  python -m unittest tests.test_backfill_meta_lead_phones -v
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from scripts.maintenance import backfill_meta_lead_phones as bf

T0 = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


class BuildIndexTest(unittest.TestCase):
    def test_index_uses_transformer_and_skips_without_phone_or_email(self):
        raw = [
            {"id": "1", "created_time": "2026-08-10T12:00:00+0000", "platform": "ig",
             "field_data": [{"name": "email", "values": ["A@Example.com "]},
                            {"name": "¿cuál_es_tu_whatsapp?", "values": ["+5490000000001"]}]},
            {"id": "2", "created_time": "2026-08-10T12:00:00+0000", "platform": "ig",
             "field_data": [{"name": "email", "values": ["b@example.com"]}]},   # sin teléfono
            {"id": "3", "created_time": "2026-08-10T12:00:00+0000", "platform": "ig",
             "field_data": [{"name": "phone_number", "values": ["+5490000000003"]}]},  # sin email
        ]
        index = bf.build_meta_index(raw)
        self.assertEqual(list(index.keys()), ["a@example.com"])
        self.assertEqual(index["a@example.com"][0][1], "+5490000000001")


class PickPhoneTest(unittest.TestCase):
    def test_single_candidate(self):
        self.assertEqual(bf._pick_phone([(T0, "+1")], None), "+1")

    def test_closest_by_date(self):
        cands = [(T0, "+old"), (T0 + timedelta(days=20), "+new")]
        self.assertEqual(bf._pick_phone(cands, T0 + timedelta(days=19)), "+new")

    def test_ambiguous_when_all_far(self):
        cands = [(T0, "+a"), (T0 + timedelta(days=30), "+b")]
        self.assertIsNone(bf._pick_phone(cands, T0 + timedelta(days=15)))

    def test_naive_lead_date_supported(self):
        cands = [(T0, "+a"), (T0 + timedelta(days=30), "+b")]
        self.assertEqual(bf._pick_phone(cands, T0.replace(tzinfo=None) + timedelta(hours=1)), "+a")


class RunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        db = self.Session()
        db.add_all([
            models.Lead(full_name="A", email="a@example.com", phone=None, source="INSTAGRAM_ADS", lead_date=T0),
            models.Lead(full_name="B", email="b@example.com", phone="+5499999999999", source="FACEBOOK_ADS", lead_date=T0),  # ya tiene
            models.Lead(full_name="C", email="c@example.com", phone=None, source="WEB_UNPO", lead_date=T0),  # no es Meta
            models.Lead(full_name="D", email="d@example.com", phone=None, source="INSTAGRAM_ADS", lead_date=T0),  # sin match
            models.Lead(full_name="N", email="n@example.com", phone=None, source="INSTAGRAM_NORA", lead_date=T0),  # NORA
        ])
        db.commit()
        db.close()
        self.env = mock.patch.dict("os.environ", {"META_PAGE_ACCESS_TOKEN": "tok-ficticio", "META_PAGE_ID": "123"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def _run(self, apply):
        fake_meta = [
            {"id": "m1", "created_time": "2026-08-10T12:00:00+0000", "platform": "ig",
             "field_data": [{"name": "email", "values": ["a@example.com"]},
                            {"name": "teléfono", "values": ["+5490000000001"]}]},
            {"id": "m2", "created_time": "2026-08-10T12:00:00+0000", "platform": "ig",
             "field_data": [{"name": "email", "values": ["b@example.com"]},
                            {"name": "teléfono", "values": ["+5490000000002"]}]},
            {"id": "m3", "created_time": "2026-08-10T12:00:00+0000", "platform": "ig",
             "field_data": [{"name": "email", "values": ["n@example.com"]},
                            {"name": "teléfono", "values": ["+5490000000009"]}]},
        ]
        with mock.patch.object(bf, "fetch_meta_leads", return_value=fake_meta), \
             mock.patch.object(bf, "SessionLocal", self.Session):
            bf.run(apply=apply)

    def _phones(self):
        db = self.Session()
        try:
            return {l.email: l.phone for l in db.query(models.Lead).all()}
        finally:
            db.close()

    def test_dry_run_writes_nothing(self):
        self._run(apply=False)
        self.assertIsNone(self._phones()["a@example.com"])

    def test_apply_fills_only_meta_unpo_without_phone(self):
        self._run(apply=True)
        p = self._phones()
        self.assertEqual(p["a@example.com"], "+5490000000001")   # completado
        self.assertEqual(p["b@example.com"], "+5499999999999")   # no pisado
        self.assertIsNone(p["c@example.com"])                    # WEB no se toca
        self.assertIsNone(p["d@example.com"])                    # sin match
        self.assertIsNone(p["n@example.com"])                    # NORA intacto

    def test_aborts_without_token(self):
        with mock.patch.dict("os.environ", {"META_PAGE_ACCESS_TOKEN": "", "META_PAGE_ID": ""}):
            with self.assertRaises(SystemExit):
                bf.run(apply=False)

    def test_page_id_optional_when_token_present(self):
        # Sin META_PAGE_ID no aborta: la Página se autodetecta (acá fetch está mockeado).
        with mock.patch.dict("os.environ", {"META_PAGE_ID": ""}):
            self._run(apply=False)  # no lanza


if __name__ == "__main__":
    unittest.main(verbosity=2)
