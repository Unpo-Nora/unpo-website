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
    Download,
    XCircle,
    Users,
    ChevronDown,
    ChevronUp
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
    const [filterFeedback, setFilterFeedback] = useState("TODOS");
    const [filterSeller, setFilterSeller] = useState("TODOS");

    // Modal state
    const [showFeedbackModal, setShowFeedbackModal] = useState(false);
    const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
    const [feedbackResult, setFeedbackResult] = useState("Respondio");
    const [respondioChecklist, setRespondioChecklist] = useState<string[]>([]);
    const [otrosProductosText, setOtrosProductosText] = useState("");
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

    // Mobile Card Accordion State
    const [expandedCardId, setExpandedCardId] = useState<number | null>(null);

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
        // Open link safely in a new tab without window features to avoid popup blockers and mobile app issues
        window.open(getWhatsAppLink(lead), '_blank', 'noopener,noreferrer');

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

    const handleMarkContacted = async (lead: Lead) => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/leads/${lead.id}/mark-contacted`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                setLeads(leads.map(l =>
                    l.id === lead.id
                        ? { ...l, status: 'CONTACTED', seller: currentUser?.email || '' }
                        : l
                ));
            } else {
                alert("Error al marcar como contactado.");
            }
        } catch (error) {
            console.error("Error al marcar como contactado:", error);
            alert("Error de conexión");
        }
    };

    const handleOpenFeedbackModal = (lead: Lead) => {
        setSelectedLead(lead);
        let status = lead.feedback_status || "Respondio";
        let checklist: string[] = [];
        let otrosTexto = "";

        if (status.startsWith("Respondio - ")) {
            const optionsStr = status.replace("Respondio - ", "");
            if (optionsStr.includes("Quiere otros productos (")) {
                 const match = optionsStr.match(/Quiere otros productos \((.*?)\)/);
                 if (match) otrosTexto = match[1];
                 checklist.push("Quiere otros productos");
            } else if (optionsStr.includes("Quiere otros productos")) {
                 checklist.push("Quiere otros productos");
            }
            
            const simpleOptions = ["Pidio Catalogo", "Precios muy altos", "Poco stock", "Poca variedad de productos"];
            simpleOptions.forEach(opt => {
                if (optionsStr.includes(opt)) checklist.push(opt);
            });
            status = "Respondio";
        }
        
        setRespondioChecklist(checklist);
        setOtrosProductosText(otrosTexto);
        setFeedbackResult(status);
        setFeedbackNotes(lead.notes || "");
        setShowFeedbackModal(true);
    };

    const handleSaveFeedback = async () => {
        if (!selectedLead) return;

        let finalFeedbackStatus = feedbackResult;

        if (feedbackResult === "Respondio" && respondioChecklist.length > 0) {
            const formattedOptions = respondioChecklist.map(opt => 
                opt === "Quiere otros productos" && otrosProductosText.trim() 
                    ? `Quiere otros productos (${otrosProductosText.trim()})` 
                    : opt
            );
            finalFeedbackStatus = `Respondio - ${formattedOptions.join(', ')}`;
        }

        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/leads/${selectedLead.id}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    feedback_status: finalFeedbackStatus,
                    notes: feedbackNotes
                })
            });

            if (response.ok) {
                // Update local state
                setLeads(leads.map(l =>
                    l.id === selectedLead.id
                        ? { ...l, feedback_status: finalFeedbackStatus, notes: feedbackNotes }
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
        // Normalizar teléfono quitando espacios, guiones, paréntesis y signos
        let phone = (lead.phone || '').replace(/[\s\-\(\)\+\.]/g, '');
        
        // Quitar el 0 inicial si es código de área de Argentina (ej 011 -> 11)
        if (phone.startsWith('0') && phone.length === 11) {
            phone = phone.substring(1);
        }
        
        // Formatear según longitud para agregar código de país si falta
        if (phone.length === 10) {
            phone = '549' + phone; // Celular local de 10 dígitos (ej 1144445555)
        } else if (phone.length === 12 && phone.startsWith('54')) {
            phone = '549' + phone.substring(2); // Código 54 sin el 9 intermedio
        } else if (!phone.startsWith('54') && phone.length >= 10) {
            phone = '549' + phone; // Fallback genérico para números sin 54
        }

        const base = "https://wa.me/" + phone;
        const sellerFirstName = currentUser?.full_name?.split(' ')[0] || "un vendedor";
        const platformMap: Record<string, string> = {
            'ig': 'Instagram',
            'fb': 'Facebook',
        };
        const platformFriendlyName = platformMap[lead.platform?.toLowerCase()] || "nuestra página web";

        const message = `Hola ${lead.full_name}, ¿cómo estás?  
Mi nombre es ${sellerFirstName}, un gusto saludarte.

Te cuento brevemente sobre nosotros, y más abajo te dejo el catálogo con nuestros productos y precios.

En UNPO somos mayoristas de productos de bazar. También trabajamos con artículos de iluminación, decoración, hogar y marroquinería.

Contamos con depósito en Zona Oeste, Buenos Aires (Francisco Álvarez), y realizamos envíos a todo el país.

Nuestro mínimo de compra es de $100.000.  
Trabajamos con pago en efectivo o transferencia.  
Además, ofrecemos descuentos especiales para compras de mayor volumen.`;

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

    const handleExportNuevosToExcel = async () => {
        const nuevos = leads.filter(l => l.status === 'NEW');
        if (nuevos.length === 0) {
            alert("No hay leads nuevos para exportar");
            return;
        }

        try {
            const XLSX = await import('xlsx');
            const dataToExport = nuevos.map(l => ({
                "Nombre": l.full_name || "",
                "Teléfono": l.phone || "",
                "Email": l.email || "",
                "Interés": l.product_interest || l.category_interest || "General",
                "Origen / Plataforma": l.platform || "WEB",
                "Fecha de creación": (l.lead_date || l.created_at) ? new Date(l.lead_date || l.created_at as string).toLocaleDateString('es-AR') : "",
                "Estado": l.status,
                "Vendedor": l.seller || "",
                "Notas / Feedback": l.feedback_status || l.notes || ""
            }));

            const ws = XLSX.utils.json_to_sheet(dataToExport);
            const wb = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(wb, ws, "Nuevos");

            const dateStr = new Date().toISOString().split('T')[0];
            XLSX.writeFile(wb, `leads_nuevos_UNPO_${dateStr}.xlsx`);
        } catch (error) {
            console.error("Error al exportar a Excel:", error);
            alert("Error al intentar exportar. Es posible que el módulo 'xlsx' esté cargando.");
        }
    };

    const filteredLeads = leads
        .filter(l => l.status === activeTab)
        .filter(l =>
            l.full_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
            l.phone?.includes(searchTerm) ||
            l.email?.toLowerCase().includes(searchTerm.toLowerCase())
        )
        .filter(l => {
            if (activeTab === "NEW") return true;
            if (filterFeedback === "TODOS") return true;
            if (filterFeedback === "PENDIENTE") return !l.feedback_status;
            if (filterFeedback === "RESPONDIO") return l.feedback_status?.startsWith("Respondio");
            if (filterFeedback === "PIDIO_CATALOGO") return l.feedback_status?.includes("Pidio Catalogo");
            if (filterFeedback === "PRECIOS_ALTOS") return l.feedback_status?.includes("Precios muy altos");
            if (filterFeedback === "POCO_STOCK") return l.feedback_status?.includes("Poco stock");
            if (filterFeedback === "POCA_VARIEDAD") return l.feedback_status?.includes("Poca variedad de productos");
            if (filterFeedback === "OTROS_PRODUCTOS") return l.feedback_status?.includes("Quiere otros productos");
            if (filterFeedback === "NO_RESPONDE") return l.feedback_status === "No responde";
            if (filterFeedback === "NUMERO_ERRONEO") return l.feedback_status === "Numero erroneo";
            return true;
        })
        .filter(l => {
            if (activeTab === "NEW") return true;
            if (filterSeller === "TODOS") return true;
            return l.seller === filterSeller;
        });

    // Pagination
    const totalPages = Math.ceil(filteredLeads.length / ITEMS_PER_PAGE);
    const paginatedLeads = filteredLeads.slice(
        (currentPage - 1) * ITEMS_PER_PAGE,
        currentPage * ITEMS_PER_PAGE
    );

    const getFeedbackBadge = (status: string) => {
        if (!status) return <span className="px-2 py-0.5 rounded-md text-[10px] font-black bg-slate-50 text-slate-400 border border-slate-100 uppercase">Pendiente</span>;
        
        if (status.startsWith('Respondio')) {
            return <div className="flex flex-col gap-1">
                <span className="px-2 py-0.5 rounded-md text-[10px] font-black bg-emerald-50 text-emerald-600 border border-emerald-100 uppercase inline-block w-fit">Respondió</span>
                {status !== 'Respondio' && (
                    <span className="text-[9px] text-slate-500 font-bold max-w-[200px] truncate" title={status.replace('Respondio - ', '')}>
                        {status.replace('Respondio - ', '')}
                    </span>
                )}
            </div>;
        }

        switch (status) {
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
                    <h2 className="text-3xl font-black text-slate-900 tracking-tight flex items-center gap-4">
                        Gestión de Leads
                        {!loading && (
                            <span className="text-sm px-4 py-1.5 bg-blue-50 text-blue-600 rounded-full font-bold border border-blue-100 shadow-sm flex items-center gap-2">
                                <Users size={16} /> {leads.length} Totales
                            </span>
                        )}
                    </h2>
                    <p className="text-slate-500">Administra y contacta a tus potenciales clientes de UNPO</p>
                </div>

                <div className="flex bg-white rounded-2xl p-1 shadow-sm border border-slate-100 self-start overflow-x-auto custom-scrollbar w-full md:w-auto">
                    <div className="flex shrink-0">
                        <button
                            onClick={handleDownloadCatalog}
                            className="px-5 py-2.5 mr-2 rounded-xl text-sm font-bold transition-all flex items-center gap-2 bg-emerald-50 text-emerald-600 hover:bg-emerald-100 border border-emerald-200 whitespace-nowrap"
                            title="Descargar Catálogo en stock (PDF)"
                        >
                            <Download size={18} />
                            Catálogo PDF
                        </button>
                        <button
                            onClick={() => { setActiveTab("NEW"); setCurrentPage(1); }}
                            className={`px-5 py-2.5 rounded-xl text-sm font-bold transition-all flex items-center gap-2 whitespace-nowrap ${activeTab === "NEW" ? 'bg-blue-600 text-white shadow-md' : 'text-slate-500 hover:bg-slate-50'
                                }`}
                        >
                        <UserPlus size={18} />
                        Nuevos ({leads.filter(l => l.status === 'NEW').length})
                    </button>
                        <button
                            onClick={() => { setActiveTab("CONTACTED"); setCurrentPage(1); }}
                            className={`px-5 py-2.5 rounded-xl text-sm font-bold transition-all flex items-center gap-2 whitespace-nowrap ${activeTab === "CONTACTED" ? 'bg-slate-900 text-white shadow-md' : 'text-slate-500 hover:bg-slate-50'
                                }`}
                        >
                            <History size={18} />
                            Contactados ({leads.filter(l => l.status === 'CONTACTED').length})
                        </button>
                    </div>
                </div>
            </div>

            {/* Content Container */}
            <div className="bg-white rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden">
                {/* Tools Bar */}
                <div className="p-6 border-b border-slate-50 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-50/30">
                    <div className="relative flex-1 flex flex-col sm:flex-row gap-4">
                        <div className="relative flex-1 md:flex-[2]">
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
                            <>
                                <select
                                    value={filterFeedback}
                                    onChange={(e) => { setFilterFeedback(e.target.value); setCurrentPage(1); }}
                                    className="flex-1 py-3 px-4 bg-white border border-slate-200 rounded-2xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 outline-none transition-all text-slate-700 font-medium appearance-none"
                                >
                                    <option value="TODOS">Cualquier Feedbacks</option>
                                    <option value="PENDIENTE">Pendiente</option>
                                    <option value="RESPONDIO">Respondió (Cualquiera)</option>
                                    <option value="PIDIO_CATALOGO">- Pidió Catálogo</option>
                                    <option value="PRECIOS_ALTOS">- Precios muy altos</option>
                                    <option value="POCO_STOCK">- Poco stock</option>
                                    <option value="POCA_VARIEDAD">- Poca variedad</option>
                                    <option value="OTROS_PRODUCTOS">- Quiere otros productos</option>
                                    <option value="NO_RESPONDE">No responde</option>
                                    <option value="NUMERO_ERRONEO">Número erróneo</option>
                                </select>
                                
                                <select
                                    value={filterSeller}
                                    onChange={(e) => { setFilterSeller(e.target.value); setCurrentPage(1); }}
                                    className="flex-1 py-3 px-4 bg-white border border-slate-200 rounded-2xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 outline-none transition-all text-slate-700 font-medium appearance-none"
                                >
                                    <option value="TODOS">Todos los Vendedores</option>
                                    {Array.from(new Set(leads.filter(l => l.seller).map(l => l.seller))).map(seller => (
                                        <option key={seller || 'unknown'} value={seller || 'unknown'}>{seller ? seller.split('@')[0] : 'Desconocido'}</option>
                                    ))}
                                </select>
                            </>
                        )}
                    </div>
                    {activeTab === "NEW" && (
                        <button
                            onClick={handleExportNuevosToExcel}
                            className="px-6 py-3 shrink-0 bg-emerald-600 text-white font-bold rounded-2xl flex items-center justify-center gap-2 hover:bg-emerald-700 transition-colors shadow-md"
                        >
                            <Download size={18} /> Exportar a Excel
                        </button>
                    )}
                    {activeTab === "CONTACTED" && (
                        <button
                            onClick={handleOpenAddLead}
                            className="px-6 py-3 shrink-0 bg-slate-900 text-white font-bold rounded-2xl flex items-center justify-center gap-2 hover:bg-slate-800 transition-colors shadow-md"
                        >
                            <UserPlus size={18} /> Nuevo Contacto Manual
                        </button>
                    )}
                </div>

                {/* Desktop Table */}
                <div className="overflow-x-auto hidden lg:block">
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
                                                <div className="flex items-center gap-3">
                                                    <button
                                                        onClick={() => handleMarkContacted(lead)}
                                                        className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-black rounded-xl transition-all shadow-md shadow-slate-200"
                                                        title="Marcar como contactado"
                                                    >
                                                        <CheckCircle size={14} />
                                                        Marcar Contactado
                                                    </button>
                                                    <button
                                                        onClick={() => handleWhatsAppClick(lead)}
                                                        className="inline-flex items-center gap-2 px-6 py-2.5 bg-green-500 hover:bg-green-600 text-white text-sm font-black rounded-2xl transition-all hover:scale-105 active:scale-95 shadow-lg shadow-green-200"
                                                    >
                                                        <MessageCircle size={20} />
                                                        WhatsApp
                                                    </button>
                                                    <button
                                                        onClick={() => setLeadToDelete(lead)}
                                                        className="p-2.5 text-slate-300 hover:text-rose-600 hover:bg-rose-50 rounded-2xl transition-all"
                                                        title="Eliminar Registro"
                                                    >
                                                        <Trash2 size={22} />
                                                    </button>
                                                </div>
                                            ) : (
                                                <>
                                                    <button
                                                        onClick={() => window.open(getWhatsAppLink(lead), '_blank', 'noopener,noreferrer')}
                                                        className="inline-flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-xs font-black rounded-xl transition-all shadow-md shadow-green-100"
                                                    >
                                                        <MessageCircle size={14} />
                                                        Ver Chat
                                                    </button>
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

                {/* Mobile / Tablet Cards */}
                <div className="lg:hidden p-4 sm:p-6 bg-slate-50/50">
                    {loading ? (
                        <div className="text-center py-10 text-slate-400 font-medium">Cargando base de datos...</div>
                    ) : paginatedLeads.length === 0 ? (
                        <div className="text-center py-10 text-slate-400 font-medium">No se encontraron registros</div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {paginatedLeads.map(lead => (
                                <div key={lead.id} className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
                                    {/* Card Header */}
                                    <div className="p-4 border-b border-slate-100 flex justify-between items-start gap-2">
                                        <div className="flex-1">
                                            <h3 className="font-black text-slate-900 text-lg leading-tight">{lead.full_name}</h3>
                                            <a href={`tel:${lead.phone}`} className="text-slate-600 font-bold mt-1 inline-block text-sm hover:text-blue-600 transition-colors">
                                                {lead.phone}
                                            </a>
                                        </div>
                                        <div className="shrink-0 text-right">
                                            {activeTab === "NEW" ? (
                                                <span className="px-2 py-1 rounded-lg text-[10px] font-black uppercase bg-blue-50 text-blue-600 border border-blue-100">Nuevo</span>
                                            ) : (
                                                getFeedbackBadge(lead.feedback_status)
                                            )}
                                        </div>
                                    </div>
                                    
                                    {/* Card Body */}
                                    <div className="p-4 flex flex-col gap-3">
                                        <div className="flex items-center gap-2">
                                            <Tag size={16} className="text-blue-500 shrink-0" />
                                            <span className="text-sm font-bold text-slate-700 truncate">{lead.product_interest || lead.category_interest || "General"}</span>
                                        </div>
                                        <div className="flex items-center justify-between">
                                            <span className={`px-2 py-0.5 rounded-md text-[10px] font-black uppercase border ${lead.platform?.includes('ig') ? 'bg-pink-50 text-pink-600 border-pink-100' : 'bg-indigo-50 text-indigo-600 border-indigo-100'}`}>
                                                {lead.platform || 'WEB'}
                                            </span>
                                            <div className="text-xs font-bold text-slate-500 flex items-center gap-1">
                                                <History size={12} />
                                                {activeTab === "NEW" 
                                                    ? ((lead.lead_date || lead.created_at) ? new Date(lead.lead_date || lead.created_at as string).toLocaleDateString('es-AR') : "-")
                                                    : (lead.contacted_at ? new Date(lead.contacted_at).toLocaleDateString('es-AR') : "-")
                                                }
                                            </div>
                                        </div>
                                        
                                        {/* Primary Action */}
                                        <button
                                            onClick={() => {
                                                if (activeTab === "NEW") {
                                                    handleWhatsAppClick(lead);
                                                } else {
                                                    window.open(getWhatsAppLink(lead), '_blank', 'noopener,noreferrer');
                                                }
                                            }}
                                            className="w-full mt-2 py-3 bg-green-500 hover:bg-green-600 text-white rounded-xl font-black text-sm flex items-center justify-center gap-2 shadow-lg shadow-green-200 transition-all active:scale-95"
                                        >
                                            <MessageCircle size={18} />
                                            {activeTab === "NEW" ? 'Contactar por WhatsApp' : 'Ver Chat'}
                                        </button>
                                        
                                        {/* Toggle Accordion */}
                                        <button 
                                            onClick={() => setExpandedCardId(expandedCardId === lead.id ? null : lead.id)}
                                            className="mt-1 w-full py-2 text-xs font-bold text-slate-400 hover:text-slate-600 flex items-center justify-center gap-1"
                                        >
                                            {expandedCardId === lead.id ? 'Ocultar detalles' : 'Ver más y opciones'}
                                            {expandedCardId === lead.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                        </button>
                                    </div>
                                    
                                    {/* Expanded Content */}
                                    {expandedCardId === lead.id && (
                                        <div className="border-t border-slate-100 bg-slate-50 p-4 flex flex-col gap-4 animate-in slide-in-from-top-2">
                                            {/* Extra Info */}
                                            <div className="space-y-2 text-xs">
                                                {lead.email && (
                                                    <div className="flex gap-2">
                                                        <span className="font-bold text-slate-500 w-16">Email:</span>
                                                        <span className="text-slate-700 break-all">{lead.email}</span>
                                                    </div>
                                                )}
                                                {lead.seller && (
                                                    <div className="flex gap-2">
                                                        <span className="font-bold text-slate-500 w-16">Vendedor:</span>
                                                        <span className="text-slate-700 font-bold">{lead.seller.split('@')[0]}</span>
                                                    </div>
                                                )}
                                                {lead.notes && (
                                                    <div className="mt-2 bg-white p-3 border border-slate-200 rounded-xl italic text-slate-600">
                                                        "{lead.notes}"
                                                    </div>
                                                )}
                                            </div>
                                            
                                            {/* Secondary Actions */}
                                            <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-200">
                                                {activeTab === "NEW" ? (
                                                    <>
                                                        <button
                                                            onClick={() => handleMarkContacted(lead)}
                                                            className="flex-[2] py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-colors shadow-sm"
                                                        >
                                                            <CheckCircle size={14} /> Marcar Contactado
                                                        </button>
                                                        <button
                                                            onClick={() => setLeadToDelete(lead)}
                                                            className="flex-1 py-2 bg-white border border-rose-200 text-rose-600 hover:bg-rose-50 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-colors shadow-sm"
                                                        >
                                                            <Trash2 size={14} /> Eliminar
                                                        </button>
                                                    </>
                                                ) : (
                                                    <>
                                                        <button
                                                            onClick={() => handleOpenFeedbackModal(lead)}
                                                            className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-colors shadow-sm"
                                                        >
                                                            <Save size={14} /> Feedback
                                                        </button>
                                                        <button
                                                            onClick={() => setLeadToClose(lead)}
                                                            className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-colors shadow-sm"
                                                        >
                                                            <CheckCircle size={14} /> Cerrar Venta
                                                        </button>
                                                        <button
                                                            onClick={() => handleRevertToNew(lead)}
                                                            className="px-3 py-2 bg-white border border-amber-200 text-amber-500 hover:bg-amber-50 rounded-lg transition-colors shadow-sm"
                                                            title="Mover a Nuevos"
                                                        >
                                                            <RotateCcw size={16} />
                                                        </button>
                                                        <button
                                                            onClick={() => setLeadToDelete(lead)}
                                                            className="px-3 py-2 bg-white border border-rose-200 text-rose-500 hover:bg-rose-50 rounded-lg transition-colors shadow-sm"
                                                            title="Eliminar Registro"
                                                        >
                                                            <Trash2 size={16} />
                                                        </button>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
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

                                    {feedbackResult === "Respondio" && (
                                        <div className="animate-in slide-in-from-top-2 fade-in duration-300">
                                            <label className="block text-[11px] font-black text-slate-400 uppercase tracking-[0.15em] mb-4">¿Qué respondió el cliente?</label>
                                            <div className="space-y-3">
                                                {[
                                                    "Pidio Catalogo",
                                                    "Precios muy altos",
                                                    "Poco stock",
                                                    "Poca variedad de productos",
                                                    "Quiere otros productos"
                                                ].map((opt) => (
                                                    <div key={opt} className="flex flex-col gap-2">
                                                        <label className="flex items-center gap-3 cursor-pointer group">
                                                            <div className={`w-6 h-6 rounded-md flex items-center justify-center border-2 transition-all ${respondioChecklist.includes(opt) ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-slate-300 group-hover:border-blue-400'}`}>
                                                                {respondioChecklist.includes(opt) && <CheckCircle size={16} strokeWidth={3} />}
                                                            </div>
                                                            <span className={`text-sm font-bold transition-all ${respondioChecklist.includes(opt) ? 'text-slate-900' : 'text-slate-600 group-hover:text-slate-900'}`}>{opt}</span>
                                                            <input 
                                                                type="checkbox" 
                                                                className="hidden" 
                                                                checked={respondioChecklist.includes(opt)}
                                                                onChange={(e) => {
                                                                    if (e.target.checked) setRespondioChecklist([...respondioChecklist, opt]);
                                                                    else setRespondioChecklist(respondioChecklist.filter(item => item !== opt));
                                                                }} 
                                                            />
                                                        </label>
                                                        {opt === "Quiere otros productos" && respondioChecklist.includes(opt) && (
                                                            <div className="pl-9 animate-in slide-in-from-top-1 fade-in duration-200">
                                                                <input
                                                                    type="text"
                                                                    placeholder="¿Qué productos solicitó?"
                                                                    value={otrosProductosText}
                                                                    onChange={(e) => setOtrosProductosText(e.target.value)}
                                                                    className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-100 focus:border-blue-400 outline-none transition-all text-sm text-slate-700"
                                                                />
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

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
