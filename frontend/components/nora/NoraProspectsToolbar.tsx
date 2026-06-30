"use client";

// Etapa 4.3 — Toolbar de filtros del panel de Prospectos NORA (estilo Clienty).
//
// Componente PRESENTACIONAL/controlado: recibe el estado de filtros + orden y los
// callbacks desde NoraProspectsPanel. NO mantiene estado de datos, no fetchea, no
// usa AuthContext y no llama APIs. El filtrado/orden real se aplica client-side en
// el panel. Estética NORA/slate, sin azul UNPO ni lenguaje de "ventas".

import React from 'react';
import { Search, X } from 'lucide-react';

export interface NoraProspectFilters {
    /** Texto libre: matchea full_name / email / phone / product_interest / notes. */
    search: string;
    /** 'ALL' | 'NEW' | 'CONTACTED' | 'CLIENT'. */
    status: string;
    /** 'ALL' | 'UNASSIGNED' | <email de seller>. */
    seller: string;
    /** 'ALL' | <valor de source/canal>. */
    channel: string;
    /** Fecha de ingreso desde (yyyy-mm-dd) o '' si no se filtra. */
    dateFrom: string;
    /** Fecha de ingreso hasta (yyyy-mm-dd) o '' si no se filtra. */
    dateTo: string;
}

/** Estado inicial / valores por defecto de los filtros. */
export const NORA_PROSPECT_DEFAULT_FILTERS: NoraProspectFilters = {
    search: '',
    status: 'ALL',
    seller: 'ALL',
    channel: 'ALL',
    dateFrom: '',
    dateTo: '',
};

/** Clave de ordenamiento del listado. */
export type NoraSortKey = 'ingreso' | 'nombre' | 'ultimo_contacto' | 'estado';
/** Dirección de ordenamiento. */
export type NoraSortDir = 'asc' | 'desc';

/** Defaults de orden: por fecha de ingreso, más nuevos primero. */
export const NORA_PROSPECT_DEFAULT_SORT_KEY: NoraSortKey = 'ingreso';
export const NORA_PROSPECT_DEFAULT_SORT_DIR: NoraSortDir = 'desc';

/** Opción de canal de adquisición (value crudo + label legible). */
export interface NoraChannelOption {
    value: string;
    label: string;
}

interface NoraProspectsToolbarProps {
    filters: NoraProspectFilters;
    onChange: (next: Partial<NoraProspectFilters>) => void;
    onClear: () => void;
    /** Emails de seller presentes en los prospectos cargados (no nulos). */
    sellerOptions: string[];
    /** Canales de adquisición disponibles (conocidos + presentes en datos). */
    channelOptions: NoraChannelOption[];
    /** Estado de ordenamiento (controlado desde el panel). */
    sortKey: NoraSortKey;
    sortDir: NoraSortDir;
    onSortChange: (key: NoraSortKey, dir: NoraSortDir) => void;
    /** True si hay algún filtro/orden distinto del default (habilita "Limpiar"). */
    isDirty: boolean;
}

const SELECT_CLASS =
    'py-2.5 px-3 bg-white border border-slate-200 rounded-xl focus:ring-4 focus:ring-slate-100 focus:border-slate-400 outline-none transition-all text-slate-700 font-medium text-sm';

const DATE_CLASS =
    'py-2 px-3 bg-white border border-slate-200 rounded-xl focus:ring-4 focus:ring-slate-100 focus:border-slate-400 outline-none transition-all text-slate-600 text-sm';

export default function NoraProspectsToolbar({
    filters,
    onChange,
    onClear,
    sellerOptions,
    channelOptions,
    sortKey,
    sortDir,
    onSortChange,
    isDirty,
}: NoraProspectsToolbarProps) {
    return (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 space-y-3">
            {/* Fila 1: búsqueda + limpiar */}
            <div className="flex flex-col sm:flex-row gap-3">
                <div className="relative flex-1 min-w-[220px]">
                    <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                    <input
                        type="text"
                        placeholder="Buscar por nombre, email, teléfono, mensaje o notas..."
                        className="w-full pl-11 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl focus:ring-4 focus:ring-slate-100 focus:border-slate-400 outline-none transition-all text-slate-700 text-sm"
                        value={filters.search}
                        onChange={(e) => onChange({ search: e.target.value })}
                    />
                </div>
                <button
                    type="button"
                    onClick={onClear}
                    disabled={!isDirty}
                    className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold text-slate-500 bg-slate-100 hover:bg-slate-200 transition-colors whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed"
                >
                    <X size={16} />
                    Limpiar filtros
                </button>
            </div>

            {/* Fila 2: filtros + orden */}
            <div className="flex flex-wrap items-center gap-3">
                {/* Estado */}
                <select
                    aria-label="Filtrar por estado"
                    className={SELECT_CLASS}
                    value={filters.status}
                    onChange={(e) => onChange({ status: e.target.value })}
                >
                    <option value="ALL">Todos los estados</option>
                    <option value="NEW">Nuevo</option>
                    <option value="CONTACTED">Contactado</option>
                    <option value="CLIENT">Cliente</option>
                </select>

                {/* Asignado */}
                <select
                    aria-label="Filtrar por asignado"
                    className={SELECT_CLASS}
                    value={filters.seller}
                    onChange={(e) => onChange({ seller: e.target.value })}
                >
                    <option value="ALL">Todos los asignados</option>
                    <option value="UNASSIGNED">Sin asignar</option>
                    {sellerOptions.map((s) => (
                        <option key={s} value={s}>
                            {s.split('@')[0]}
                        </option>
                    ))}
                </select>

                {/* Canal de adquisición */}
                <select
                    aria-label="Filtrar por canal de adquisición"
                    className={SELECT_CLASS}
                    value={filters.channel}
                    onChange={(e) => onChange({ channel: e.target.value })}
                >
                    <option value="ALL">Todos los canales</option>
                    {channelOptions.map((c) => (
                        <option key={c.value} value={c.value}>
                            {c.label}
                        </option>
                    ))}
                </select>

                {/* Rango de fechas (ingreso) */}
                <div className="flex items-center gap-2">
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wide">Desde</label>
                    <input
                        type="date"
                        aria-label="Fecha de ingreso desde"
                        className={DATE_CLASS}
                        value={filters.dateFrom}
                        max={filters.dateTo || undefined}
                        onChange={(e) => onChange({ dateFrom: e.target.value })}
                    />
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wide">Hasta</label>
                    <input
                        type="date"
                        aria-label="Fecha de ingreso hasta"
                        className={DATE_CLASS}
                        value={filters.dateTo}
                        min={filters.dateFrom || undefined}
                        onChange={(e) => onChange({ dateTo: e.target.value })}
                    />
                </div>

                {/* Separador flexible */}
                <div className="flex-1 min-w-[8px]" />

                {/* Ordenar por */}
                <select
                    aria-label="Ordenar por"
                    className={SELECT_CLASS}
                    value={sortKey}
                    onChange={(e) => onSortChange(e.target.value as NoraSortKey, sortDir)}
                >
                    <option value="ingreso">Ordenar: Ingreso</option>
                    <option value="nombre">Ordenar: Nombre</option>
                    <option value="ultimo_contacto">Ordenar: Último contacto</option>
                    <option value="estado">Ordenar: Estado</option>
                </select>

                {/* Dirección */}
                <select
                    aria-label="Dirección de orden"
                    className={SELECT_CLASS}
                    value={sortDir}
                    onChange={(e) => onSortChange(sortKey, e.target.value as NoraSortDir)}
                >
                    <option value="desc">Descendente</option>
                    <option value="asc">Ascendente</option>
                </select>
            </div>
        </div>
    );
}
