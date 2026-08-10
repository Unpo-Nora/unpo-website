/**
 * Formateadores compartidos (es-AR). Antes convivían 4 formatos de moneda
 * incompatibles (con locale del navegador, con Intl currency, sin locale) y
 * ~25 `toLocaleDateString` inline.
 */

/**
 * ARS (default): "$1.234.567" — sin decimales, separador de miles es-AR.
 * USD: "US$1.234,56" — hasta 2 decimales, para montos chicos en dólares.
 */
export function formatCurrency(value: number | null | undefined, currency: string = 'ARS'): string {
    const n = Number(value);
    const prefix = currency === 'USD' ? 'US$' : '$';
    if (value == null || isNaN(n)) return `${prefix}0`;
    const maxDecimals = currency === 'USD' ? 2 : 0;
    return `${prefix}${n.toLocaleString('es-AR', { maximumFractionDigits: maxDecimals })}`;
}

/** "dd/mm/aaaa" es-AR; '—' si la fecha falta o es inválida. */
export function formatDate(value: string | Date | null | undefined): string {
    if (!value) return '—';
    const d = new Date(value);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleDateString('es-AR');
}
