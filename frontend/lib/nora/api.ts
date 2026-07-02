// Etapa 4.1-D — Wrapper de datos del CRM NORA (frontend).
//
// Centraliza TODAS las llamadas a leads de NORA para garantizar que siempre se
// consulte con brand=nora y se aplique el filtro defensivo por los sources de la
// marca NORA. Objetivo: que ningún componente NORA vuelva a pegarle a /leads/ "a
// mano" sin el scope de marca.
//
// No toca backend ni cambia endpoints: usa los mismos que ya consumía el board.

import type { NoraLead } from '@/components/nora/types';
import type { NoraLeadStatus } from '@/components/nora/leadStatus';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Sources que pertenecen a la marca NORA: web + Meta Lead Ads (Facebook/Instagram).
 * Debe mantenerse en sincronía con NORA_SOURCES del backend (crud.py).
 */
export const NORA_SOURCES = ['WEB_NORA', 'FACEBOOK_NORA', 'INSTAGRAM_NORA'];

/** Campos que el CRM NORA puede actualizar de un lead. */
export interface NoraLeadUpdate {
    status?: NoraLeadStatus | string;
    seller?: string | null;
    feedback_status?: string | null;
}

function authHeaders(token: string): HeadersInit {
    return { Authorization: `Bearer ${token}` };
}

/**
 * Trae los leads de NORA. SIEMPRE consulta con brand=nora y aplica el filtro
 * defensivo por NORA_SOURCES (defensa en profundidad: el backend ya filtra por
 * brand=nora). Incluye web + Meta Lead Ads (FACEBOOK_NORA / INSTAGRAM_NORA).
 */
export async function fetchNoraLeads(token: string): Promise<NoraLead[]> {
    const response = await fetch(`${API_BASE}/leads/?brand=nora`, {
        headers: authHeaders(token),
    });
    const data = await response.json();
    return (data as NoraLead[]).filter((l) => NORA_SOURCES.includes(l.source));
}

/**
 * Actualiza un lead NORA (estado / seller / feedback) vía PATCH /leads/{id}.
 * Devuelve true si el backend respondió OK. Mismo endpoint que ya usaba el board.
 */
export async function updateNoraLeadStatus(
    token: string,
    leadId: number,
    payload: NoraLeadUpdate
): Promise<boolean> {
    const response = await fetch(`${API_BASE}/leads/${leadId}`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            ...authHeaders(token),
        },
        body: JSON.stringify(payload),
    });
    return response.ok;
}
