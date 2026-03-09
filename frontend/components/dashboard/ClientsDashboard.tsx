"use client";

import React, { useEffect, useState } from 'react';
import { Search, History, FileText, Download, XCircle, MessageCircle } from 'lucide-react';

interface Client {
    id: number;
    full_name: string;
    email: string;
    phone: string;
    status: string;
    dni_cuit: string;
    address: string;
    locality: string;
    province: string;
}

const ITEMS_PER_PAGE = 10;

export default function ClientsDashboard() {
    const [clients, setClients] = useState<Client[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");
    const [currentPage, setCurrentPage] = useState(1);

    useEffect(() => {
        fetchClients();
    }, []);

    const fetchClients = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('http://localhost:8000/leads/?status=CLIENT', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            setClients(data);
            setLoading(false);
        } catch (error) {
            console.error("Error fetching clients:", error);
            setLoading(false);
        }
    };

    const handleDownloadPDF = async (orderId: number) => {
        try {
            window.open(`http://localhost:8000/sales/${orderId}/pdf`, '_blank');
        } catch (error) {
            console.error(error);
        }
    };

    const handleCancelOrder = async (orderId: number) => {
        if (!confirm("¿Estás seguro de que quieres CANCELAR esta venta? Esta acción devolverá el stock y marcará el remito como cancelado.")) return;

        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`http://localhost:8000/sales/${orderId}/cancel`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (res.ok) {
                alert("Venta cancelada exitosamente y stock devuelto.");
                // We might want to refresh the UI here, but since this is just the client view, 
                // typically we'd just want to re-fetch the client's history. For simplicity we assume success.
            } else {
                alert("Ocurrió un error al cancelar la venta.");
            }
        } catch (err) {
            console.error(err);
        }
    };

    const filteredClients = clients.filter(c =>
        c.full_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.phone?.includes(searchTerm) ||
        c.dni_cuit?.includes(searchTerm)
    );

    const totalPages = Math.ceil(filteredClients.length / ITEMS_PER_PAGE) || 1;
    const paginatedClients = filteredClients.slice(
        (currentPage - 1) * ITEMS_PER_PAGE,
        currentPage * ITEMS_PER_PAGE
    );

    useEffect(() => {
        setCurrentPage(1);
    }, [searchTerm]);

    return (
        <div className="space-y-6">
            <div className="bg-white rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden">
                <div className="p-6 border-b border-slate-50 flex items-center bg-slate-50/30">
                    <div className="relative flex-1 max-w-lg">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                        <input
                            type="text"
                            placeholder="Buscar cliente por nombre, DNI o teléfono..."
                            className="w-full pl-12 pr-4 py-3 bg-white border border-slate-200 rounded-2xl focus:ring-4 focus:ring-emerald-100 focus:border-emerald-500 outline-none transition-all text-slate-700"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead className="bg-slate-50/50 text-slate-500 text-[11px] uppercase tracking-widest font-black">
                            <tr>
                                <th className="px-8 py-5">Cliente</th>
                                <th className="px-8 py-5">Facturación</th>
                                <th className="px-8 py-5">Contacto</th>
                                <th className="px-8 py-5 text-right flex items-center justify-end gap-2"><History size={14} /> Acciones</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {loading ? (
                                <tr><td colSpan={4} className="text-center py-20 text-slate-400 font-medium">Cargando clientes...</td></tr>
                            ) : paginatedClients.length === 0 ? (
                                <tr><td colSpan={4} className="text-center py-20 text-slate-400 font-medium">No hay clientes aún</td></tr>
                            ) : paginatedClients.map((client) => (
                                <tr key={client.id} className="hover:bg-slate-50/80 transition-colors">
                                    <td className="px-8 py-6">
                                        <div className="font-bold text-slate-900 text-lg leading-tight">{client.full_name}</div>
                                        <div className="text-sm text-emerald-600 mt-1 font-bold">Cliente Oficial</div>
                                    </td>
                                    <td className="px-8 py-6">
                                        <div className="text-sm font-bold text-slate-700">{client.dni_cuit || "Sin DNI"}</div>
                                        <div className="text-xs text-slate-500 mt-1 max-w-[200px] truncate">{client.address}, {client.locality}</div>
                                    </td>
                                    <td className="px-8 py-6">
                                        <div className="text-sm font-medium text-slate-700 flex items-center gap-3">
                                            {client.phone}
                                            {client.phone && (
                                                <a href={`https://wa.me/${client.phone.replace(/[^0-9]/g, '')}`} target="_blank" rel="noreferrer" className="p-1.5 bg-green-50 text-green-600 hover:bg-green-600 hover:text-white rounded-md transition-colors shadow-sm" title="Contactar por WhatsApp">
                                                    <MessageCircle size={16} />
                                                </a>
                                            )}
                                        </div>
                                    </td>
                                    <td className="px-8 py-6 text-right">
                                        <ClientHistory leadId={client.id} onDownload={handleDownloadPDF} onCancel={handleCancelOrder} />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {totalPages > 1 && (
                    <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 bg-slate-50/50">
                        <span className="text-sm text-slate-500 font-medium">
                            Página <span className="text-slate-900">{currentPage}</span> de <span className="text-slate-900">{totalPages}</span>
                        </span>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setCurrentPage(1)}
                                disabled={currentPage === 1}
                                className="px-4 py-2 text-sm font-bold rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
                            >
                                Primera
                            </button>
                            <button
                                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                                disabled={currentPage === 1}
                                className="px-4 py-2 text-sm font-bold rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
                            >
                                Anterior
                            </button>
                            <button
                                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                                disabled={currentPage === totalPages}
                                className="px-4 py-2 text-sm font-bold rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
                            >
                                Siguiente
                            </button>
                            <button
                                onClick={() => setCurrentPage(totalPages)}
                                disabled={currentPage === totalPages}
                                className="px-4 py-2 text-sm font-bold rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
                            >
                                Última
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

// Subcomponent to fetch and display the sales history of a specific client
function ClientHistory({ leadId, onDownload, onCancel }: { leadId: number, onDownload: (id: number) => void, onCancel: (id: number) => void }) {
    const [orders, setOrders] = useState<any[]>([]);

    useEffect(() => {
        fetchHistory();
    }, [leadId]);

    const fetchHistory = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`http://localhost:8000/sales/lead/${leadId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            setOrders(data);
        } catch (error) {
            console.error(error);
        }
    };

    if (orders.length === 0) return <span className="text-xs text-slate-400 italic">No hay órdenes registadas (Error interno)</span>;

    return (
        <div className="flex flex-col items-end gap-2">
            {orders.map(order => (
                <div key={order.id} className="flex items-center gap-3 bg-white border border-slate-200 shadow-sm px-3 py-1.5 rounded-lg">
                    <div className="text-right pr-3 border-r border-slate-100">
                        <span className="block text-xs font-black text-slate-800">Orden #{order.id}</span>
                        <span className={`text-[10px] font-bold ${order.status === 'COMPLETED' ? 'text-emerald-500' : 'text-rose-500'}`}>{order.status}</span>
                    </div>
                    <span className="text-sm font-black text-slate-700 w-24 text-right">${order.total_amount?.toLocaleString()}</span>

                    <button
                        onClick={() => onDownload(order.id)}
                        className="p-1.5 bg-blue-50 text-blue-600 hover:bg-blue-600 hover:text-white rounded-md transition-colors"
                        title="Descargar Remito"
                    >
                        <FileText size={16} />
                    </button>

                    {order.status === 'COMPLETED' && (
                        <button
                            onClick={() => onCancel(order.id)}
                            className="p-1.5 bg-rose-50 text-rose-600 hover:bg-rose-600 hover:text-white rounded-md transition-colors"
                            title="Cancelar Venta y Devolver Stock"
                        >
                            <XCircle size={16} />
                        </button>
                    )}
                </div>
            ))}
        </div>
    );
}
