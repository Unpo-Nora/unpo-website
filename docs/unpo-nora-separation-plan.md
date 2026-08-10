# Separación UNPO / NORA — Diagnóstico y plan técnico

> Estado: **diagnóstico + plan** (etapas 1 y 2 del proceso obligatorio de CLAUDE.md).
> La implementación (etapa 3) NO comienza hasta validar este plan, porque requiere
> decisiones de negocio: dominios, hosting, y si NORA tendrá base de datos propia.
> Fecha: 2026-08-10.

## Modelo objetivo (regla de negocio, ya definida)

- NORA deja de ser sub-marca de UNPO: marca completamente separada.
- NORA tiene **CRM propio** y **web pública propia**, cada uno en **su propio dominio**
  (distintos entre sí y distintos de UNPO).
- Vendedor dedicado NORA: WhatsApp **1131488378**. Los leads UNPO no van a ese número
  y los leads NORA no van a vendedores UNPO.

## Etapa 1 — Diagnóstico: qué está compartido HOY

### Backend (una sola app FastAPI, una sola DB)

| Recurso compartido | Detalle | Riesgo de mezcla |
|---|---|---|
| Tabla `Lead` | Única para ambas marcas; se distingue por `source` (`WEB_UNPO`, `WEB_NORA`, `FACEBOOK_NORA`, `INSTAGRAM_NORA`) y query param `brand` | Alto: un filtro olvidado mezcla leads |
| `crud.create_lead` | Una sola función asigna vendedores de ambas marcas; teléfonos UNPO (`1144227969`, `1167063123`) y NORA (`1131488378`) hardcodeados en el mismo bloque | Alto |
| `routers/leads.py` | Contiene los DOS webhooks de Meta (UNPO sin firma; NORA con firma validada) y los endpoints de leads de ambas marcas | Alto |
| `User` / auth / JWT | Un solo login y una sola tabla de usuarios para el staff de ambas marcas | Medio |
| Products/Sales/Finance/HR | Hoy son solo-UNPO en la práctica, pero viven en la misma app y DB | Bajo |
| Variables Meta | `META_*` (UNPO) y `NORA_META_*` (NORA) ya separadas por nombre — único límite ya trazado | — |
| `backend/data/NORA/` | Assets NORA dentro del repo/almacenamiento UNPO | Bajo |

### Frontend (una sola app Next.js)

| Recurso compartido | Detalle |
|---|---|
| Route groups | `app/(unpo)` y `app/(nora)/nora` en el mismo proyecto y dominio |
| Portales admin | `/admin` (UNPO) y `/nora-admin` (NORA) en la misma app; además persiste el CRM NORA legacy dentro del panel UNPO (`/admin/nora` → `NoraDashboard`, link "Waitlist NORA" en el Sidebar UNPO) — duplicado del `/nora-admin` nuevo |
| Capa común | `AuthContext`, `lib/api.ts`, `lib/format.ts` sirven a ambas marcas |
| Logins/layouts/sidebars | Duplicados por copy-paste entre marcas (~60-80 % idénticos). **A propósito no se unificaron** en la corrección 2026-08: fusionarlos iría contra la separación |
| Dominio | Todo cuelga del mismo deploy (unpo.com.ar / vercel) |

### Infra

- Un solo `docker-compose`, una sola Postgres (`unpo_nora_db`), un solo backend en Render.
- CORS: una sola allowlist para ambas marcas.

## Etapa 2 — Plan técnico por etapas

Cada etapa termina con validación (tests + smoke test) antes de pasar a la siguiente.
Nunca se borra código UNPO sin aprobación explícita.

**Fase A — Frontera limpia dentro del monolito (sin infra nueva, bajo riesgo)**
1. Backend: extraer `routers/nora_leads.py` (webhook NORA + endpoints de prospectos NORA) y un `services/lead_assignment.py` con la asignación por marca; los teléfonos salen de `crud.py` hacia settings/env por marca.
2. Backend: hacer `brand` obligatorio en las consultas de leads (default explícito, nunca implícito).
3. Frontend: retirar el CRM NORA legacy del panel UNPO (`/admin/nora`, `NoraDashboard`, link del Sidebar) — requiere aprobación porque elimina una pantalla en uso; `/nora-admin` ya lo reemplaza.
4. Validación: suite de backend + tests nuevos de aislamiento por marca (un vendedor UNPO no ve leads NORA y viceversa).

**Fase B — Identidad NORA separada (decisiones de negocio necesarias)**
5. Registrar dominios: web pública NORA y CRM NORA (distintos entre sí). ← decisión/compra del usuario
6. Decidir DB: ¿schema separado en la misma Postgres o instancia propia? Recomendación inicial: schema separado + usuario de DB propio (barato, reversible), instancia propia recién si NORA escala.
7. Usuarios/roles: separar staff NORA (al menos por rol/claim de marca en el JWT; ideal: tabla o tenant propio).

**Fase C — Deploy separado**
8. Frontend NORA como proyecto Next propio (se extrae `app/(nora)`, `components/nora`, `lib/nora`) desplegado en su dominio; CRM NORA ídem en el suyo.
9. Backend: servicio NORA propio (o el mismo código con `BRAND=nora` y DB/schema propio) con CORS solo para los dominios NORA.
10. Migración de datos: mover los leads con `source` NORA al almacenamiento NORA; redirects desde `unpo.com.ar/nora` al dominio nuevo.
11. Validación final: leads de prueba por cada canal (web, FB, IG) verificando que lleguen SOLO al CRM y WhatsApp correctos.

## Qué NO hacer (anti-objetivos)

- No unificar componentes de UI entre marcas "por DRY": la duplicación entre marcas es
  deseable aquí porque van a repos distintos.
- No borrar código UNPO al construir NORA sin aprobación.
- No tocar los webhooks productivos de Meta sin plan de rollback (Meta reintenta, pero
  la verificación de dominio/token es frágil).
