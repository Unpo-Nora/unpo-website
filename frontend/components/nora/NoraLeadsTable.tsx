// Etapa 4.2-A.2 — Tabla base (desktop) del Panel de Ventas NORA.
//
// Componente PRESENTACIONAL: recibe los leads ya cargados y solo los renderiza.
// No fetchea, no modifica datos, no usa AuthContext ni llama APIs. Filtros,
// ordenamiento, paginación, cards mobile y acciones reales llegan en subetapas
// posteriores (4.2-A.3+). La columna "Acciones" es un placeholder deshabilitado.

import React from 'react';
import type { NoraLead } from './types';
import NoraStatusBadge from './NoraStatusBadge';

interface NoraLeadsTableProps {
    leads: NoraLead[];
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

export default function NoraLeadsTable({ leads }: NoraLeadsTableProps) {
    return (
        <div className="overflow-x-auto">
            <table className="w-full text-left">
                <thead className="bg-slate-50/50 text-slate-500 text-[11px] uppercase tracking-widest font-black">
                    <tr>
                        <th className="px-6 py-5">Prospecto</th>
                        <th className="px-6 py-5">Interés</th>
                        <th className="px-6 py-5">Estado</th>
                        <th className="px-6 py-5">Asignado</th>
                        <th className="px-6 py-5">Canal</th>
                        <th className="px-6 py-5">Ingreso</th>
                        <th className="px-6 py-5">Último contacto</th>
                        <th className="px-6 py-5">Notas</th>
                        <th className="px-6 py-5 text-right">Acciones</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                    {leads.map((lead) => (
                        <tr key={lead.id} className="hover:bg-slate-50/80 transition-colors">
                            {/* Prospecto */}
                            <td className="px-6 py-5">
                                <div className="font-bold text-slate-900">{lead.full_name}</div>
                                <div className="text-sm text-slate-500 mt-1 flex flex-wrap items-center gap-x-2">
                                    <span>{lead.phone}</span>
                                    {lead.email && <span className="text-slate-300">|</span>}
                                    <span className="text-slate-400">{lead.email}</span>
                                </div>
                            </td>
                            {/* Interés */}
                            <td className="px-6 py-5">
                                <span className="text-sm font-bold text-slate-700 bg-slate-100 px-3 py-1 rounded-lg inline-block">
                                    {lead.product_interest || 'General'}
                                </span>
                            </td>
                            {/* Estado */}
                            <td className="px-6 py-5">
                                <NoraStatusBadge status={lead.status} />
                            </td>
                            {/* Asignado */}
                            <td className="px-6 py-5">
                                <span className="text-sm text-slate-600">
                                    {lead.seller ? lead.seller.split('@')[0] : 'Sin asignar'}
                                </span>
                            </td>
                            {/* Canal */}
                            <td className="px-6 py-5">
                                <span className="text-sm font-medium text-slate-600">{formatChannel(lead.source)}</span>
                            </td>
                            {/* Ingreso */}
                            <td className="px-6 py-5">
                                <span className="text-sm font-bold text-slate-700">
                                    {formatDate(lead.lead_date || lead.created_at)}
                                </span>
                            </td>
                            {/* Último contacto */}
                            <td className="px-6 py-5">
                                <span className="text-sm text-slate-600">{formatDate(lead.contacted_at)}</span>
                            </td>
                            {/* Notas */}
                            <td className="px-6 py-5">
                                <span
                                    className="text-[13px] text-slate-500 italic max-w-[220px] truncate block"
                                    title={lead.notes || undefined}
                                >
                                    {lead.notes || '—'}
                                </span>
                            </td>
                            {/* Acciones (placeholder) */}
                            <td className="px-6 py-5 text-right">
                                <button
                                    type="button"
                                    disabled
                                    className="px-4 py-2 text-xs font-bold rounded-xl bg-slate-100 text-slate-400 cursor-not-allowed"
                                    title="Disponible en una próxima subetapa"
                                >
                                    Próximamente
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
