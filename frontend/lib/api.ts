/**
 * Cliente API compartido de todo el frontend.
 *
 * - `API_URL`: única fuente de la URL del backend (antes el literal estaba
 *   repetido en ~70 call-sites).
 * - `authHeaders()`: header Authorization desde el token de localStorage.
 * - `apiFetch()`: fetch autenticado contra el backend. Ante un 401 dispara el
 *   handler global registrado por AuthContext (sesión expirada → logout),
 *   y devuelve la Response para que cada pantalla siga su flujo.
 *
 * Los endpoints públicos (login, formularios de leads, catálogo) NO deben usar
 * `apiFetch` — usan `fetch` con `API_URL` directamente, porque sus 401 son parte
 * del flujo normal (p. ej. contraseña incorrecta) y no deben cerrar la sesión.
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return window.localStorage.getItem('token');
}

export function authHeaders(extra?: Record<string, string>): Record<string, string> {
    const token = getToken();
    return {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(extra ?? {}),
    };
}

let onUnauthorized: (() => void) | null = null;

/** Lo registra AuthContext al montar; se invoca cuando un apiFetch recibe 401. */
export function setOnUnauthorized(handler: (() => void) | null) {
    onUnauthorized = handler;
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = { ...authHeaders(), ...((init.headers as Record<string, string>) ?? {}) };
    const response = await fetch(`${API_URL}${path}`, { ...init, headers });
    if (response.status === 401 && onUnauthorized) {
        onUnauthorized();
    }
    return response;
}
