// Etapa 4.3 — Helpers de presentación compartidos por el panel de Prospectos NORA.
//
// Solo formato/strings/derivaciones: SIN fetch, SIN estado, SIN APIs y SIN tocar
// backend. Centraliza el formateo de fechas, el etiquetado de canal de adquisición,
// la normalización de teléfono para wa.me y el mensaje inicial de WhatsApp (deep
// link, NO WhatsApp Business API). Lo consumen el panel, la tabla y el drawer.

import type { NoraLead } from '@/components/nora/types';

/** Fecha en formato argentino simple; "—" si falta o es inválida. */
export function formatDate(value?: string | null): string {
    if (!value) return '—';
    const d = new Date(value);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleDateString('es-AR');
}

/** Fecha + hora corta (es-AR); "—" si falta o es inválida. */
export function formatDateTime(value?: string | null): string {
    if (!value) return '—';
    const d = new Date(value);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' });
}

/** Epoch en ms de una fecha; null si falta o es inválida. */
export function timeOf(value?: string | null): number | null {
    if (!value) return null;
    const t = new Date(value).getTime();
    return isNaN(t) ? null : t;
}

/**
 * Etiqueta legible del canal de adquisición a partir de source/platform.
 * Mapea los canales NORA conocidos (Facebook / Instagram / Web NORA) y deja
 * listo el soporte para futuros canales. No inventa datos: si no reconoce el
 * valor, devuelve el crudo (o "—" si está vacío).
 */
export function channelLabel(source?: string | null, platform?: string | null): string {
    const raw = `${source ?? ''} ${platform ?? ''}`.toUpperCase();
    if (!raw.trim()) return '—';
    if (raw.includes('WEB_NORA')) return 'Web NORA';
    if (raw.includes('INSTAGRAM') || /\bIG\b/.test(raw)) return 'Instagram';
    if (raw.includes('FACEBOOK') || raw.includes('META') || /\bFB\b/.test(raw)) return 'Facebook';
    return source || platform || '—';
}

/**
 * Normaliza un teléfono a formato wa.me para Argentina.
 * Quita todo lo no numérico; saca el 0 inicial; asegura el 9 de celular y el
 * código país 54. Devuelve null si está vacío o queda demasiado corto.
 */
export function normalizeArPhone(raw?: string | null): string | null {
    if (!raw) return null;
    let phone = raw.replace(/\D/g, '');
    if (!phone) return null;

    if (phone.startsWith('0')) phone = phone.slice(1);

    if (phone.startsWith('54')) {
        let rest = phone.slice(2);
        if (!rest.startsWith('9')) rest = '9' + rest;
        phone = '54' + rest;
    } else {
        phone = '549' + phone;
    }

    if (phone.length < 12) return null;
    return phone;
}

/** Mensaje inicial propio de NORA (B2C). Sin nada de UNPO ni de "waitlist". */
export function buildNoraMessage(lead: NoraLead): string {
    const greeting = lead.full_name ? `Hola ${lead.full_name}, ¿cómo estás?` : 'Hola, ¿cómo estás?';
    const interest = lead.product_interest?.trim();
    if (interest) {
        return `${greeting} Te escribo de NORA por tu consulta sobre ${interest}.`;
    }
    return `${greeting} Te escribo de NORA por tu consulta.`;
}
