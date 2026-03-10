"use client";

import React, { useEffect, useState } from 'react';
import {
    MessageCircle,
    Search,
    Tag,
    ChevronLeft,
    ChevronRight,
    History,
    UserPlus,
    X,
    Save,
    RotateCcw,
    CheckCircle,
    Trash2,
    Download
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import CloseSaleModal from './CloseSaleModal';

interface Lead {
    id: number;
    full_name: string;
    email: string;
    phone: string;
    product_interest: string;
    category_interest: string;
    status: string;
    lead_date?: string;
    created_at?: string;
    contacted_at?: string;
    source: string;
    platform: string;
    seller: string;
    notes: string;
    feedback_status: string;
}

const ITEMS_PER_PAGE = 10;

export default function SellerDashboard() {
    const { user: currentUser } = useAuth();
    const [leads, setLeads] = useState<Lead[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");
    const [activeTab, setActiveTab] = useState<"NEW" | "CONTACTED">("NEW");
    const [currentPage, setCurrentPage] = useState(1);

    // Modal state
    const [showFeedbackModal, setShowFeedbackModal] = useState(false);
    const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
    const [feedbackResult, setFeedbackResult] = useState("Respondio");
    const [feedbackNotes, setFeedbackNotes] = useState("");

    // Close Sale state
    const [leadToClose, setLeadToClose] = useState<Lead | null>(null);

    // New Lead State
    const [showAddLeadModal, setShowAddLeadModal] = useState(false);
    const [isSavingNewLead, setIsSavingNewLead] = useState(false);
    const [newLeadFormData, setNewLeadFormData] = useState({
        full_name: '',
        address: '',
        email: '',
        phone: '',
        product_interest: ''
    });

    // Delete Lead State
    const [leadToDelete, setLeadToDelete] = useState<Lead | null>(null);
    const [deleteReason, setDeleteReason] = useState("No contesta llamados ni mensajes");
    const [isDeleting, setIsDeleting] = useState(false);

    useEffect(() => {
        fetchLeads();
    }, []);

    const fetchLeads = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/leads/`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            const data = await response.json();
            setLeads(data);
            setLoading(false);
        } catch (error) {
            console.error("Error fetching leads:", error);
            setLoading(false);
        }
    };

    const handleWhatsAppClick = async (lead: Lead) => {
        // Open link immediately
        window.open(getWhatsAppLink(lead), '_blank');

        // Move to contacted automatically if it was new
        if (lead.status === 'NEW' && currentUser?.email) {
            try {
                const token = localStorage.getItem('token');
                const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/leads/${lead.id}`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        status: 'CONTACTED',
                        seller: currentUser.email
                    })
                });

                if (response.ok) {
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

    const handleOpenFeedbackModal = (lead: Lead) => {
        setSelectedLead(lead);
        setFeedbackResult(lead.feedback_status || "Respondio");
        setFeedbackNotes(lead.notes || "");
        setShowFeedbackModal(true);
    };

    const handleSaveFeedback = async () => {
        if (!selectedLead) return;

        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/leads/${selectedLead.id}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    feedback_status: feedbackResult,
                    notes: feedbackNotes
                })
            });

            if (response.ok) {
                // Update local state
                setLeads(leads.map(l =>
                    l.id === selectedLead.id
                        ? { ...l, feedback_status: feedbackResult, notes: feedbackNotes }
                        : l
                ));
                setShowFeedbackModal(false);
                setFeedbackNotes("");
            }
        } catch (error) {
            console.error("Error saving feedback:", error);
        }
    };

    const handleRevertToNew = async (lead: Lead) => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/leads/${lead.id}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    status: 'NEW',
                    feedback_status: null, // Reset feedback when reverting
                    seller: null // Release ownership
                })
            });

            if (response.ok) {
                setLeads(leads.map(l => l.id === lead.id ? { ...l, status: 'NEW', feedback_status: null, seller: null } : l));
            }
        } catch (error) {
            console.error("Error reverting lead:", error);
        }
    };

    const handleDeleteLead = async () => {
        if (!leadToDelete) return;
        setIsDeleting(true);
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/leads/${leadToDelete.id}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    status: 'LOST',
                    feedback_status: `Eliminado: ${deleteReason}`
                })
            });

            if (response.ok) {
                setLeads(leads.filter(l => l.id !== leadToDelete.id));
                setLeadToDelete(null);
            } else {
                alert("Error al eliminar el prospecto");
            }
        } catch (error) {
            console.error("Error deleting lead:", error);
            alert("Error de conexión");
        } finally {
            setIsDeleting(false);
        }
    };

    const getWhatsAppLink = (lead: Lead) => {
        const base = "https://wa.me/" + lead.phone.replace(/\+/g, '').replace(/\s/g, '');
        const sellerFirstName = currentUser?.full_name?.split(' ')[0] || "un vendedor";
        const platformMap: Record<string, string> = {
            'ig': 'Instagram',
            'fb': 'Facebook',
        };
        const platformFriendlyName = platformMap[lead.platform?.toLowerCase()] || "nuestra página web";

        const message = `Hola ${lead.full_name}, ¿cómo estás? Soy ${sellerFirstName} de UNPO, importadores directos con más de 5 años de trayectoria en el rubro. Te escribo por la consulta que nos hiciste por ${platformFriendlyName}. ¿Tenés unos minutos para que hablemos un rato y te cuente un poco más sobre lo que ofrecemos?`;

        return `${base}?text=${encodeURIComponent(message)}`;
    };

    const handleOpenAddLead = () => {
        setNewLeadFormData({ full_name: '', address: '', email: '', phone: '', product_interest: '' });
        setShowAddLeadModal(true);
    };

    const handleSaveNewLead = async () => {
        if (!newLeadFormData.full_name.trim() || !newLeadFormData.address.trim()) {
            alert("El nombre/apellido y la dirección son obligatorios.");
            return;
        }
        setIsSavingNewLead(true);
        try {
            const payload = {
                ...newLeadFormData,
                status: 'CONTACTED',
                source: 'SELLER',
                platform: 'Bazar / Personal',
                seller: currentUser?.email
            };
            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/leads/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const newLead = await response.json();
                setLeads([newLead, ...leads]);
                setShowAddLeadModal(false);
                setActiveTab("CONTACTED");
                setCurrentPage(1);
            } else {
                const err = await response.json();
                alert(`Error al guardar el prospecto: ${err.detail || 'Desconocido'}`);
            }
        } catch (e) {
            console.error("Error creating manual lead:", e);
            alert("Error de red");
        } finally {
            setIsSavingNewLead(false);
        }
    };

    const handleDownloadCatalog = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/catalog/pdf`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `Catalogo_UNPO.pdf`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            } else {
                alert("Error al descargar el catálogo. Usted no tiene permisos o hubo un error en el servidor.");
            }
        } catch (error) {
            console.error("Error downloading catalog:", error);
            alert("Error de red al intentar descargar.");
        }
    };

    const filteredLeads = leads
        .filter(l => l.status === activeTab)
        .filter(l =>
            l.full_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
            l.phone?.includes(searchTerm) ||
            l.email?.toLowerCase().includes(searchTerm.toLowerCase())
        );

    // Pagination
    const totalPages = Math.ceil(filteredLeads.length / ITEMS_PER_PAGE);
    const paginatedLeads = filteredLeads.slice(
        (currentPage - 1) * ITEMS_PER_PAGE,
        currentPage * ITEMS_PER_PAGE
    );

    const getFeedbackBadge = (status: string) => {
        switch (status) {
            case 'Respondio':
                return <span className="px-2 py-0.5 rounded-md text-[10px] font-black bg-emerald-50 text-emerald-600 border border-emerald-100 uppercase">Respondió</span>;
            case 'No responde':
                return <span className="px-2 py-0.5 rounded-md text-[10px] font-black bg-amber-50 text-amber-600 border border-amber-100 uppercase">Sin respuesta</span>;
            case 'Numero erroneo':
                return <span className="px-2 py-0.5 rounded-md text-[10px] font-black bg-rose-50 text-rose-600 border border-rose-100 uppercase">Nro. Erróneo</span>;
            default:
                return <span className="px-2 py-0.5 rounded-md text-[10px] font-black bg-slate-50 text-slate-400 border border-slate-100 uppercase">Pendiente</span>;
        }
    };

    return (
        <div className="space-y-6">
            {/* Header & Stats */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-3xl font-black text-slate-900 tracking-tight">Gestión de Leads</h2>
                    <p className="text-slate-500">Administra y contacta a tus potenciales clientes de UNPO</p>
                </div>

                <div className="flex bg-white rounded-2xl p-1 shadow-sm border border-slate-100 self-start">
                    <button
                        onClick={handleDownloadCatalog}
                        className="px-6 py-2 mr-2 rounded-xl text-sm font-bold transition-all flex items-center gap-2 bg-emerald-50 text-emerald-600 hover:bg-emerald-100 border border-emerald-200"
                        title="Descargar Catálogo en stock (PDF)"
                    >
                        <Download size={18} />
                        Catálogo PDF
                    </button>
                    <button
                        onClick={() => { setActiveTab("NEW"); setCurrentPage(1); }}
                        className={`px-6 py-2 rounded-xl text-sm font-bold transition-all flex items-center gap-2 ${activeTab === "NEW" ? 'bg-blue-600 text-white shadow-md' : 'text-slate-500 hover:bg-slate-50'
                            }`}
                    >
                        <UserPlus size={18} />
                        Nuevos ({leads.filter(l => l.status === 'NEW').length})
                    </button>
                    <button
                        onClick={() => { setActiveTab("CONTACTED"); setCurrentPage(1); }}
                        className={`px-6 py-2 rounded-xl text-sm font-bold transition-all flex items-center gap-2 ${activeTab === "CONTACTED" ? 'bg-slate-900 text-white shadow-md' : 'text-slate-500 hover:bg-slate-50'
                            }`}
                    >
                        <History size={18} />
                        Contactados ({leads.filter(l => l.status === 'CONTACTED').length})
                    </button>
                </div>
            </div>

            {/* Content Container */}
            <div className="bg-white rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden">
                {/* Tools Bar */}
                <div className="p-6 border-b border-slate-50 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-50/30">
                    <div className="relative flex-1">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                        <input
                            type="text"
                            placeholder="Buscar por nombre, email o tel..."
                            className="w-full pl-12 pr-4 py-3 bg-white border border-slate-200 rounded-2xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 outline-none transition-all text-slate-700"
                            value={searchTerm}
                            onChange={(e) => { setSearchTerm(e.target.value); setCurrentPage(1); }}
                        />
                    </div>
                    {activeTab === "CONTACTED" && (
                        <button
                            onClick={handleOpenAddLead}
                            className="px-6 py-3 shrink-0 bg-slate-900 text-white font-bold rounded-2xl flex items-center justify-center gap-2 hover:bg-slate-800 transition-colors shadow-md"
                        >
                            <UserPlus size={18} /> Nuevo Contacto Manual
                        </button>
                    )}
                </div>

                {/* Table */}
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead className="bg-slate-50/50 text-slate-500 text-[11px] uppercase tracking-widest font-black">
                            <tr>
                                <th className="px-8 py-5">Cliente</th>
                                <th className="px-8 py-5">Interés</th>
                                <th className="px-8 py-5">{activeTab === "NEW" ? "Fecha / Origen" : "Resultado / Notas"}</th>
                                <th className="px-8 py-5 text-right">Acción</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {loading ? (
                                <tr><td colSpan={4} className="text-center py-20 text-slate-400 font-medium">Cargando base de datos...</td></tr>
                            ) : paginatedLeads.length === 0 ? (
                                <tr><td colSpan={4} className="text-center py-20 text-slate-400 font-medium">No se encontraron registros</td></tr>
                            ) : paginatedLeads.map((lead) => (
                                <tr key={lead.id} className="hover:bg-slate-50/80 transition-colors group">
                                    <td className="px-8 py-6">
                                        <div className="font-bold text-slate-900 text-lg leading-tight">{lead.full_name}</div>
                                        <div className="text-sm text-slate-500 mt-1 flex items-center gap-2">
                                            <span>{lead.phone}</span>
                                            {lead.email && <span className="text-slate-300">|</span>}
                                            <span className="truncate max-w-[150px] font-medium text-slate-400">{lead.email}</span>
                                        </div>
                                    </td>
                                    <td className="px-8 py-6">
                                        <div className="flex items-center gap-2">
                                            <Tag size={16} className="text-blue-500" />
                                            <span className="text-sm font-bold text-slate-700">{lead.product_interest || lead.category_interest || "General"}</span>
                                        </div>
                                        <div className="mt-2 text-[10px] font-black">
                                            <span className={`px-2 py-0.5 rounded-md uppercase border ${lead.platform?.includes('ig')
                                                ? 'bg-pink-50 text-pink-600 border-pink-100'
                                                : 'bg-indigo-50 text-indigo-600 border-indigo-100'
                                                }`}>
                                                {lead.platform || 'WEB'}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-8 py-6">
                                        {activeTab === "NEW" ? (
                                            <div className="text-sm font-bold text-slate-700">
                                                {(lead.lead_date || lead.created_at) ? new Date(lead.lead_date || lead.created_at as string).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' }) : "-"}
                                            </div>
                                        ) : (
                                            <div className="space-y-1">
                                                <div className="text-[10px] text-slate-400 uppercase font-black tracking-widest leading-none mb-1">Contactado el</div>
                                                <div className="flex items-center gap-1.5 text-sm font-bold text-blue-600">
                                                    <History size={14} strokeWidth={2.5} />
                                                    {lead.contacted_at ? new Date(lead.contacted_at).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' }) : "-"}
                                                </div>
                                            </div>
                                        )}
                                    </td>
                                    <td className="px-8 py-6">
                                        {activeTab === "NEW" ? (
                                            <div className="text-[10px] font-black uppercase text-slate-400 tracking-widest italic leading-none">Pendiente</div>
                                        ) : (
                                            <div className="space-y-2">
                                                <div className="flex items-center gap-2">
                                                    {getFeedbackBadge(lead.feedback_status)}
                                                    {currentUser?.role === 'admin' && lead.seller && (
                                                        <span className="text-[10px] font-bold text-slate-400 bg-slate-100 px-2 py-0.5 rounded uppercase">
                                                            Vendedor: {lead.seller.split('@')[0]}
                                                        </span>
                                                    )}
                                                </div>
                                                {lead.notes && (
                                                    <div className="text-[11px] text-slate-500 bg-slate-50 p-2 rounded-lg italic border border-slate-100 max-w-[200px] truncate group-hover:whitespace-normal group-hover:overflow-visible transition-all">
                                                        {lead.notes}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </td>
                                    <td className="px-8 py-6 text-right">
                                        <div className="flex items-center justify-end gap-3">
                                            {activeTab === "NEW" ? (
                                                <button
                                                    onClick={() => handleWhatsAppClick(lead)}
                                                    className="inline-flex items-center gap-2 px-6 py-2.5 bg-green-500 hover:bg-green-600 text-white text-sm font-black rounded-2xl transition-all hover:scale-105 active:scale-95 shadow-lg shadow-green-200"
                                                >
                                                    <MessageCircle size={20} />
                                                    WhatsApp
                                                </button>
                                            ) : (
                                                <>
                                                    <button
                                                        onClick={() => handleOpenFeedbackModal(lead)}
                                                        className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-black rounded-xl transition-all shadow-md shadow-blue-100"
                                                    >
                                                        <Save size={14} />
                                                        Feedback
                                                    </button>
                                                    <button
                                                        onClick={() => setLeadToClose(lead)}
                                                        className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-black rounded-xl transition-all shadow-md shadow-emerald-100"
                                                    >
                                                        <CheckCircle size={14} />
                                                        Cerrar Venta
                                                    </button>
                                                    <button
                                                        onClick={() => handleRevertToNew(lead)}
                                                        className="p-2 text-slate-300 hover:text-amber-500 hover:bg-amber-50 rounded-xl transition-all"
                                                        title="Mover a Nuevos"
                                                    >
                                                        <RotateCcw size={18} />
                                                    </button>
                                                    <button
                                                        onClick={() => setLeadToDelete(lead)}
                                                        className="p-2 text-slate-300 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-all"
                                                        title="Eliminar Registro"
                                                    >
                                                        <Trash2 size={18} />
                                                    </button>
                                                </>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Pagination Footer */}
                {
                    !loading && totalPages > 1 && (
                        <div className="px-8 py-6 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between">
                            <div className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                                Página {currentPage} de {totalPages}
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                    disabled={currentPage === 1}
                                    className="p-2 border border-slate-200 rounded-xl hover:bg-white disabled:opacity-30 transition-all shadow-sm"
                                >
                                    <ChevronLeft size={20} />
                                </button>

                                <div className="flex items-center gap-1 mx-2">
                                    {Array.from({ length: totalPages }, (_, i) => i + 1)
                                        .filter(p => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 1)
                                        .map((p, i, arr) => (
                                            <React.Fragment key={p}>
                                                {i > 0 && arr[i - 1] !== p - 1 && <span className="text-slate-300 mx-1">...</span>}
                                                <button
                                                    onClick={() => setCurrentPage(p)}
                                                    className={`w-10 h-10 rounded-xl text-sm font-bold transition-all ${currentPage === p ? 'bg-blue-600 text-white shadow-md' : 'text-slate-400 hover:bg-white hover:text-slate-700 border border-transparent hover:border-slate-100'}`}
                                                >
                                                    {p}
                                                </button>
                                            </React.Fragment>
                                        ))
                                    }
                                </div>

                                <button
                                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                    disabled={currentPage === totalPages}
                                    className="p-2 border border-slate-200 rounded-xl hover:bg-white disabled:opacity-30 transition-all shadow-sm"
                                >
                                    <ChevronRight size={20} />
                                </button>
                            </div>
                        </div>
                    )
                }
            </div >

            {/* Feedback Modal */}
            {
                showFeedbackModal && selectedLead && (
                    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
                        <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={() => setShowFeedbackModal(false)}></div>
                        <div className="relative bg-white w-full max-w-md rounded-[40px] shadow-2xl overflow-hidden border border-white translate-y-[-20px] animate-in fade-in zoom-in duration-300">
                            <div className="p-10">
                                <div className="flex justify-between items-start mb-8">
                                    <div>
                                        <h3 className="text-3xl font-black text-slate-900 tracking-tighter italic">Registro de Contacto</h3>
                                        <p className="text-slate-500 text-sm mt-1 font-medium italic">¿Cómo resultó la charla con {selectedLead.full_name}?</p>
                                    </div>
                                    <button onClick={() => setShowFeedbackModal(false)} className="p-2 hover:bg-slate-100 rounded-full transition-colors mt-[-8px] mr-[-8px]">
                                        <X size={28} className="text-slate-400" />
                                    </button>
                                </div>

                                <div className="space-y-8">
                                    <div>
                                        <label className="block text-[11px] font-black text-slate-400 uppercase tracking-[0.15em] mb-4">Resultado</label>
                                        <div className="grid grid-cols-1 gap-3">
                                            {[
                                                { id: "Respondio", label: "Respondio", color: "blue", active: feedbackResult === "Respondio" },
                                                { id: "No responde", label: "No responde", color: "slate", active: feedbackResult === "No responde" },
                                                { id: "Numero erroneo", label: "Numero erroneo", color: "slate", active: feedbackResult === "Numero erroneo" }
                                            ].map((res) => (
                                                <button
                                                    key={res.id}
                                                    onClick={() => setFeedbackResult(res.id)}
                                                    className={`px-6 py-4 rounded-2xl text-base font-black border-[3px] transition-all text-left flex items-center justify-between ${res.active
                                                        ? 'border-blue-600 bg-white text-blue-700 shadow-md shadow-blue-50'
                                                        : 'border-slate-100 hover:border-slate-200 text-slate-400 bg-white'
                                                        }`}
                                                >
                                                    <span>{res.label}</span>
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-[11px] font-black text-slate-400 uppercase tracking-[0.15em] mb-4">Comentarios Adicionales</label>
                                        <textarea
                                            className="w-full px-6 py-5 bg-white border-2 border-slate-100 rounded-3xl focus:ring-4 focus:ring-blue-50 focus:border-blue-500 outline-none transition-all text-slate-700 min-h-[140px] text-base placeholder:text-slate-300 resize-none shadow-inner"
                                            placeholder="Escribe aquí cualquier detalle importante..."
                                            value={feedbackNotes}
                                            onChange={(e) => setFeedbackNotes(e.target.value)}
                                        ></textarea>
                                    </div>

                                    <div className="space-y-6 pt-2">
                                        <button
                                            onClick={handleSaveFeedback}
                                            className="w-full py-5 bg-slate-900 hover:bg-slate-800 text-white font-black text-xl rounded-[24px] transition-all shadow-2xl shadow-slate-300 flex items-center justify-center gap-3 active:scale-95"
                                        >
                                            <Save size={24} />
                                            Guardar y Finalizar
                                        </button>

                                        <button
                                            onClick={() => setShowFeedbackModal(false)}
                                            className="w-full text-center text-[10px] text-slate-400 font-black uppercase tracking-[0.05em] hover:text-slate-600 transition-colors"
                                        >
                                            OMITIR POR AHORA (QUEDARÁ EN CONTACTADOS)
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )
            }

            {/* Add Lead Modal */}
            {
                showAddLeadModal && (
                    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
                        <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={() => setShowAddLeadModal(false)}></div>
                        <div className="relative bg-white w-full max-w-lg rounded-[40px] shadow-2xl overflow-hidden border border-white translate-y-[-20px] animate-in fade-in zoom-in duration-300 flex flex-col max-h-[90vh]">
                            <div className="p-8 border-b border-slate-100 flex justify-between items-center bg-slate-50/50 shrink-0">
                                <div>
                                    <h3 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
                                        <UserPlus size={24} className="text-blue-600" /> Nuevo Contacto Bazar
                                    </h3>
                                    <p className="text-slate-500 text-sm mt-1 font-medium italic">Registra un potencial cliente de la calle.</p>
                                </div>
                                <button onClick={() => setShowAddLeadModal(false)} className="p-2 hover:bg-slate-200 rounded-full transition-colors mt-[-8px] mr-[-8px] text-slate-400 hover:text-slate-600">
                                    <X size={24} />
                                </button>
                            </div>

                            <div className="p-8 overflow-y-auto space-y-6 flex-1">
                                <div className="space-y-4">
                                    <div>
                                        <label className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1">Nombre y Apellido <span className="text-rose-500">*</span></label>
                                        <input
                                            value={newLeadFormData.full_name}
                                            onChange={e => setNewLeadFormData({ ...newLeadFormData, full_name: e.target.value })}
                                            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                                            autoFocus
                                        />
                                    </div>
                                    <div>
                                        <label className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1">Dirección del Bazar <span className="text-rose-500">*</span></label>
                                        <input
                                            value={newLeadFormData.address}
                                            onChange={e => setNewLeadFormData({ ...newLeadFormData, address: e.target.value })}
                                            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className="text-xs font-bold text-slate-500 uppercase">Teléfono / WhatsApp</label>
                                            <input
                                                value={newLeadFormData.phone}
                                                onChange={e => setNewLeadFormData({ ...newLeadFormData, phone: e.target.value })}
                                                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                                            />
                                        </div>
                                        <div>
                                            <label className="text-xs font-bold text-slate-500 uppercase">Email</label>
                                            <input
                                                value={newLeadFormData.email}
                                                onChange={e => setNewLeadFormData({ ...newLeadFormData, email: e.target.value })}
                                                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                                            />
                                        </div>
                                    </div>
                                    <div>
                                        <label className="text-xs font-bold text-slate-500 uppercase">Producto Principal de Interés</label>
                                        <input
                                            value={newLeadFormData.product_interest}
                                            onChange={e => setNewLeadFormData({ ...newLeadFormData, product_interest: e.target.value })}
                                            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="p-8 border-t border-slate-100 shrink-0 bg-white">
                                <button
                                    disabled={isSavingNewLead}
                                    onClick={handleSaveNewLead}
                                    className="w-full py-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-black text-lg rounded-2xl transition-all shadow-xl shadow-blue-200 flex items-center justify-center gap-2"
                                >
                                    {isSavingNewLead ? 'Guardando...' : (
                                        <><Save size={20} /> Guardar Contacto</>
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                )
            }

            {/* Delete Lead Modal */}
            {leadToDelete && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
                    <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={() => setLeadToDelete(null)}></div>
                    <div className="relative bg-white w-full max-w-md rounded-[40px] shadow-2xl overflow-hidden border border-white animate-in fade-in zoom-in duration-300">
                        <div className="p-10">
                            <div className="flex justify-between items-start mb-6">
                                <div>
                                    <h3 className="text-2xl font-black text-rose-600 tracking-tight">Eliminar Registro</h3>
                                    <p className="text-slate-500 text-sm mt-1">¿Por qué deseas eliminar el lead de <br /> <strong className="text-slate-700">{leadToDelete.full_name}</strong>?</p>
                                </div>
                                <button onClick={() => setLeadToDelete(null)} className="p-2 hover:bg-slate-100 rounded-full transition-colors mt-[-8px] mr-[-8px]">
                                    <X size={24} className="text-slate-400" />
                                </button>
                            </div>

                            <div className="space-y-3">
                                {[
                                    "No contesta llamados ni mensajes",
                                    "Número erróneo",
                                    "Número inválido"
                                ].map((reason) => (
                                    <button
                                        key={reason}
                                        onClick={() => setDeleteReason(reason)}
                                        className={`w-full p-4 rounded-xl text-left border-[3px] transition-all font-bold ${deleteReason === reason ? 'border-rose-500 bg-rose-50 text-rose-700' : 'border-slate-100 text-slate-500 hover:border-slate-200'}`}
                                    >
                                        {reason}
                                    </button>
                                ))}
                            </div>

                            <div className="mt-8 flex gap-3">
                                <button
                                    onClick={() => setLeadToDelete(null)}
                                    className="flex-1 py-4 font-bold text-slate-500 hover:bg-slate-100 rounded-2xl transition-all"
                                >
                                    Cancelar
                                </button>
                                <button
                                    onClick={handleDeleteLead}
                                    disabled={isDeleting}
                                    className="flex-1 flex items-center justify-center gap-2 py-4 bg-rose-600 hover:bg-rose-700 text-white font-black rounded-2xl transition-all shadow-lg shadow-rose-200 disabled:opacity-50"
                                >
                                    {isDeleting ? 'Borrando...' : <><Trash2 size={18} /> Eliminar</>}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Close Sale Modal */}
            {leadToClose && (
                <CloseSaleModal
                    lead={leadToClose}
                    onClose={() => setLeadToClose(null)}
                    onSuccess={() => {
                        setLeadToClose(null);
                        setLeads(leads.filter(l => l.id !== leadToClose.id));
                    }}
                />
            )}
        </div >
    );
}
