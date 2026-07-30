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

Cliente/tipos/hooks: [`frontend/lib/whatsapp/`](../frontend/lib/whatsapp/) — `types.ts`
(contrato), `api.ts` (`whatsappApi`, fetch + Bearer + `AbortController` + errores tipados),
`format.ts` (fecha/hora, etiqueta de contacto, estado). La lógica está extraída en hooks
(el orquestador quedó delgado): `useWhatsAppInboxData` (líneas, no leídos, conversaciones con
paginación/polling/recuperación), `useConversationMessages` (detalle, timeline, cursores,
polling y marcado de lectura) y `useAssignment`. No se usa `any`.

## Polling

Se usa **polling** con `setInterval` + `AbortController` (sin SSE/WebSocket):

| Recurso | Intervalo |
|---|---|
| `GET /whatsapp/unread-counts` | 10 s |
| `GET /whatsapp/conversations` | 7 s |
| Mensajes nuevos de la conversación abierta | 4 s |

Reglas: sin requests superpuestos (guards + se aborta el previo por recurso — unread,
líneas, asignables, conversaciones, detalle, historial, mensajes); se **pausa** cuando
`document.hidden = true` y se **refresca** al volver visible (`visibilitychange`); los timers y
`AbortController` se limpian al desmontar; un fallo temporal **no borra** los datos ya
cargados; tras fallos consecutivos se muestra **"Reconectando…"**; un `401` usa el `logout`
del `AuthContext`; un error de red **no** cierra la sesión. La lista se reemplaza solo si su
firma cambió (evita flicker). Botón manual **"Actualizar"** que además **reintenta** cargas
iniciales que hayan fallado (líneas, usuarios asignables) y marca de última actualización.

**Paginación de conversaciones**: incremental real por `offset` (carga inicial `limit=30,
offset=0`; "Cargar más" usa `offset=<cantidad cargada>`), con dedupe por `conversation_id` y
`has_more` del backend controlando el botón (se oculta cuando `has_more=false`). Soporta **más
de 100** conversaciones. El polling refresca la primera ventana (`offset=0`, `limit` = cantidad
cargada, cap 100) y hace **merge/dedup** sin descartar las páginas ya cargadas; cambiar filtros
reinicia lista y offset.

**Distinción de errores**: si la carga de líneas **falla** (red/servidor) se muestra un estado
de error con "Reintentar" (no "Sin líneas accesibles"); "Sin líneas accesibles" solo aparece
cuando la respuesta fue exitosa y vacía.

## Paginación de mensajes (bidireccional)

- **Apertura**: `direction=backward&limit=50` → últimos N; el timeline hace scroll inicial al
  final.
- **"Cargar mensajes anteriores"** (scroll arriba): `direction=backward&cursor=older_cursor`;
  se **preserva la posición** de lectura al anteponer.
- **Polling de nuevos**: `direction=forward&cursor=newer_cursor`; se **deduplica por
  `message.id`** y se ordena por `(created_at, id)`. Si el usuario está cerca del final, se
  mantiene abajo; si está leyendo arriba, no se fuerza scroll y se muestra "N mensajes
  nuevos".
- **Conversación inicialmente vacía**: si no hay `newer_cursor` (0 mensajes), el polling
  consulta `direction=forward` **sin cursor** para detectar el **primer mensaje**; una vez que
  llega, se fija `newer_cursor` y los polls siguientes solo traen posteriores (no re-descarga
  histórico). El primer mensaje aparece sin cerrar/reabrir la conversación.

Nunca se recorren todas las páginas desde el inicio.

## Marcado de lectura

`POST /whatsapp/conversations/{id}/read` con `{ last_read_message_id }` (último id cargado).
Se marca **solo** cuando: la conversación fue abierta, los mensajes cargaron, la pestaña está
visible (`document.hidden = false`), `unread_count > 0`, hay al menos un mensaje y ese id no se
marcó ya. El estado local (badges, total, línea, conversación) se actualiza **después** del
HTTP 200. No se marca durante prefetch ni con la pestaña oculta, ni se marcan otras
conversaciones.

Al **volver visible** la pestaña, si la conversación abierta tiene `unread_count > 0` se marca
hasta el último mensaje cargado **aunque no haya llegado ningún mensaje nuevo**, usando el
`unread_count` **real** de la conversación (no un valor capturado al abrirla). Se evita repetir
el mismo id y se previenen requests de mark-read superpuestos (guard en curso).

## Asignación

- **Admin**: carga usuarios asignables (ver abajo), muestra selector + botón explícito
  **Asignar/Reasignar**; no cambia al seleccionar; **confirma** antes de reasignar una
  conversación ya asignada; `PATCH /whatsapp/conversations/{id}/assignment` solo tras
  confirmar; refresca detalle, lista e historial con toast (sin recargar la página). El
  agente elegido y la confirmación se **resetean** al cambiar de conversación.
- **Vendedor**: asignación **solo lectura**; no carga `/users/`, no renderiza selector ni
  llama al PATCH.
- **Desasignar no está habilitado** (el backend no lo permite en esta etapa).

### Usuarios asignables — `GET /whatsapp/assignable-users` (solo admin)

Se usa el endpoint **dedicado** `GET /whatsapp/assignable-users` (admin-only), que devuelve
solo `id`, `full_name` y `role` de usuarios con rol asignable (`admin`/`vendedor`) — **sin
email** ni otros datos. El inbox ya **no** usa `GET /users/`. Los vendedores no lo llaman. El
`PATCH .../assignment` valida además que el usuario destino exista y tenga rol `admin`/
`vendedor` (otro rol → **400**). El historial de asignaciones resuelve
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

## Limitaciones conocidas

- **Estados de mensajes ya cargados**: el polling forward solo trae mensajes **nuevos** (los
  posteriores a `newer_cursor`); **no** re-consulta ni actualiza el `current_status` de
  mensajes ya renderizados. Como 1H no envía mensajes salientes, el impacto es mínimo, pero la
  actualización en vivo de estados (`sent → delivered → read`) de mensajes existentes queda
  para una etapa posterior (1I). No se afirma que los estados outbound se actualicen en tiempo
  real.
- El refresh de conversaciones por polling cubre la primera ventana (hasta 100); páginas más
  allá de 100 se refrescan al hacer "Cargar más" o "Actualizar".

## Fuera de alcance (1H)

- Envío de mensajes salientes (el pie del panel lo informa: "El envío de mensajes se habilitará
  en una próxima etapa").
- Media / adjuntos.
- SSE / WebSocket (el MVP usa polling).
- Conversión manual a lead, cierre/reapertura.
- Conexión de números reales y cualquier cosa de **NORA**.
- Automatizaciones de IA.
