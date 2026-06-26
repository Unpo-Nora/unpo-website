// Etapa 4.1-A — Tipos frontend propios del CRM NORA.
//
// Reflejan los campos que el board de leads NORA usa hoy y que YA existen en el
// modelo `Lead` del backend (backend/app/models.py, tabla `leads`).
// No se inventan campos nuevos ni se tocan modelos backend.
//
// Aislamiento: NORA deja de depender de la `interface Lead` declarada dentro de
// NoraDashboard.tsx, para poder evolucionar sin afectar la versión legacy.

import type { NoraLeadStatus } from "./leadStatus";

/**
 * Lead tal como lo consume el CRM NORA en el frontend.
 *
 * Espejo del subconjunto de columnas de la tabla `leads` que el board usa.
 * La nullability refleja la del backend:
 *  - `product_interest`, `notes`, `feedback_status`, `seller` son nullable.
 *  - `lead_date` y `contacted_at` son nullable; `created_at` siempre viene seteado.
 * `status` se tipa laxo (NoraLeadStatus | string) porque el backend puede
 * devolver cualquier valor del enum `LeadStatus`; NORA solo opera sobre
 * los estados de NoraLeadStatus.
 */
export interface NoraLead {
    id: number;
    full_name: string;
    email: string;
    phone: string;
    product_interest: string | null;
    source: string;
    status: NoraLeadStatus | string;
    lead_date?: string | null;
    created_at?: string | null;
    contacted_at?: string | null;
    seller: string | null;
    notes: string | null;
    feedback_status: string | null;
}
