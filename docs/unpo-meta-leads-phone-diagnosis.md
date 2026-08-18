# Leads de Meta sin teléfono — diagnóstico y corrección (2026-08-18)

## Síntoma reportado

Los vendedores notaron que "estos últimos días" llegaban muchos leads de Instagram/Facebook
al CRM sin número de teléfono y que, además, esos leads ya no enviaban el WhatsApp inicial
que antes sí llegaba. Pregunta: ¿es un bug nuestro, o la gente puede optar por no enviar el
mensaje (como afirma la agencia que maneja la pauta)?

## Datos (agregados sobre la API productiva, sin extraer PII)

Últimas 10 semanas (junio → agosto 2026), leads UNPO:

| Origen | Leads | Sin teléfono |
|---|---|---|
| `INSTAGRAM_ADS` + `FACEBOOK_ADS` | 812 | **812 (100 %)** — todas las semanas, sin excepción |
| `WEB_UNPO` | ~150 | **0** |

Los leads de Meta llegan completos en todo lo demás: nombre real, email real y las cinco
preguntas personalizadas del formulario (`business_type`, `purchase_volume`,
`category_interest`, `experience_level`, `product_interest`). Solo el teléfono falta.

## Conclusión: son DOS problemas distintos

1. **Teléfono ausente → problema nuestro, y desde siempre.** `meta_api.transform_meta_lead_to_schemas`
   solo reconocía el teléfono con los nombres estándar de Meta (`phone_number` / `phone`). El
   formulario de la agencia pide el teléfono como **pregunta personalizada**, cuyo nombre lo
   genera Meta a partir del texto de la pregunta (estilo `¿cuál_es_tu_whatsapp?`), y ese
   nombre nunca coincidió. El campo se descartaba en silencio. Las preguntas de negocio sí
   estaban mapeadas una por una con su nombre exacto; el teléfono quedó afuera.
2. **"Dejaron de mandar WhatsApp" → externo.** El CRM no envía mensajes a los leads de Meta ni
   les pide que escriban: ese paso es la pantalla final del formulario de Meta (configurada por
   la agencia), y el usuario siempre pudo omitirlo. Cuando la gente lo tocaba, el WhatsApp era
   lo que le daba el número al vendedor y tapaba el problema 1. Cuando dejaron de tocarlo,
   quedó expuesto.

## Corrección aplicada

- `backend/app/meta_api.py`: detección **tolerante** del teléfono por palabra clave (`phone`,
  `telefono`, `celular`, `whatsapp`, `movil`, `cel`) normalizando acentos, mayúsculas y signos
  `¿?`; ídem para nombre y email. Primer teléfono gana. Los nombres de campo NO reconocidos y
  los leads que quedan sin teléfono se loguean **solo por nombre de campo** (nunca valores),
  para que un futuro cambio del formulario no vuelva a perder datos en silencio.
- `backend/app/crud.py`: todos los leads `WEB_UNPO` se asignan a un único vendedor
  (`WEB_UNPO_SELLER_PHONE`, default Martín Trojavcich), sin la rotación anterior. NORA intacto.
- Tests: `backend/tests/test_meta_lead_mapping.py` (18 casos).

## Pendientes fuera del código

- Pedirle a la agencia el nombre exacto de la pregunta del teléfono en el formulario y
  confirmar que la corrección lo cubre (los logs `[meta-leads]` de Render lo muestran).
- Los leads históricos sin teléfono no se recuperan desde el CRM (nunca se guardó). Meta
  retiene los leads 90 días: con el export CSV de la agencia se pueden importar.
- El WhatsApp inicial del lead es decisión del formulario/agencia; si se quiere forzar, es
  configuración del lado de Meta, no del CRM.
