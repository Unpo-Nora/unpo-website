"use client";

// Etapa 4.2-A.5 — Panel de Ventas NORA: carga + métricas + filtros + orden +
// acciones básicas (WhatsApp etapa 1).
//
// Carga los leads NORA reales vía fetchNoraLeads (wrapper centralizado que ya
// fuerza brand=nora + filtro defensivo source === "WEB_NORA"), aplica filtros y
// ordenamiento client-side y permite acciones por prospecto:
//   - Contactar por WhatsApp con deep-link wa.me (NO WhatsApp Business API).
//   - Marcado automático a CONTACTED cuando el lead está en NEW.
//   - Volver un lead CONTACTED a NEW.
// Los cambios de estado usan el endpoint existente (PATCH /leads/{id}) vía
// updateNoraLeadStatus; no se crea backend nuevo ni se toca la DB.
//
// TODAVÍA NO incluye: rango de fechas, paginación, ficha/drawer ni cards mobile
// (subetapas 4.2-A.6+). No toca CLIENT, no crea estados nuevos, no usa WhatsApp
// Business API / Meta API y no copia NADA del Panel de Ventas UNPO
// (SellerDashboard).

import React, { useEffect, useMemo, useState } from 'react';
import { Users, UserPlus, History } from 'lucide-react';
import type { NoraLead } from './types';
import { useAuth } from '@/context/AuthContext';
import { fetchNoraLeads, updateNoraLeadStatus, type NoraLeadUpdate } from '@/lib/nora/api';
import NoraLeadsTable from './NoraLeadsTable';
import NoraSalesToolbar, {
    NoraSalesFilters,
    NORA_DEFAULT_FILTERS,
    NoraSortKey,
    NoraSortDir,
    NORA_DEFAULT_SORT_KEY,
    NORA_DEFAULT_SORT_DIR,
} from './NoraSalesToolbar';

/** Orden lógico del pipeline para el sort por estado. */
const STATUS_ORDER: Record<string, number> = { NEW: 0, CONTACTED: 1, CLIENT: 2 };

/** Epoch en ms de una fecha; null si falta o es inválida. */
function timeOf(value?: string | null): number | null {
    if (!value) return null;
    const t = new Date(value).getTime();
    return isNaN(t) ? null : t;
}

/**
 * Normaliza un teléfono a formato wa.me para Argentina.
 * Quita todo lo no numérico; saca el 0 inicial; asegura el 9 de celular y el
 * código país 54. Devuelve null si está vacío o queda demasiado corto.
 */
function normalizeArPhone(raw?: string | null): string | null {
    if (!raw) return null;
    let phone = raw.replace(/\D/g, ''); // solo dígitos
    if (!phone) return null;

    // quitar 0 inicial de código de área nacional (ej 011 -> 11)
    if (phone.startsWith('0')) phone = phone.slice(1);

    if (phone.startsWith('54')) {
        let rest = phone.slice(2);
        if (!rest.startsWith('9')) rest = '9' + rest; // celular AR
        phone = '54' + rest;
    } else {
        phone = '549' + phone; // sin código país: asumir AR celular
    }

    // validación mínima de longitud (54 + 9 + área/número)
    if (phone.length < 12) return null;
    return phone;
}

/** Mensaje inicial propio de NORA (B2C). Sin nada de UNPO. */
function buildNoraMessage(lead: NoraLead): string {
    const greeting = lead.full_name ? `Hola ${lead.full_name}, ¿cómo estás?` : 'Hola, ¿cómo estás?';
    const interest = lead.product_interest?.trim();
    if (interest) {
        return `${greeting} Te escribo de NORA por tu consulta sobre ${interest}.`;
    }
    return `${greeting} Te escribo de NORA por tu consulta sobre nuestras mesas inteligentes.`;
}

export default function NoraSalesPanel() {
    const { user } = useAuth();
    const [leads, setLeads] = useState<NoraLead[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);
    const [filters, setFilters] = useState<NoraSalesFilters>(NORA_DEFAULT_FILTERS);
    const [sortKey, setSortKey] = useState<NoraSortKey>(NORA_DEFAULT_SORT_KEY);
    const [sortDir, setSortDir] = useState<NoraSortDir>(NORA_DEFAULT_SORT_DIR);
    const [updatingLeadId, setUpdatingLeadId] = useState<number | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        const load = async () => {
            setLoading(true);
            setError(false);
            try {
                const token = localStorage.getItem('token') ?? '';
                const data = await fetchNoraLeads(token);
                if (!cancelled) setLeads(data);
            } catch (err) {
                console.error('Error fetching NORA leads:', err);
                if (!cancelled) setError(true);
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        load();
        return () => {
            cancelled = true;
        };
    }, []);

    // Métricas: SIEMPRE sobre el total real de leads cargados (no filtrados).
    const totalCount = leads.length;
    const newCount = leads.filter((l) => l.status === 'NEW').length;
    const contactedCount = leads.filter((l) => l.status === 'CONTACTED').length;

    // Opciones dinámicas derivadas de los leads cargados.
    const sellerOptions = useMemo(
        () =>
            Array.from(
                new Set(leads.map((l) => l.seller).filter((s): s is string => Boolean(s)))
            ).sort(),
        [leads]
    );

    const channelOptions = useMemo(
        () => Array.from(new Set(leads.map((l) => l.source).filter(Boolean))).sort(),
        [leads]
    );

    // Filtrado client-side.
    const filteredLeads = useMemo(() => {
        const term = filters.search.trim().toLowerCase();
        return leads.filter((l) => {
            // Estado
            if (filters.status !== 'ALL' && l.status !== filters.status) return false;

            // Asignado
            if (filters.seller === 'UNASSIGNED') {
                if (l.seller) return false;
            } else if (filters.seller !== 'ALL') {
                if (l.seller !== filters.seller) return false;
            }

            // Canal
            if (filters.channel !== 'ALL' && l.source !== filters.channel) return false;

            // Buscador libre
            if (term) {
                const haystack = [l.full_name, l.email, l.phone, l.product_interest, l.notes]
                    .filter(Boolean)
                    .join(' ')
                    .toLowerCase();
                if (!haystack.includes(term)) return false;
            }

            return true;
        });
    }, [leads, filters]);

    // Ordenamiento client-side, SIEMPRE después del filtrado.
    const sortedLeads = useMemo(() => {
        const dirMul = sortDir === 'asc' ? 1 : -1;
        const arr = [...filteredLeads];

        arr.sort((a, b) => {
            switch (sortKey) {
                case 'nombre':
                    return (a.full_name || '').localeCompare(b.full_name || '', 'es', { sensitivity: 'base' }) * dirMul;

                case 'ultimo_contacto': {
                    const ta = timeOf(a.contacted_at);
                    const tb = timeOf(b.contacted_at);
                    // Nulos SIEMPRE al final, sin importar la dirección.
                    if (ta === null && tb === null) return 0;
                    if (ta === null) return 1;
                    if (tb === null) return -1;
                    return (ta - tb) * dirMul;
                }

                case 'estado': {
                    const ra = STATUS_ORDER[a.status];
                    const rb = STATUS_ORDER[b.status];
                    const aKnown = ra !== undefined;
                    const bKnown = rb !== undefined;
                    // Estados desconocidos SIEMPRE al final, sin importar la dirección.
                    if (!aKnown && !bKnown) return 0;
                    if (!aKnown) return 1;
                    if (!bKnown) return -1;
                    return (ra - rb) * dirMul;
                }

                case 'ingreso':
                default: {
                    const ta = timeOf(a.lead_date || a.created_at);
                    const tb = timeOf(b.lead_date || b.created_at);
                    if (ta === null && tb === null) return 0;
                    if (ta === null) return 1;
                    if (tb === null) return -1;
                    return (ta - tb) * dirMul;
                }
            }
        });

        return arr;
    }, [filteredLeads, sortKey, sortDir]);

    const handleFilterChange = (next: Partial<NoraSalesFilters>) =>
        setFilters((prev) => ({ ...prev, ...next }));

    const handleClearFilters = () => setFilters(NORA_DEFAULT_FILTERS);

    const handleSortChange = (key: NoraSortKey, dir: NoraSortDir) => {
        setSortKey(key);
        setSortDir(dir);
    };

    /**
     * Aplica un cambio de estado vía el endpoint existente (PATCH /leads/{id})
     * y refleja el cambio en el estado local sin recargar. Maneja loading por
     * lead y error simple. No crea backend nuevo ni toca WhatsApp API.
     */
    const applyStatusUpdate = async (
        lead: NoraLead,
        payload: NoraLeadUpdate,
        optimistic: Partial<NoraLead>
    ) => {
        if (updatingLeadId !== null) return; // evita doble click / acciones simultáneas
        setUpdatingLeadId(lead.id);
        setActionError(null);
        try {
            const token = localStorage.getItem('token') ?? '';
            const ok = await updateNoraLeadStatus(token, lead.id, payload);
            if (ok) {
                setLeads((prev) => prev.map((l) => (l.id === lead.id ? { ...l, ...optimistic } : l)));
            } else {
                setActionError('No se pudo actualizar el prospecto. Intentá nuevamente.');
            }
        } catch (err) {
            console.error('Error updating NORA lead:', err);
            setActionError('Ocurrió un error al actualizar el prospecto.');
        } finally {
            setUpdatingLeadId(null);
        }
    };

    const handleWhatsApp = async (lead: NoraLead) => {
        const phone = normalizeArPhone(lead.phone);
        if (!phone) {
            setActionError(`El teléfono de ${lead.full_name || 'el prospecto'} no es válido o está vacío.`);
            return;
        }
        setActionError(null);

        const url = `https://wa.me/${phone}?text=${encodeURIComponent(buildNoraMessage(lead))}`;
        window.open(url, '_blank', 'noopener,noreferrer');

        // Marcado automático a contactado solo si está NEW. No toca CLIENT.
        if (lead.status === 'NEW') {
            const seller = user?.email ?? null;
            await applyStatusUpdate(
                lead,
                { status: 'CONTACTED', seller },
                { status: 'CONTACTED', seller }
            );
        }
    };

    const handleRevertToNew = async (lead: NoraLead) => {
        await applyStatusUpdate(
            lead,
            { status: 'NEW', seller: null, feedback_status: null },
            { status: 'NEW', seller: null, feedback_status: null }
        );
    };

    const hasLeads = !loading && !error && leads.length > 0;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-serif font-medium text-slate-900">Panel de Ventas NORA</h1>
                <p className="text-slate-500 mt-2">Gestión comercial de prospectos NORA</p>
            </div>

            {/* Métricas */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <MetricCard icon={<Users size={20} />} label="Total de prospectos" value={totalCount} />
                <MetricCard icon={<UserPlus size={20} />} label="Nuevos" value={newCount} />
                <MetricCard icon={<History size={20} />} label="Contactados" value={contactedCount} />
            </div>

            {/* Toolbar de filtros + contador (solo si hay leads reales cargados) */}
            {hasLeads && (
                <div className="space-y-2">
                    <NoraSalesToolbar
                        filters={filters}
                        onChange={handleFilterChange}
                        onClear={handleClearFilters}
                        sellerOptions={sellerOptions}
                        channelOptions={channelOptions}
                        sortKey={sortKey}
                        sortDir={sortDir}
                        onSortChange={handleSortChange}
                    />
                    <div className="text-xs font-bold text-slate-400 px-1">
                        Mostrando {filteredLeads.length} de {leads.length} prospectos
                    </div>
                </div>
            )}

            {/* Error de acción (simple) */}
            {actionError && (
                <div className="bg-rose-50 border border-rose-200 text-rose-600 text-sm font-medium rounded-2xl px-4 py-3">
                    {actionError}
                </div>
            )}

            {/* Contenido */}
            <div className="bg-white rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden">
                {loading ? (
                    <div className="text-center py-20 text-slate-400 font-medium">Cargando prospectos NORA...</div>
                ) : error ? (
                    <div className="text-center py-20 text-rose-500 font-medium">
                        Ocurrió un error al cargar los prospectos. Intentá nuevamente más tarde.
                    </div>
                ) : leads.length === 0 ? (
                    <div className="text-center py-20 text-slate-400 font-medium">Aún no hay prospectos NORA.</div>
                ) : filteredLeads.length === 0 ? (
                    <div className="text-center py-20 text-slate-400 font-medium">
                        No hay prospectos que coincidan con los filtros seleccionados.
                    </div>
                ) : (
                    <NoraLeadsTable
                        leads={sortedLeads}
                        onWhatsApp={handleWhatsApp}
                        onRevertToNew={handleRevertToNew}
                        updatingLeadId={updatingLeadId}
                    />
                )}
            </div>
        </div>
    );
}

interface MetricCardProps {
    icon: React.ReactNode;
    label: string;
    value: number;
}

function MetricCard({ icon, label, value }: MetricCardProps) {
    return (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 flex items-center gap-4">
            <div className="w-11 h-11 rounded-xl bg-slate-100 flex items-center justify-center text-slate-500 shrink-0">
                {icon}
            </div>
            <div>
                <div className="text-2xl font-black text-slate-900 leading-none">{value}</div>
                <div className="text-xs font-bold text-slate-400 uppercase tracking-widest mt-1">{label}</div>
            </div>
        </div>
    );
}
