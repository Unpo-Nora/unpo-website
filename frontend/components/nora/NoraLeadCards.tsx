// Etapa 4.2-A.6 — Cards mobile/tablet del Panel de Ventas NORA.
//
// Componente PRESENTACIONAL: equivalente mobile de NoraLeadsTable. Recibe los
// leads ya cargados/filtrados/ordenados/paginados y los renderiza como cards.
// No fetchea, no modifica datos, no usa AuthContext ni llama APIs: las acciones
// se delegan al panel vía callbacks (onWhatsApp / onRevertToNew) y el panel
// maneja el loading por lead (updatingLeadId). Estética NORA/slate.

import React from 'react';
import { MessageCircle, RotateCcw } from 'lucide-react';
import type { NoraLead } from './types';
import NoraStatusBadge from './NoraStatusBadge';

interface NoraLeadCardsProps {
    leads: NoraLead[];
    /** Abre WhatsApp y (si corresponde) marca el lead como contactado. */
    onWhatsApp: (lead: NoraLead) => void;
    /** Devuelve un lead CONTACTED al estado NEW. */
    onRevertToNew: (lead: NoraLead) => void;
    /** Id del lead que está actualizándose (deshabilita sus acciones). */
    updatingLeadId: number | null;
}

/** Fecha en formato argentino simple; "—" si falta o es inválida. */
function formatDate(value?: string | null): string {
    if (!value) return '—';
    const d = new Date(value);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleDateString('es-AR');
}

/** Etiqueta legible del canal de adquisición. */
function formatChannel(source: string): string {
    if (source === 'WEB_NORA') return 'Web NORA';
    return source || '—';
}

export default function NoraLeadCards({
    leads,
    onWhatsApp,
    onRevertToNew,
    updatingLeadId,
}: NoraLeadCardsProps) {
    return (
        <div className="p-4 sm:p-6 bg-slate-50/50 grid grid-cols-1 md:grid-cols-2 gap-4">
            {leads.map((lead) => {
                const isUpdating = updatingLeadId === lead.id;
                const hasPhone = Boolean(lead.phone && lead.phone.trim());
                return (
                    <div
                        key={lead.id}
                        className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col"
                    >
                        {/* Header */}
                        <div className="p-4 border-b border-slate-100 flex justify-between items-start gap-2">
                            <div className="min-w-0">
                                <h3 className="font-bold text-slate-900 text-lg leading-tight truncate">{lead.full_name}</h3>
                                <div className="text-sm text-slate-500 mt-1">{lead.phone || '—'}</div>
                                {lead.email && <div className="text-xs text-slate-400 mt-0.5 truncate">{lead.email}</div>}
                            </div>
                            <div className="shrink-0">
                                <NoraStatusBadge status={lead.status} />
                            </div>
                        </div>

                        {/* Body */}
                        <div className="p-4 flex flex-col gap-3">
                            <div>
                                <span className="text-sm font-bold text-slate-700 bg-slate-100 px-3 py-1 rounded-lg inline-block">
                                    {lead.product_interest || 'General'}
                                </span>
                            </div>

                            <dl className="grid grid-cols-2 gap-x-3 gap-y-2">
                                <Field label="Asignado" value={lead.seller ? lead.seller.split('@')[0] : 'Sin asignar'} />
                                <Field label="Canal" value={formatChannel(lead.source)} />
                                <Field label="Ingreso" value={formatDate(lead.lead_date || lead.created_at)} />
                                <Field label="Último contacto" value={formatDate(lead.contacted_at)} />
                            </dl>

                            <div>
                                <div className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-1">Notas</div>
                                <p className="text-[13px] text-slate-500 italic" title={lead.notes || undefined}>
                                    {lead.notes || '—'}
                                </p>
                            </div>

                            {/* Acciones */}
                            <div className="flex items-center gap-2 pt-1">
                                <button
                                    type="button"
                                    onClick={() => onWhatsApp(lead)}
                                    disabled={!hasPhone || isUpdating}
                                    className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-bold rounded-xl bg-slate-900 hover:bg-slate-800 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                                    title={hasPhone ? 'Contactar por WhatsApp' : 'Sin teléfono válido'}
                                >
                                    <MessageCircle size={16} />
                                    WhatsApp
                                </button>
                                {lead.status === 'CONTACTED' && (
                                    <button
                                        type="button"
                                        onClick={() => onRevertToNew(lead)}
                                        disabled={isUpdating}
                                        className="inline-flex items-center justify-center gap-2 px-3 py-2.5 text-sm font-bold rounded-xl bg-slate-100 text-slate-500 hover:bg-slate-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                                        title="Volver a Nuevo"
                                    >
                                        <RotateCcw size={15} />
                                        Volver a Nuevo
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

interface FieldProps {
    label: string;
    value: string;
}

function Field({ label, value }: FieldProps) {
    return (
        <div className="min-w-0">
            <div className="text-[10px] font-black uppercase tracking-widest text-slate-400">{label}</div>
            <div className="text-sm text-slate-600 truncate">{value}</div>
        </div>
    );
}
