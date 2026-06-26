"use client";

// Etapa 4.1-B — Board de leads propio del CRM NORA.
//
// Copia funcional DEPURADA de components/dashboard/NoraDashboard.tsx (legacy):
// mismo comportamiento básico (listar, separar por estado, marcar contactado,
// revertir a nuevo), pero desacoplado del legacy y apoyado en el andamiaje 4.1-A
// (tipos + labels de estado propios de NORA).
//
// IMPORTANTE: este componente TODAVÍA NO se usa. /nora-admin sigue renderizando
// el legacy hasta la subetapa 4.1-C. No se modifica ningún archivo existente.
//
// No incluye NADA del Panel de Ventas UNPO: sin CloseSaleModal, sin presupuesto/
// PDF/catálogo, sin productos, ventas, IVA, tipo de cambio ni finanzas.
// El enlace "Contactar" reusa el deep-link wa.me ya existente en el legacy
// (no es WhatsApp Business API ni Meta API: no se agrega ninguna integración).

import React, { useEffect, useState } from 'react';
import {
    MessageCircle,
    Search,
    ChevronLeft,
    ChevronRight,
    History,
    RotateCcw
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import type { NoraLead } from './types';
import { NoraLeadStatus, getNoraLeadStatusLabel } from './leadStatus';
import { fetchNoraLeads, updateNoraLeadStatus } from '@/lib/nora/api';

const ITEMS_PER_PAGE = 10;

export default function NoraLeadsBoard() {
    const { user: currentUser } = useAuth();
    const [leads, setLeads] = useState<NoraLead[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");
    const [activeTab, setActiveTab] = useState<NoraLeadStatus>("NEW");
    const [currentPage, setCurrentPage] = useState(1);

    useEffect(() => {
        fetchLeads();
    }, []);

    const fetchLeads = async () => {
        try {
            const token = localStorage.getItem('token') ?? '';
            // El wrapper centraliza brand=nora + filtro defensivo source === "WEB_NORA".
            const noraLeads = await fetchNoraLeads(token);
            setLeads(noraLeads);
            setLoading(false);
        } catch (error) {
            console.error("Error fetching leads:", error);
            setLoading(false);
        }
    };

    const handleWhatsAppClick = async (lead: NoraLead) => {
        const base = "https://wa.me/" + lead.phone.replace(/\+/g, '').replace(/\s/g, '');
        const message = `Hola ${lead.full_name}, ¿cómo estás? Soy ${currentUser?.full_name?.split(' ')[0] || "un asesor"} de la nueva línea NORA. Hemos recibido tu interés en sumarte a nuestra waitlist. ¿Tenés unos minutos para contarte más detalles y cómo ser de los primeros en acceder a los beneficios?`;
        window.open(`${base}?text=${encodeURIComponent(message)}`, '_blank');

        if (lead.status === 'NEW' && currentUser?.email) {
            try {
                const token = localStorage.getItem('token') ?? '';
                const ok = await updateNoraLeadStatus(token, lead.id, {
                    status: 'CONTACTED',
                    seller: currentUser.email
                });

                if (ok) {
                    setLeads(leads.map(l =>
                        l.id === lead.id
                            ? { ...l, status: 'CONTACTED', seller: currentUser.email }
                            : l
                    ));
                }
            } catch (error) {
                console.error("Error moving lead to contacted:", error);
            }
        }
    };

    const handleRevertToNew = async (lead: NoraLead) => {
        try {
            const token = localStorage.getItem('token') ?? '';
            const ok = await updateNoraLeadStatus(token, lead.id, {
                status: 'NEW',
                feedback_status: null,
                seller: null
            });

            if (ok) {
                setLeads(leads.map(l => l.id === lead.id ? { ...l, status: 'NEW', feedback_status: null, seller: null } : l));
            }
        } catch (error) {
            console.error("Error reverting lead:", error);
        }
    };

    const filteredLeads = leads
        .filter(l => l.status === activeTab)
        .filter(l =>
            l.full_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
            l.phone?.includes(searchTerm) ||
            l.email?.toLowerCase().includes(searchTerm.toLowerCase())
        );

    const totalPages = Math.ceil(filteredLeads.length / ITEMS_PER_PAGE);
    const paginatedLeads = filteredLeads.slice(
        (currentPage - 1) * ITEMS_PER_PAGE,
        currentPage * ITEMS_PER_PAGE
    );

    return (
        <div className="space-y-6">
            <div className="flex bg-white rounded-2xl p-1 shadow-sm border border-slate-100 self-start w-fit">
                <button
                    onClick={() => { setActiveTab("NEW"); setCurrentPage(1); }}
                    className={`px-6 py-2 rounded-xl text-sm font-bold transition-all flex items-center gap-2 ${activeTab === "NEW" ? 'bg-slate-900 text-white shadow-md' : 'text-slate-500 hover:bg-slate-50'}`}
                >
                    {getNoraLeadStatusLabel("NEW")} ({leads.filter(l => l.status === 'NEW').length})
                </button>
                <button
                    onClick={() => { setActiveTab("CONTACTED"); setCurrentPage(1); }}
                    className={`px-6 py-2 rounded-xl text-sm font-bold transition-all flex items-center gap-2 ${activeTab === "CONTACTED" ? 'bg-slate-900 text-white shadow-md' : 'text-slate-500 hover:bg-slate-50'}`}
                >
                    <History size={18} /> {getNoraLeadStatusLabel("CONTACTED")} ({leads.filter(l => l.status === 'CONTACTED').length})
                </button>
            </div>

            <div className="bg-white rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden">
                <div className="p-6 border-b border-slate-50 bg-slate-50/30">
                    <div className="relative max-w-md">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                        <input
                            type="text"
                            placeholder="Buscar por nombre, email o tel..."
                            className="w-full pl-12 pr-4 py-3 bg-white border border-slate-200 rounded-2xl focus:ring-4 focus:ring-slate-100 focus:border-slate-400 outline-none transition-all text-slate-700"
                            value={searchTerm}
                            onChange={(e) => { setSearchTerm(e.target.value); setCurrentPage(1); }}
                        />
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead className="bg-slate-50/50 text-slate-500 text-[11px] uppercase tracking-widest font-black">
                            <tr>
                                <th className="px-8 py-5">Interesado en NORA</th>
                                <th className="px-8 py-5">Interés de Producto</th>
                                <th className="px-8 py-5">Fecha</th>
                                <th className="px-8 py-5 text-right">Acción</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {loading ? (
                                <tr><td colSpan={4} className="text-center py-20 text-slate-400 font-medium">Cargando base de datos...</td></tr>
                            ) : paginatedLeads.length === 0 ? (
                                <tr><td colSpan={4} className="text-center py-20 text-slate-400 font-medium">Aún no hay leads en esta sección</td></tr>
                            ) : paginatedLeads.map((lead) => (
                                <tr key={lead.id} className="hover:bg-slate-50/80 transition-colors group">
                                    <td className="px-8 py-6">
                                        <div className="font-bold text-slate-900 text-lg">{lead.full_name}</div>
                                        <div className="text-sm text-slate-500 gap-2 flex mt-1">
                                            <span>{lead.phone}</span> | <span>{lead.email}</span>
                                        </div>
                                    </td>
                                    <td className="px-8 py-6">
                                        <div className="font-bold text-slate-700 bg-slate-100 px-3 py-1 rounded w-fit">{lead.product_interest}</div>
                                    </td>
                                    <td className="px-8 py-6">
                                        <div className="text-sm font-bold text-slate-700">
                                            {(lead.lead_date || lead.created_at) ? new Date((lead.lead_date || lead.created_at) as string).toLocaleDateString('es-AR') : "-"}
                                        </div>
                                    </td>
                                    <td className="px-8 py-6 text-right">
                                        {activeTab === "NEW" ? (
                                            <button
                                                onClick={() => handleWhatsAppClick(lead)}
                                                className="inline-flex items-center gap-2 px-6 py-2.5 bg-slate-900 hover:bg-slate-800 text-white text-sm font-black rounded-2xl transition-all shadow-lg"
                                            >
                                                <MessageCircle size={20} />
                                                Contactar
                                            </button>
                                        ) : (
                                            <button
                                                onClick={() => handleRevertToNew(lead)}
                                                className="p-2 text-slate-300 hover:text-amber-500 hover:bg-amber-50 rounded-xl transition-all"
                                                title="Mover a Nuevos"
                                            >
                                                <RotateCcw size={18} />
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {!loading && totalPages > 1 && (
                    <div className="px-8 py-6 bg-slate-50/50 flex items-center justify-between border-t border-slate-100">
                        <div className="text-xs font-bold text-slate-400">Página {currentPage} de {totalPages}</div>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                disabled={currentPage === 1}
                                className="p-2 border border-slate-200 rounded-xl hover:bg-white disabled:opacity-30"
                            >
                                <ChevronLeft size={20} />
                            </button>
                            <button
                                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                disabled={currentPage === totalPages}
                                className="p-2 border border-slate-200 rounded-xl hover:bg-white disabled:opacity-30"
                            >
                                <ChevronRight size={20} />
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
