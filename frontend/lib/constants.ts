/**
 * Datos de negocio que antes estaban hardcodeados dentro de componentes.
 * Regla de marcas (ver CLAUDE.md): los leads NORA van SOLO al vendedor NORA y
 * los UNPO solo a vendedores UNPO — no mezclar estos números.
 */

/** Vendedor dedicado NORA (formato wa.me, con 549). */
export const NORA_SELLER_PHONE = '5491131488378';

/** Fallback UNPO si el backend no asignó vendedor (sin prefijo; se antepone 549 al armar el link). */
export const UNPO_FALLBACK_SELLER_PHONE = '1144227969';
