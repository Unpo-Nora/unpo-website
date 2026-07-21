"""
Servicios del webhook de WhatsApp Cloud API (Meta).

Separación de responsabilidades (el router solo orquesta):

    config      -> lectura de configuración/secretos desde el entorno
    signature   -> validación HMAC-SHA256 de X-Hub-Signature-256
    redaction   -> helpers de logging seguro (nunca datos personales completos)
    normalizer  -> parseo/normalización del envelope de Meta + event_key determinístico
    events      -> persistencia e idempotencia en whatsapp_webhook_events
    processor   -> resolución de línea/contacto/conversación y alta de mensajes/estados

Ningún módulo de este paquete se conecta a Meta ni envía mensajes: la Etapa 1C es
exclusivamente de recepción.
"""
