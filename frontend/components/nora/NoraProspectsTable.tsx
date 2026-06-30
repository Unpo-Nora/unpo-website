"use client";

// Etapa 4.3 — Tabla principal del panel de Prospectos NORA (estilo Clienty).
//
// Componente PRESENTACIONAL: recibe los prospectos ya cargados/filtrados/ordenados/
// paginados y los renderiza. No fetchea, no usa AuthContext ni llama APIs: las
// acciones se delegan al panel vía callbacks (onWhatsApp / onOpenDetail /
// onStatusChange) y el panel maneja el loading por prospecto (updatingLeadId).
//
// Columnas: Fecha · Contacto · Estado · Etiquetas · Notas · Acciones.
// La fila completa abre la ficha; los controles de acción frenan la propagación.
// "Etiquetas" deriva del canal de adquisición (dato real) y deja lugar para tags
// manuales futuros. Sin WhatsApp Business API: el botón usa deep link wa.me.

import React from 'react';
import { MessageCircle, Eye } from 'lucide-react';
import type { NoraLead } from './types';
import NoraStatusBadge from './NoraStatusBadge';
import { formatDate, channelLabel } from '@/lib/nora/format';

interface NoraProspectsTableProps {
    leads: NoraLead[];
    onWhatsApp: (lead: NoraLead) => void;
    onOpenDetail: (lead: NoraLead) => void;
    onStatusChange: (lead: NoraLead, status: string) => void;
    updatingLeadId: number | null;
}

const ROW_STATUS_SELECT =
    'text-xs font-bold rounded-lg border border-slate-200 bg-white py-1.5 px-2 text-slate-600 focus:ring-2 focus:ring-slate-200 outline-none disabled:opacity-40';

export default function NoraProspectsTable({
    leads,
    onWhatsApp,
    onOpenDetail,
    onStatusChange,
    updatingLeadId,
}: NoraProspectsTableProps) {
    return (
        <div className="overflow-x-auto">
            <table className="w-full text-left">
                <thead className="bg-slate-50/50 text-slate-500 text-[11px] uppercase tracking-widest font-black">
                    <tr>
                        <th className="px-6 py-5">Fecha</th>
                        <th className="px-6 py-5">Contacto</th>
                        <th className="px-6 py-5">Estado</th>
                        <th className="px-6 py-5">Etiquetas</th>
                        <th className="px-6 py-5">Notas</th>
                        <th className="px-6 py-5 text-right">Acciones</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                    {leads.map((lead) => {
                        const isUpdating = updatingLeadId === lead.id;
                        const hasPhone = Boolean(lead.phone && lead.phone.trim());
                        const channel = channelLabel(lead.source, lead.platform);
                        return (
                            <tr
                                key={lead.id}
                                onClick={() => onOpenDetail(lead)}
                                className="hover:bg-slate-50/80 transition-colors cursor-pointer"
                            >
                                {/* Fecha de ingreso */}
                                <td className="px-6 py-5 align-top">
                                    <span className="text-sm font-bold text-slate-700 whitespace-nowrap">
                                        {formatDate(lead.lead_date || lead.created_at)}
                                    </span>
                                </td>

                                {/* Contacto */}
                                <td className="px-6 py-5 align-top">
                                    <div className="font-bold text-slate-900">{lead.full_name || 'Sin nombre'}</div>
                                    <div className="text-sm text-slate-500 mt-1 flex flex-wrap items-center gap-x-2">
                                        {lead.phone && <span>{lead.phone}</span>}
                                        {lead.phone && lead.email && <span className="text-slate-300">|</span>}
                                        {lead.email && <span className="text-slate-400">{lead.email}</span>}
                                    </div>
                                </td>

                                {/* Estado */}
                                <td className="px-6 py-5 align-top">
                                    <NoraStatusBadge status={lead.status} />
                                </td>

                                {/* Etiquetas (derivadas del canal de adquisición) */}
                                <td className="px-6 py-5 align-top">
                                    {channel !== '—' ? (
                                        <span className="inline-flex items-center text-[11px] font-bold uppercase tracking-wide text-slate-600 bg-slate-100 border border-slate-200 px-2.5 py-1 rounded-full">
                                            {channel}
                                        </span>
                                    ) : (
                                        <span className="text-sm text-slate-300">—</span>
                                    )}
                                </td>

                                {/* Notas */}
                                <td className="px-6 py-5 align-top">
                                    <span
                                        className="text-[13px] text-slate-500 italic max-w-[220px] truncate block"
                                        title={lead.notes || undefined}
                                    >
                                        {lead.notes || '—'}
                                    </span>
                                </td>

                                {/* Acciones (frenan la propagación para no abrir la ficha) */}
                                <td className="px-6 py-5 align-top text-right">
                                    <div
                                        className="flex items-center justify-end gap-2"
                                        onClick={(e) => e.stopPropagation()}
                                    >
                                        {/* Cambio de estado básico */}
                                        <select
                                            aria-label="Cambiar estado"
                                            className={ROW_STATUS_SELECT}
                                            value={['NEW', 'CONTACTED', 'CLIENT'].includes(lead.status) ? lead.status : ''}
                                            disabled={isUpdating}
                                            onChange={(e) => onStatusChange(lead, e.target.value)}
                                        >
                                            {!['NEW', 'CONTACTED', 'CLIENT'].includes(lead.status) && (
                                                <option value="" disabled>
                                                    {lead.status}
                                                </option>
                                            )}
                                            <option value="NEW">Nuevo</option>
                                            <option value="CONTACTED">Contactado</option>
                                            <option value="CLIENT">Cliente</option>
                                        </select>

                                        {/* WhatsApp (deep link) */}
                                        <button
                                            type="button"
                                            onClick={() => onWhatsApp(lead)}
                                            disabled={!hasPhone || isUpdating}
                                            className="inline-flex items-center gap-2 px-3 py-2 text-xs font-bold rounded-xl bg-slate-900 hover:bg-slate-800 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                                            title={hasPhone ? 'Contactar por WhatsApp' : 'Sin teléfono válido'}
                                        >
                                            <MessageCircle size={16} />
                                            WhatsApp
                                        </button>

                                        {/* Abrir ficha */}
                                        <button
                                            type="button"
                                            onClick={() => onOpenDetail(lead)}
                                            className="inline-flex items-center gap-2 px-3 py-2 text-xs font-bold rounded-xl bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors"
                                            title="Ver detalle del prospecto"
                                        >
                                            <Eye size={16} />
                                            Detalle
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
