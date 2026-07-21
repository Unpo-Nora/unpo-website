"""
Webhook de WhatsApp Cloud API (Meta) — Etapa 1C: fundación de recepción.

Rutas (definidas en el documento de arquitectura §6):

    GET  /whatsapp/webhook   handshake de verificación (hub.challenge)
    POST /whatsapp/webhook   recepción de eventos, con firma X-Hub-Signature-256

Ambos endpoints son **públicos por diseño** (Meta no envía JWT): la autenticación del
POST es la firma HMAC, y la del GET es el verify token. No usan `get_current_user`.

El router es deliberadamente delgado: valida transporte y orquesta los servicios de
`app/services/whatsapp/`. No contiene lógica de negocio ni consultas SQL.
"""

import json
import logging
import hmac

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.whatsapp import config as wa_config
from ..services.whatsapp import events as wa_events
from ..services.whatsapp import processor as wa_processor
from ..services.whatsapp.normalizer import normalize_envelope
from ..services.whatsapp.redaction import safe_error, short_key
from ..services.whatsapp.signature import SIGNATURE_HEADER, verify_signature

logger = logging.getLogger("uvicorn.error")

router = APIRouter(
    prefix="/whatsapp",
    tags=["whatsapp"],
)

WEBHOOK_PATH = "/webhook"
SUBSCRIBE_MODE = "subscribe"


@router.get(WEBHOOK_PATH)
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Handshake de verificación de Meta.

    Devuelve `hub.challenge` en texto plano con 200 únicamente si `hub.mode` es
    `subscribe` y el verify token coincide (comparación en tiempo constante).
    Cualquier otro caso — token inválido, modo inválido o parámetros faltantes —
    responde 403 con un mensaje genérico: no se distingue el motivo para no dar un
    oráculo, y el verify token NUNCA se registra ni se devuelve.
    """
    verify_token = wa_config.get_verify_token()
    if not verify_token:
        # Falla controlada: sin token configurado no se valida "contra vacío".
        logger.error("[whatsapp-webhook] %s no está configurado", wa_config.VERIFY_TOKEN_ENV)
        raise HTTPException(
            status_code=503,
            detail=f"{wa_config.VERIFY_TOKEN_ENV} no está configurado en el entorno.",
        )

    valid = (
        hub_mode == SUBSCRIBE_MODE
        and bool(hub_verify_token)
        and bool(hub_challenge)
        and hmac.compare_digest(hub_verify_token, verify_token)
    )
    if not valid:
        logger.warning("[whatsapp-webhook] verificación rechazada mode=%s", hub_mode)
        raise HTTPException(status_code=403, detail="Verification failed")

    logger.info("[whatsapp-webhook] verificación OK")
    return PlainTextResponse(content=hub_challenge)


@router.post(WEBHOOK_PATH)
async def receive_whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Recepción de eventos de WhatsApp Cloud API.

    Secuencia (arquitectura §7):
      1. leer el cuerpo CRUDO una sola vez y acotar su tamaño;
      2. validar la firma `X-Hub-Signature-256` sobre esos bytes (obligatoria);
      3. recién ahí parsear el JSON;
      4. persistir el evento con `event_key` determinístico (idempotente);
      5. procesar los elementos soportados;
      6. marcar el resultado del procesamiento y responder 200.

    Códigos: 403 firma inválida/ausente · 400 JSON inválido · 413 cuerpo excesivo ·
    503 App Secret sin configurar · 500 si NO se pudo almacenar el evento (Meta
    reintenta) · 200 si el evento quedó almacenado, incluso si el procesamiento
    posterior falló (el evento queda en `failed` para reproceso, sin pérdida).
    """
    # Corte temprano por Content-Length: evita bufferizar un cuerpo enorme en memoria.
    declared_length = request.headers.get("content-length", "")
    if declared_length.isdigit() and int(declared_length) > wa_config.MAX_WEBHOOK_BODY_BYTES:
        logger.warning("[whatsapp-webhook] cuerpo rechazado por content-length")
        raise HTTPException(status_code=413, detail="Payload demasiado grande")

    raw_body = await request.body()
    # Segundo corte: la cabecera puede faltar o mentir (transfer-encoding: chunked).
    if len(raw_body) > wa_config.MAX_WEBHOOK_BODY_BYTES:
        logger.warning("[whatsapp-webhook] cuerpo rechazado por tamaño bytes=%d", len(raw_body))
        raise HTTPException(status_code=413, detail="Payload demasiado grande")

    app_secret = wa_config.get_app_secret()
    if not app_secret:
        # La firma es OBLIGATORIA: sin App Secret el endpoint no acepta nada.
        logger.error("[whatsapp-webhook] %s no está configurado", wa_config.APP_SECRET_ENV)
        raise HTTPException(
            status_code=503,
            detail=f"{wa_config.APP_SECRET_ENV} no está configurado en el entorno.",
        )

    signature = request.headers.get(SIGNATURE_HEADER, "")
    if not verify_signature(app_secret, raw_body, signature):
        # No se registra la firma recibida ni el cuerpo.
        logger.warning("[whatsapp-webhook] firma inválida o ausente signature_present=%s",
                       bool(signature))
        raise HTTPException(status_code=403, detail="Firma X-Hub-Signature-256 inválida")

    try:
        payload = json.loads(raw_body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("[whatsapp-webhook] JSON inválido con firma válida")
        raise HTTPException(status_code=400, detail="Payload JSON inválido")

    normalized = normalize_envelope(payload)

    try:
        persisted = wa_events.persist_event(
            db,
            event_key=normalized.event_key,
            payload_hash=normalized.payload_hash,
            event_type=normalized.event_type,
            raw_payload=payload,
        )
    except Exception as exc:  # noqa: BLE001 — sin evento almacenado no hay garantía
        db.rollback()
        logger.exception("[whatsapp-webhook] no se pudo persistir el evento")
        raise HTTPException(status_code=500, detail="No se pudo almacenar el evento") from exc

    if persisted.duplicate:
        logger.info("[whatsapp-webhook] evento duplicado event_key=%s status=%s",
                    short_key(normalized.event_key, 20), persisted.event.processing_status)
        return {"status": "duplicate", "duplicate": True}

    logger.info(
        "[whatsapp-webhook] evento aceptado event_key=%s type=%s messages=%d statuses=%d",
        short_key(normalized.event_key, 20), normalized.event_type,
        normalized.total_messages, normalized.total_statuses,
    )

    report = wa_processor.process_event(db, normalized)
    result_status = report.resolve_status()
    try:
        wa_events.mark_processing_result(
            db, persisted.event, status=result_status, error=report.summary_error()
        )
    except Exception as exc:  # noqa: BLE001 — el evento ya está almacenado
        db.rollback()
        logger.error("[whatsapp-webhook] no se pudo marcar el resultado: %s", safe_error(exc))

    if report.errors:
        logger.error("[whatsapp-webhook] procesamiento con errores event_key=%s errores=%d",
                     short_key(normalized.event_key, 20), len(report.errors))

    return {"status": result_status, "duplicate": False}
