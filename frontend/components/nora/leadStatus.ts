// Etapa 4.1-A — Andamiaje de estados de leads NORA (solo presentación).
//
// Estos valores son strings YA EXISTENTES en el enum `LeadStatus` del backend
// (backend/app/models.py). Acá NO se define ni se crea ningún enum nuevo ni se
// toca la DB: solo se mapean a labels visuales en español para el CRM NORA.
//
// Todavía no se consume desde ningún componente: este archivo es solo la base
// técnica (4.1-A). El cableado al board ocurre en subetapas posteriores.

/**
 * Estados que el flujo NORA usa hoy. Subconjunto del enum `LeadStatus` del
 * backend (NEW | CONTACTED | NEGOTIATION | CLOSED | LOST | CLIENT).
 * Hoy el board solo expone NEW y CONTACTED; CLIENT ya existe en el flujo
 * actual (lo usa el backend y la vista de Clientes) y se incluye para futura
 * reutilización en NORA.
 */
export type NoraLeadStatus = "NEW" | "CONTACTED" | "CLIENT";

export interface NoraLeadStatusMeta {
    /** Valor crudo, tal cual lo guarda/serializa el backend. */
    value: NoraLeadStatus;
    /** Texto visible en la UI NORA (es-AR). */
    label: string;
}

/**
 * Labels visuales por estado. Fuente única de presentación para el CRM NORA.
 * Los labels acompañan la terminología que el board ya muestra hoy
 * ("Nuevos" / "Contactados").
 */
export const NORA_LEAD_STATUS: Record<NoraLeadStatus, NoraLeadStatusMeta> = {
    NEW: { value: "NEW", label: "Nuevo" },
    CONTACTED: { value: "CONTACTED", label: "Contactado" },
    CLIENT: { value: "CLIENT", label: "Cliente" },
};

/** Orden de las pestañas/columnas que el board NORA expone hoy. */
export const NORA_ACTIVE_STATUSES: NoraLeadStatus[] = ["NEW", "CONTACTED"];

/** Devuelve el label de un estado; si no está mapeado, retorna el valor crudo. */
export function getNoraLeadStatusLabel(status: string): string {
    return (NORA_LEAD_STATUS as Record<string, NoraLeadStatusMeta>)[status]?.label ?? status;
}

// --- Estados futuros (NO usar todavía como funcionalidad real) --------------
// El enum `LeadStatus` del backend también define: NEGOTIATION, CLOSED, LOST.
// NORA aún no los usa. El pipeline B2C dedicado (p. ej. WAITLIST / IN_CONVERSATION
// / CONVERTED / DISCARDED) se definirá en una etapa futura que SÍ requiere
// trabajo de backend + migración. Hasta entonces, no se referencian acá.
