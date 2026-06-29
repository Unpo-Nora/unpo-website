// Etapa 4.2-A.2 — Badge de estado del Panel de Ventas NORA.
//
// Componente PRESENTACIONAL: recibe un `status` crudo y muestra un label legible
// (es-AR) reutilizando getNoraLeadStatusLabel. Estética NORA (slate / emerald),
// sin branding azul UNPO. No fetchea, no usa AuthContext, no llama APIs.

import React from 'react';
import { getNoraLeadStatusLabel } from './leadStatus';

interface NoraStatusBadgeProps {
    /** Valor crudo del estado tal como lo serializa el backend. */
    status: string;
}

/** Estilos por estado (slate como base NORA; emerald para Cliente/ganado). */
const STATUS_STYLES: Record<string, string> = {
    NEW: 'bg-slate-100 text-slate-600 border-slate-200',
    CONTACTED: 'bg-slate-800 text-white border-slate-800',
    CLIENT: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

export default function NoraStatusBadge({ status }: NoraStatusBadgeProps) {
    const style = STATUS_STYLES[status] ?? 'bg-slate-50 text-slate-400 border-slate-200';
    return (
        <span className={`px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-wide border inline-block ${style}`}>
            {getNoraLeadStatusLabel(status)}
        </span>
    );
}
