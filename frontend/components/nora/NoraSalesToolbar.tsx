"use client";

// Etapa 4.2-A.3 — Toolbar de filtros del Panel de Ventas NORA.
//
// Componente PRESENTACIONAL/controlado: recibe el estado de filtros y los
// callbacks desde NoraSalesPanel; NO mantiene estado de datos, no fetchea, no
// usa AuthContext y no llama APIs. El filtrado real se aplica client-side en
// NoraSalesPanel. Ordenamiento, rango de fechas y paginación llegan en subetapas
// posteriores (4.2-A.4+). Estética NORA/slate, sin azul UNPO.

import React from 'react';
import { Search, X } from 'lucide-react';

export interface NoraSalesFilters {
    /** Texto libre: matchea full_name / email / phone / product_interest / notes. */
    search: string;
    /** 'ALL' | 'NEW' | 'CONTACTED' | 'CLIENT'. */
    status: string;
    /** 'ALL' | 'UNASSIGNED' | <email de seller>. */
    seller: string;
    /** 'ALL' | <valor de source>. */
    channel: string;
}

/** Estado inicial / valores por defecto de los filtros. */
export const NORA_DEFAULT_FILTERS: NoraSalesFilters = {
    search: '',
    status: 'ALL',
    seller: 'ALL',
    channel: 'ALL',
};

/** Clave de ordenamiento del listado. */
export type NoraSortKey = 'ingreso' | 'nombre' | 'ultimo_contacto' | 'estado';
/** Dirección de ordenamiento. */
export type NoraSortDir = 'asc' | 'desc';

/** Defaults de orden: por fecha de ingreso, más nuevos primero. */
export const NORA_DEFAULT_SORT_KEY: NoraSortKey = 'ingreso';
export const NORA_DEFAULT_SORT_DIR: NoraSortDir = 'desc';

interface NoraSalesToolbarProps {
    filters: NoraSalesFilters;
    onChange: (next: Partial<NoraSalesFilters>) => void;
    onClear: () => void;
    /** Emails de seller presentes en los leads cargados (no nulos). */
    sellerOptions: string[];
    /** Valores de source presentes en los leads cargados. */
    channelOptions: string[];
    /** Estado de ordenamiento (controlado desde el panel). */
    sortKey: NoraSortKey;
    sortDir: NoraSortDir;
    onSortChange: (key: NoraSortKey, dir: NoraSortDir) => void;
}

/** Etiqueta legible del canal de adquisición. */
function channelLabel(source: string): string {
    return source === 'WEB_NORA' ? 'Web NORA' : source;
}

const SELECT_CLASS =
    'py-2.5 px-3 bg-white border border-slate-200 rounded-xl focus:ring-4 focus:ring-slate-100 focus:border-slate-400 outline-none transition-all text-slate-700 font-medium text-sm';

export default function NoraSalesToolbar({
    filters,
    onChange,
    onClear,
    sellerOptions,
    channelOptions,
    sortKey,
    sortDir,
    onSortChange,
}: NoraSalesToolbarProps) {
    return (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 flex flex-col lg:flex-row lg:items-center gap-3">
            {/* Buscador libre */}
            <div className="relative flex-1 min-w-[220px]">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                <input
                    type="text"
                    placeholder="Buscar por nombre, email, teléfono, interés o notas..."
                    className="w-full pl-11 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl focus:ring-4 focus:ring-slate-100 focus:border-slate-400 outline-none transition-all text-slate-700 text-sm"
                    value={filters.search}
                    onChange={(e) => onChange({ search: e.target.value })}
                />
            </div>

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

            {/* Canal */}
            <select
                aria-label="Filtrar por canal"
                className={SELECT_CLASS}
                value={filters.channel}
                onChange={(e) => onChange({ channel: e.target.value })}
            >
                <option value="ALL">Todos los canales</option>
                {channelOptions.map((c) => (
                    <option key={c} value={c}>
                        {channelLabel(c)}
                    </option>
                ))}
            </select>

            {/* Ordenar por */}
            <select
                aria-label="Ordenar por"
                className={SELECT_CLASS}
                value={sortKey}
                onChange={(e) => onSortChange(e.target.value as NoraSortKey, sortDir)}
            >
                <option value="ingreso">Ingreso</option>
                <option value="nombre">Nombre</option>
                <option value="ultimo_contacto">Último contacto</option>
                <option value="estado">Estado</option>
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

            {/* Limpiar filtros */}
            <button
                type="button"
                onClick={onClear}
                className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold text-slate-500 bg-slate-100 hover:bg-slate-200 transition-colors whitespace-nowrap"
            >
                <X size={16} />
                Limpiar filtros
            </button>
        </div>
    );
}
