"""
Backfill de teléfonos de leads históricos de Meta Lead Ads (UNPO).

Contexto (2026-08-18, ver docs/unpo-meta-leads-phone-diagnosis.md): hasta el PR #33 el
CRM descartaba el teléfono de los leads de Instagram/Facebook porque venía como pregunta
personalizada del formulario. Los leads quedaron guardados con nombre y email pero sin
teléfono. Meta retiene las respuestas de cada formulario ~90 días: este script las vuelve
a bajar y completa el teléfono de los leads existentes.

Cómo cruza: los leads del CRM NO guardan el `leadgen_id` de Meta, así que se cruzan por
EMAIL (normalizado) y, como desempate, por cercanía de fecha. Solo toca leads UNPO de
Meta (INSTAGRAM_ADS / FACEBOOK_ADS) que hoy no tienen teléfono. Nunca pisa un teléfono
existente. NORA no se toca.

Requiere en el entorno: DATABASE_URL, META_PAGE_ACCESS_TOKEN (el mismo del webhook) y
META_PAGE_ID (id numérico de la Página de Facebook de UNPO). Uso, desde backend/:

    python -m scripts.maintenance.backfill_meta_lead_phones            # dry-run (no escribe)
    python -m scripts.maintenance.backfill_meta_lead_phones --apply    # escribe

Seguridad: NO imprime teléfonos, emails ni nombres; solo conteos e ids internos.
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import httpx
from sqlalchemy import or_

from app import models
from app.database import SessionLocal
from app.meta_api import _graph_url, transform_meta_lead_to_schemas

META_SOURCES = ("INSTAGRAM_ADS", "FACEBOOK_ADS")
PAGE_SIZE = 100
# Tolerancia para el desempate por fecha entre el created_time de Meta y nuestro lead.
MAX_DATE_DELTA_HOURS = 48


def _norm_email(email: Optional[str]) -> Optional[str]:
    e = (email or "").strip().lower()
    return e if e and e != "unknown@example.com" else None


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # Meta: 2026-08-18T12:00:00+0000
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


def _get_paginated(client: httpx.Client, url: str, params: dict) -> List[dict]:
    """Recorre la paginación de Graph API (`paging.next`)."""
    items: List[dict] = []
    next_url: Optional[str] = url
    next_params: Optional[dict] = params
    while next_url:
        r = client.get(next_url, params=next_params)
        if r.status_code != 200:
            # Sin body crudo (puede traer datos personales): solo status.
            print(f"  ! Graph API HTTP {r.status_code} en {next_url.split('?')[0].rsplit('/', 1)[-1]}")
            break
        data = r.json()
        items.extend(data.get("data", []))
        next_url = (data.get("paging") or {}).get("next")
        next_params = None  # `next` ya trae los params embebidos
    return items


def resolve_page_ids(client: httpx.Client, token: str, page_id_env: str) -> List[str]:
    """
    IDs de Página a recorrer. Si META_PAGE_ID está seteado, solo esa. Si no, se
    autodetectan desde el token: un Page Access Token responde a `/me` con la Página
    misma; un User token lista sus Páginas en `/me/accounts`.
    """
    if page_id_env:
        return [page_id_env]
    base = _graph_url()
    r = client.get(f"{base}/me", params={"access_token": token, "fields": "id,name"})
    if r.status_code == 200:
        me = r.json()
        # Un Page token devuelve directamente la Página.
        accounts = _get_paginated(client, f"{base}/me/accounts",
                                  {"access_token": token, "fields": "id,name", "limit": PAGE_SIZE})
        ids = [a["id"] for a in accounts if a.get("id")]
        if not ids and me.get("id"):
            ids = [str(me["id"])]
        print(f"Páginas detectadas desde el token: {len(ids)}")
        return ids
    print(f"  ! No se pudo resolver la Página desde el token (HTTP {r.status_code}). Seteá META_PAGE_ID.")
    return []


def fetch_meta_leads(token: str, page_id: str) -> List[dict]:
    """Todos los leads (≤90 días) de todos los formularios de la(s) Página(s)."""
    base = _graph_url()
    with httpx.Client(timeout=30.0) as client:
        page_ids = resolve_page_ids(client, token, page_id)
        forms: List[dict] = []
        for pid in page_ids:
            forms.extend(_get_paginated(client, f"{base}/{pid}/leadgen_forms",
                                        {"access_token": token, "fields": "id,name,status", "limit": PAGE_SIZE}))
        print(f"Formularios encontrados: {len(forms)}")
        leads: List[dict] = []
        for form in forms:
            form_leads = _get_paginated(
                client, f"{base}/{form['id']}/leads",
                {"access_token": token,
                 "fields": "id,created_time,field_data,platform,ad_name,campaign_name",
                 "limit": PAGE_SIZE},
            )
            print(f"  formulario {form.get('id')} ({form.get('status')}): {len(form_leads)} leads")
            leads.extend(form_leads)
    return leads


def build_meta_index(meta_leads: List[dict]) -> Dict[str, List[Tuple[datetime, str]]]:
    """email normalizado -> [(created_time, phone)] usando el MISMO transformador del webhook."""
    index: Dict[str, List[Tuple[datetime, str]]] = {}
    sin_tel = 0
    for raw in meta_leads:
        t = transform_meta_lead_to_schemas(raw)
        email = _norm_email(t.get("email"))
        phone = (t.get("phone") or "").strip()
        if not phone:
            sin_tel += 1
            continue
        if not email:
            continue
        index.setdefault(email, []).append((_parse_dt(raw.get("created_time")) or datetime.min.replace(tzinfo=timezone.utc), phone))
    print(f"Leads de Meta con teléfono y email utilizables: {sum(len(v) for v in index.values())} (sin teléfono en Meta: {sin_tel})")
    return index


def _pick_phone(candidates: List[Tuple[datetime, str]], lead_dt: Optional[datetime]) -> Optional[str]:
    if not candidates:
        return None
    if len(candidates) == 1 or lead_dt is None:
        return candidates[0][1]
    if lead_dt.tzinfo is None:
        lead_dt = lead_dt.replace(tzinfo=timezone.utc)
    best = min(candidates, key=lambda c: abs((c[0] - lead_dt).total_seconds()))
    if abs((best[0] - lead_dt).total_seconds()) > MAX_DATE_DELTA_HOURS * 3600:
        # Mismo email con varios leads lejanos en el tiempo: no adivinar.
        return None
    return best[1]


def run(apply: bool) -> None:
    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    page_id = os.getenv("META_PAGE_ID", "").strip()  # opcional: si falta se autodetecta
    if not token:
        print("Falta META_PAGE_ACCESS_TOKEN en el entorno. Abortando.")
        sys.exit(1)

    print(f"Modo: {'APPLY (escribe)' if apply else 'DRY-RUN (no escribe)'}")
    meta_leads = fetch_meta_leads(token, page_id)
    index = build_meta_index(meta_leads)

    db = SessionLocal()
    try:
        targets = (
            db.query(models.Lead)
            .filter(models.Lead.source.in_(META_SOURCES),
                    or_(models.Lead.phone.is_(None), models.Lead.phone == ""))
            .all()
        )
        print(f"Leads UNPO de Meta sin teléfono en el CRM: {len(targets)}")

        matched, ambiguous, no_match = 0, 0, 0
        for lead in targets:
            email = _norm_email(lead.email)
            candidates = index.get(email, []) if email else []
            if not candidates:
                no_match += 1
                continue
            phone = _pick_phone(candidates, lead.lead_date or lead.created_at)
            if not phone:
                ambiguous += 1
                continue
            matched += 1
            if apply:
                lead.phone = phone
        if apply:
            db.commit()
        print(f"Resultado: completados={matched} ambiguos(no tocados)={ambiguous} sin_match_en_meta={no_match}")
        if not apply:
            print("Dry-run: no se escribió nada. Repetir con --apply para guardar.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill de teléfonos de leads históricos de Meta (UNPO).")
    parser.add_argument("--apply", action="store_true", help="Escribe en la DB (default: dry-run).")
    args = parser.parse_args()
    run(apply=args.apply)
