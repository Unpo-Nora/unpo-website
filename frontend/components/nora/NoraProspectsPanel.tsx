"use client";

// Etapa 4.3 — Panel principal de Prospectos NORA (estilo Clienty).
//
// Reconvierte el CRM NORA a un ÚNICO panel comercial de prospectos. Elimina el
// concepto de "waitlist" y deja de hablar de "Panel de Ventas": el eje es
// Prospectos. Orquesta carga + filtros (búsqueda, estado, asignado, canal, rango
// de fechas) + orden + paginación + ficha lateral + acciones (WhatsApp deep link,
// cambio de estado básico).
//
// Datos: vía fetchNoraLeads (wrapper que fuerza brand=nora + filtro defensivo por
// los sources NORA: WEB_NORA / FACEBOOK_NORA / INSTAGRAM_NORA). Cambios de estado
// vía updateNoraLeadStatus (PATCH /leads/{id}). NO toca backend, DB ni WhatsApp
// Business API. NO copia nada del Panel de Ventas UNPO (SellerDashboard).

import React, { useEffect, useMemo, useState } from 'react';
import { Users, ChevronLeft, ChevronRight } from 'lucide-react';
import type { NoraLead } from './types';
import { useAuth } from '@/context/AuthContext';
import { fetchNoraLeads, updateNoraLeadStatus, type NoraLeadUpdate } from '@/lib/nora/api';
import { timeOf, normalizeArPhone, buildNoraMessage, channelLabel } from '@/lib/nora/format';
import NoraProspectsToolbar, {
    NoraProspectFilters,
    NORA_PROSPECT_DEFAULT_FILTERS,
    NoraSortKey,
    NoraSortDir,
    NORA_PROSPECT_DEFAULT_SORT_KEY,
    NORA_PROSPECT_DEFAULT_SORT_DIR,
    NoraChannelOption,
} from './NoraProspectsToolbar';
import NoraProspectsTable from './NoraProspectsTable';
import NoraProspectDrawer from './NoraProspectDrawer';

/** Cantidad de prospectos por página (paginación client-side). */
const PAGE_SIZE = 12;

/** Orden lógico del pipeline para el sort por estado. */
const STATUS_ORDER: Record<string, number> = { NEW: 0, CONTACTED: 1, CLIENT: 2 };

/**
 * Canales de adquisición conocidos de NORA. Se muestran SIEMPRE en el filtro para
 * dejar la UI lista. Los `value` coinciden con los sources reales que emite el
 * backend (webhook Meta Lead Ads NORA), de modo que el filtro por canal matchea.
 */
const KNOWN_CHANNELS: NoraChannelOption[] = [
    { value: 'WEB_NORA', label: 'Web NORA' },
    { value: 'FACEBOOK_NORA', label: 'Facebook' },
    { value: 'INSTAGRAM_NORA', label: 'Instagram' },
];

export default function NoraProspectsPanel() {
    const { user } = useAuth();
    const [leads, setLeads] = useState<NoraLead[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);
    const [filters, setFilters] = useState<NoraProspectFilters>(NORA_PROSPECT_DEFAULT_FILTERS);
    const [sortKey, setSortKey] = useState<NoraSortKey>(NORA_PROSPECT_DEFAULT_SORT_KEY);
    const [sortDir, setSortDir] = useState<NoraSortDir>(NORA_PROSPECT_DEFAULT_SORT_DIR);
    const [updatingLeadId, setUpdatingLeadId] = useState<number | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);
    const [currentPage, setCurrentPage] = useState(1);
    const [selectedLeadId, setSelectedLeadId] = useState<number | null>(null);

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
                console.error('Error fetching NORA prospects:', err);
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

    // Reset a página 1 cuando cambian filtros u ordenamiento.
    useEffect(() => {
        setCurrentPage(1);
    }, [filters, sortKey, sortDir]);

    const totalCount = leads.length;

    // Opciones dinámicas de asignado.
    const sellerOptions = useMemo(
        () =>
            Array.from(new Set(leads.map((l) => l.seller).filter((s): s is string => Boolean(s)))).sort(),
        [leads]
    );

    // Canales: conocidos (siempre) + los realmente presentes en los datos.
    const channelOptions = useMemo<NoraChannelOption[]>(() => {
        const map = new Map<string, NoraChannelOption>();
        KNOWN_CHANNELS.forEach((c) => map.set(c.value, c));
        leads.forEach((l) => {
            if (l.source && !map.has(l.source)) {
                map.set(l.source, { value: l.source, label: channelLabel(l.source, l.platform) });
            }
        });
        return Array.from(map.values());
    }, [leads]);

    const isDirty =
        JSON.stringify(filters) !== JSON.stringify(NORA_PROSPECT_DEFAULT_FILTERS) ||
        sortKey !== NORA_PROSPECT_DEFAULT_SORT_KEY ||
        sortDir !== NORA_PROSPECT_DEFAULT_SORT_DIR;

    // Filtrado client-side.
    const filteredLeads = useMemo(() => {
        const term = filters.search.trim().toLowerCase();
        const fromT = filters.dateFrom ? new Date(`${filters.dateFrom}T00:00:00`).getTime() : null;
        const toT = filters.dateTo ? new Date(`${filters.dateTo}T23:59:59`).getTime() : null;

        return leads.filter((l) => {
            if (filters.status !== 'ALL' && l.status !== filters.status) return false;

            if (filters.seller === 'UNASSIGNED') {
                if (l.seller) return false;
            } else if (filters.seller !== 'ALL') {
                if (l.seller !== filters.seller) return false;
            }

            if (filters.channel !== 'ALL' && l.source !== filters.channel) return false;

            // Rango de fechas sobre el ingreso (lead_date || created_at).
            if (fromT !== null || toT !== null) {
                const t = timeOf(l.lead_date || l.created_at);
                if (t === null) return false;
                if (fromT !== null && t < fromT) return false;
                if (toT !== null && t > toT) return false;
            }

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
                    return (
                        (a.full_name || '').localeCompare(b.full_name || '', 'es', { sensitivity: 'base' }) *
                        dirMul
                    );
                case 'ultimo_contacto': {
                    const ta = timeOf(a.contacted_at);
                    const tb = timeOf(b.contacted_at);
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

    const handleFilterChange = (next: Partial<NoraProspectFilters>) =>
        setFilters((prev) => ({ ...prev, ...next }));

    const handleClearFilters = () => {
        setFilters(NORA_PROSPECT_DEFAULT_FILTERS);
        setSortKey(NORA_PROSPECT_DEFAULT_SORT_KEY);
        setSortDir(NORA_PROSPECT_DEFAULT_SORT_DIR);
    };

    const handleSortChange = (key: NoraSortKey, dir: NoraSortDir) => {
        setSortKey(key);
        setSortDir(dir);
    };

    /**
     * Aplica un cambio vía el endpoint existente (PATCH /leads/{id}) y refleja el
     * cambio en el estado local sin recargar. Loading por prospecto + error simple.
     */
    const applyUpdate = async (lead: NoraLead, payload: NoraLeadUpdate, optimistic: Partial<NoraLead>) => {
        if (updatingLeadId !== null) return;
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
            console.error('Error updating NORA prospect:', err);
            setActionError('Ocurrió un error al actualizar el prospecto.');
        } finally {
            setUpdatingLeadId(null);
        }
    };

    /** Cambio de estado básico. Mantiene la lógica de asignación coherente. */
    const handleStatusChange = async (lead: NoraLead, status: string) => {
        if (!status || status === lead.status) return;
        if (status === 'CONTACTED') {
            const seller = lead.seller ?? user?.email ?? null;
            await applyUpdate(lead, { status: 'CONTACTED', seller }, { status: 'CONTACTED', seller });
        } else if (status === 'NEW') {
            await applyUpdate(
                lead,
                { status: 'NEW', seller: null, feedback_status: null },
                { status: 'NEW', seller: null, feedback_status: null }
            );
        } else {
            await applyUpdate(lead, { status }, { status });
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

        // Marca automática a contactado sólo si está NEW.
        if (lead.status === 'NEW') {
            const seller = user?.email ?? null;
            await applyUpdate(lead, { status: 'CONTACTED', seller }, { status: 'CONTACTED', seller });
        }
    };

    // Paginación client-side, SIEMPRE después del ordenamiento.
    const totalPages = Math.max(1, Math.ceil(sortedLeads.length / PAGE_SIZE));
    const safePage = Math.min(currentPage, totalPages);
    const startIndex = (safePage - 1) * PAGE_SIZE;
    const endIndex = Math.min(startIndex + PAGE_SIZE, sortedLeads.length);
    const paginatedLeads = useMemo(
        () => sortedLeads.slice(startIndex, endIndex),
        [sortedLeads, startIndex, endIndex]
    );

    const goPrev = () => setCurrentPage(Math.max(1, safePage - 1));
    const goNext = () => setCurrentPage(Math.min(totalPages, safePage + 1));

    const selectedLead = useMemo(
        () => leads.find((l) => l.id === selectedLeadId) ?? null,
        [leads, selectedLeadId]
    );

    const hasLeads = !loading && !error && leads.length > 0;

    return (
        <div className="space-y-6">
            {/* Header: eje = Prospectos + contador total */}
            <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-xl bg-slate-900 text-white flex items-center justify-center shrink-0">
                    <Users size={22} />
                </div>
                <div>
                    <h1 className="text-3xl font-serif font-medium text-slate-900 flex items-center gap-3">
                        Prospectos
                        {!loading && !error && (
                            <span className="text-sm font-bold text-slate-500 bg-slate-100 border border-slate-200 rounded-full px-3 py-1">
                                {totalCount}
                            </span>
                        )}
                    </h1>
                </div>
            </div>

            {/* Toolbar + contador de resultados */}
            {hasLeads && (
                <div className="space-y-2">
                    <NoraProspectsToolbar
                        filters={filters}
                        onChange={handleFilterChange}
                        onClear={handleClearFilters}
                        sellerOptions={sellerOptions}
                        channelOptions={channelOptions}
                        sortKey={sortKey}
                        sortDir={sortDir}
                        onSortChange={handleSortChange}
                        isDirty={isDirty}
                    />
                    {sortedLeads.length > 0 && (
                        <div className="text-xs font-bold text-slate-400 px-1">
                            Mostrando {startIndex + 1}-{endIndex} de {sortedLeads.length} prospecto
                            {sortedLeads.length === 1 ? '' : 's'}
                            {sortedLeads.length !== totalCount ? ` (filtrados de ${totalCount})` : ''}
                        </div>
                    )}
                </div>
            )}

            {/* Error de acción */}
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
                ) : sortedLeads.length === 0 ? (
                    <div className="text-center py-20 text-slate-400 font-medium">
                        No hay prospectos que coincidan con los filtros seleccionados.
                    </div>
                ) : (
                    <>
                        <NoraProspectsTable
                            leads={paginatedLeads}
                            onWhatsApp={handleWhatsApp}
                            onOpenDetail={(lead) => setSelectedLeadId(lead.id)}
                            onStatusChange={handleStatusChange}
                            updatingLeadId={updatingLeadId}
                        />

                        {totalPages > 1 && (
                            <div className="px-6 py-5 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between gap-3">
                                <button
                                    type="button"
                                    onClick={goPrev}
                                    disabled={safePage === 1}
                                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-bold rounded-xl border border-slate-200 text-slate-600 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                                >
                                    <ChevronLeft size={18} />
                                    Anterior
                                </button>
                                <div className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                                    Página {safePage} de {totalPages}
                                </div>
                                <button
                                    type="button"
                                    onClick={goNext}
                                    disabled={safePage === totalPages}
                                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-bold rounded-xl border border-slate-200 text-slate-600 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                                >
                                    Siguiente
                                    <ChevronRight size={18} />
                                </button>
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* Ficha/detalle del prospecto */}
            <NoraProspectDrawer
                lead={selectedLead}
                onClose={() => setSelectedLeadId(null)}
                onWhatsApp={handleWhatsApp}
                onStatusChange={handleStatusChange}
                updating={selectedLead ? updatingLeadId === selectedLead.id : false}
            />
        </div>
    );
}
