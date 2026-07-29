# UNPO — Frontend del inbox multiagente de WhatsApp (Etapa 1H)

MVP del inbox de WhatsApp con **polling** (sin SSE/WebSocket), marcado de lectura y
asignación administrativa. Consume la API autenticada de 1G
([unpo-whatsapp-inbox-api.md](./unpo-whatsapp-inbox-api.md)) más la extensión de paginación
bidireccional agregada en 1H. **No** implementa envío de mensajes ni media.

## Ruta y navegación

- Ruta: **`/admin/whatsapp`** ([`frontend/app/admin/whatsapp/page.tsx`](../frontend/app/admin/whatsapp/page.tsx)),
  dentro del portal admin existente (no es una ruta pública `/whatsapp`).
- Item en el Sidebar ([`components/dashboard/Sidebar.tsx`](../frontend/components/dashboard/Sidebar.tsx)):
  `WhatsApp` (icono `MessageCircle`), roles `["admin","vendedor"]`. A otros roles no se les
  muestra el link.
- **Autorización**: la página valida el rol además de ocultar el link (ocultar no alcanza
  como control de acceso); un rol no permitido se redirige a `/admin/sales`. El backend sigue
  siendo la autoridad real de acceso.

## Componentes

Todos en [`frontend/components/dashboard/whatsapp/`](../frontend/components/dashboard/whatsapp/):

| Componente | Responsabilidad |
|---|---|
| `WhatsAppInboxDashboard` | Orquestador: estado, polling, mark-read, asignación, layout responsive. |
| `WhatsAppFilters` | Buscador + buckets (Todas / Asignadas a mí / Sin asignar) + línea + estado + no leídas. |
| `ConversationList` / `ConversationListItem` | Lista de conversaciones (skeleton, empty/sin-resultados, "cargar más"). |
| `ConversationPanel` | Panel derecho: header (contacto/línea/estado/asignación), timeline, historial, pie deshabilitado. |
| `MessageTimeline` / `MessageBubble` | Historial: scroll, "cargar anteriores", "N nuevos", burbujas in/out con estados. |
| `AssignmentControl` | Admin: selector + botón explícito + confirmación al reasignar. Vendedor: solo lectura. |
| `AssignmentHistory` | Historial colapsable con nombres resueltos; no bloquea si falla. |
| `UnreadBadge`, `WhatsAppEmptyState` | UI compartida. |

Cliente/tipos: [`frontend/lib/whatsapp/`](../frontend/lib/whatsapp/) — `types.ts` (contrato),
`api.ts` (`whatsappApi`, fetch + Bearer + `AbortController` + errores tipados), `format.ts`
(fecha/hora, etiqueta de contacto, estado). No se usa `any`.

## Polling

Se usa **polling** con `setInterval` + `AbortController` (sin SSE/WebSocket):

| Recurso | Intervalo |
|---|---|
| `GET /whatsapp/unread-counts` | 10 s |
| `GET /whatsapp/conversations` | 7 s |
| Mensajes nuevos de la conversación abierta | 4 s |

Reglas: sin requests superpuestos (se aborta el previo); se **pausa** cuando
`document.hidden = true` y se **refresca** al volver visible (`visibilitychange`); los timers y
`AbortController` se limpian al desmontar; un fallo temporal **no borra** los datos ya
cargados; tras fallos consecutivos se muestra **"Reconectando…"**; un `401` usa el `logout`
del `AuthContext`; un error de red **no** cierra la sesión. La lista se reemplaza solo si su
firma cambió (evita flicker). Botón manual **"Actualizar"** y marca de última actualización.

## Paginación de mensajes (bidireccional)

- **Apertura**: `direction=backward&limit=50` → últimos N; el timeline hace scroll inicial al
  final.
- **"Cargar mensajes anteriores"** (scroll arriba): `direction=backward&cursor=older_cursor`;
  se **preserva la posición** de lectura al anteponer.
- **Polling de nuevos**: `direction=forward&cursor=newer_cursor`; se **deduplica por
  `message.id`** y se ordena por `(created_at, id)`. Si el usuario está cerca del final, se
  mantiene abajo; si está leyendo arriba, no se fuerza scroll y se muestra "N mensajes
  nuevos".

Nunca se recorren todas las páginas desde el inicio.

## Marcado de lectura

`POST /whatsapp/conversations/{id}/read` con `{ last_read_message_id }` (último id cargado).
Se marca **solo** cuando: la conversación fue abierta, los mensajes cargaron, la pestaña está
visible (`document.hidden = false`), `unread_count > 0`, hay al menos un mensaje y ese id no se
marcó ya. El estado local (badges, total, línea, conversación) se actualiza **después** del
HTTP 200. No se marca durante prefetch ni con la pestaña oculta, ni se marcan otras
conversaciones.

## Asignación

- **Admin**: carga usuarios asignables (ver abajo), muestra selector + botón explícito
  **Asignar/Reasignar**; no cambia al seleccionar; **confirma** antes de reasignar una
  conversación ya asignada; `PATCH /whatsapp/conversations/{id}/assignment` solo tras
  confirmar; refresca detalle, lista e historial con toast (sin recargar la página). El
  agente elegido y la confirmación se **resetean** al cambiar de conversación.
- **Vendedor**: asignación **solo lectura**; no carga `/users/`, no renderiza selector ni
  llama al PATCH.
- **Desasignar no está habilitado** (el backend no lo permite en esta etapa).

### Usuarios asignables — `GET /users/` (solo admin)

Se **reutiliza** `GET /users/` (endpoint admin-only existente) en lugar de crear uno nuevo. El
frontend usa exclusivamente `id`, `full_name` y `role`; **no muestra ni guarda el email** ni
otros datos. Los vendedores no llaman `/users/`. El historial de asignaciones resuelve
`from_user_id`/`to_user_id`/`assigned_by_user_id` a nombres con esa lista; si un id no se puede
resolver, muestra `Usuario #<id>`.

## Permisos (resumen)

- Link + página visibles para `admin` y `vendedor`; validación de rol en la página.
- Admin ve/gestiona todo; vendedor ve solo sus conversaciones autorizadas y no ve controles
  de asignación. El backend valida cada acceso (autoridad final).

## Responsive

- **Desktop**: dos columnas — lista ~360 px + panel flexible; scroll independiente de lista y
  timeline; altura contenida dentro del layout admin.
- **Mobile**: primero la lista; al seleccionar se muestra solo la conversación con botón
  **volver**; filtros accesibles; sin dos columnas comprimidas ni scroll horizontal.

## Seguridad frontend

No se registra el JWT ni respuestas completas; no se guarda contenido de mensajes ni teléfonos
en `localStorage`; el texto se renderiza **como texto** (nunca `dangerouslySetInnerHTML`); el
teléfono llega **enmascarado** desde el backend y se respeta; no se renderizan `raw_payload`,
`external_message_id`, `phone_number_id` ni `waba_id` (el backend no los expone). Ocultar
botones no sustituye la autorización del backend.

## Estados cubiertos

Loading de líneas/conversaciones/mensajes; sin líneas; sin conversaciones; sin resultados de
búsqueda; conversación sin mensajes; `401` (logout); `403`; `404` (se limpia la selección, se
quita del listado y se vuelve a la lista en mobile); error de red / backend indisponible
("Reconectando…"); fallo de asignación (toast); fallo de marcado de lectura (toast). No se
muestran stack traces ni respuestas técnicas crudas.

## Validación

```bash
# backend
python -m compileall -q app tests
python -m unittest tests.test_whatsapp_inbox -v   # 67 PASS (incluye direction=backward)
python -m unittest discover -s tests -t .          # 335 PASS, 6 skipped
# PostgreSQL 17: alembic upgrade head / current / heads / check + escenarios de paginación

# frontend (desde frontend/)
npx tsc --noEmit      # typecheck
npm run build         # incluye lint + type-check de Next
```

`package.json` no define `typecheck` ni `test` (no se inventan). No hay framework de tests
frontend configurado en esta etapa; el código nuevo pasa `tsc --noEmit`, `next build` y ESLint
`next/core-web-vitals` (scoped) sin warnings.

## Fuera de alcance (1H)

- Envío de mensajes salientes (el pie del panel lo informa: "El envío de mensajes se habilitará
  en una próxima etapa").
- Media / adjuntos.
- SSE / WebSocket (el MVP usa polling).
- Conversión manual a lead, cierre/reapertura.
- Conexión de números reales y cualquier cosa de **NORA**.
- Automatizaciones de IA.
