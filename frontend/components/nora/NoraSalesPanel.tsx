"use client";

// Etapa 4.2-A.2 — Panel de Ventas NORA: carga de leads NORA + tabla base.
//
// Carga los leads NORA reales vía fetchNoraLeads (wrapper centralizado que ya
// fuerza brand=nora + filtro defensivo source === "WEB_NORA") y los muestra en
// una tabla desktop básica con métricas simples.
//
// TODAVÍA NO incluye: filtros, ordenamiento, paginación, ficha/drawer ni
// acciones comerciales (subetapas 4.2-A.3+). No modifica estados (no llama
// updateNoraLeadStatus), no toca WhatsApp y no copia NADA del Panel de Ventas
// UNPO (SellerDashboard).

import React, { useEffect, useState } from 'react';
import { Users, UserPlus, History } from 'lucide-react';
import type { NoraLead } from './types';
import { fetchNoraLeads } from '@/lib/nora/api';
import NoraLeadsTable from './NoraLeadsTable';

export default function NoraSalesPanel() {
    const [leads, setLeads] = useState<NoraLead[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

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

    const totalCount = leads.length;
    const newCount = leads.filter((l) => l.status === 'NEW').length;
    const contactedCount = leads.filter((l) => l.status === 'CONTACTED').length;

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
                ) : (
                    <NoraLeadsTable leads={leads} />
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
