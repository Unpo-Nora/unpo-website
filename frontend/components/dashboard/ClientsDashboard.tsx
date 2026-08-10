"use client";

import React, { useEffect, useState } from 'react';
import { Search, History, FileText, Download, XCircle, MessageCircle, ShoppingCart, Trash2, Pencil } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { formatCurrency } from '@/lib/format';
import CloseSaleModal from './CloseSaleModal';

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
    zip_code?: string;
    notes?: string;
    seller?: string;
}

const ITEMS_PER_PAGE = 10;

export default function ClientsDashboard() {
    const [clients, setClients] = useState<Client[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");
    const [currentPage, setCurrentPage] = useState(1);
    const [clientToCloseSale, setClientToCloseSale] = useState<Client | null>(null);
    const [clientForRemitos, setClientForRemitos] = useState<Client | null>(null);
    const [clientToEdit, setClientToEdit] = useState<Client | null>(null);
    const [refreshKey, setRefreshKey] = useState(0);

    useEffect(() => {
        fetchClients();
    }, []);

    const fetchClients = async () => {
        try {
            const response = await apiFetch('/leads/?status=CLIENT');
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
            // El endpoint del remito ahora exige Authorization (Etapa 0A de seguridad).
            // window.open no envía headers, así que se descarga con fetch autenticado y se
            // abre el blob resultante.
            const res = await apiFetch(`/sales/${orderId}/pdf`);
            if (!res.ok) {
                alert("No se pudo descargar el remito (sesión vencida o sin permisos).");
                return;
            }
            const blobUrl = window.URL.createObjectURL(await res.blob());
            window.open(blobUrl, '_blank');
            setTimeout(() => window.URL.revokeObjectURL(blobUrl), 60000);
        } catch (error) {
            console.error(error);
        }
    };

    const handleCancelOrder = async (orderId: number) => {
        if (!confirm("¿Estás seguro de que quieres CANCELAR esta venta? Esta acción devolverá el stock y marcará el remito como cancelado.")) return;

        try {
            const res = await apiFetch(`/sales/${orderId}/cancel`, {
                method: 'POST'
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


    const handleExportExcel = async () => {
        if (filteredClients.length === 0) {
            alert("No hay clientes para exportar");
            return;
        }

        try {
            const XLSX = await import('xlsx');
            const dataToExport = filteredClients.map(c => ({
                "Nombre": c.full_name || "",
                "Email": c.email || "",
                "Teléfono": c.phone || "",
                "DNI/CUIT": c.dni_cuit || "",
                "Dirección": c.address || "",
                "Localidad": c.locality || "",
                "Provincia": c.province || "",
                "C.P.": c.zip_code || "",
                "Vendedor": c.seller || "",
                "Notas": c.notes || ""
            }));

            const ws = XLSX.utils.json_to_sheet(dataToExport);
            const wb = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(wb, ws, "Clientes");

            const dateStr = new Date().toISOString().split('T')[0];
            XLSX.writeFile(wb, `clientes_UNPO_${dateStr}.xlsx`);
        } catch (error) {
            console.error("Error al exportar a Excel:", error);
            alert("Error al intentar exportar. Es posible que el módulo 'xlsx' esté cargando.");
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
                <div className="p-6 border-b border-slate-50 flex items-center justify-between bg-slate-50/30">
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
                    <div className="flex items-center gap-3">
                        <button
                            onClick={handleExportExcel}
                            className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-black rounded-xl transition-all shadow-md shadow-emerald-100"
                        >
                            <Download size={16} /> Exportar Excel
                        </button>
                        <span className="text-sm font-bold text-slate-500 bg-white px-4 py-2 rounded-xl border border-slate-200">
                            Total Clientes: {clients.length}
                        </span>
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
                                <tr key={`${client.id}-${refreshKey}`} className="hover:bg-slate-50/80 transition-colors">
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
                                                <button onClick={() => window.open(`https://wa.me/${client.phone.replace(/[^0-9]/g, '')}`, 'whatsapp_window', 'width=800,height=600,scrollbars=yes,resizable=yes')} className="p-1.5 bg-green-50 text-green-600 hover:bg-green-600 hover:text-white rounded-md transition-colors shadow-sm" title="Contactar por WhatsApp">
                                                    <MessageCircle size={16} />
                                                </button>
                                            )}
                                        </div>
                                    </td>
                                    <td className="px-8 py-6 text-right">
                                        <div className="flex flex-col items-end gap-3">
                                            <div className="flex gap-2 mb-2">
                                                <button
                                                    onClick={() => setClientToEdit(client)}
                                                    className="inline-flex items-center gap-2 px-3 py-2 bg-slate-100 hover:bg-slate-800 text-slate-600 hover:text-white text-xs font-black rounded-xl transition-all"
                                                    title="Editar cliente"
                                                >
                                                    <Pencil size={14} />
                                                </button>
                                                <button
                                                    onClick={() => setClientForRemitos(client)}
                                                    className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-black rounded-xl transition-all shadow-md shadow-indigo-100"
                                                >
                                                    <FileText size={14} /> Ver Remitos
                                                </button>
                                                <button
                                                    onClick={() => setClientToCloseSale(client)}
                                                    className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-black rounded-xl transition-all shadow-md shadow-blue-100"
                                                >
                                                    <ShoppingCart size={14} /> Nueva Venta
                                                </button>
                                            </div>
                                        </div>
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

            {/* Close Sale Modal */}
            {clientToCloseSale && (
                <CloseSaleModal
                    lead={clientToCloseSale}
                    onClose={() => setClientToCloseSale(null)}
                    onSuccess={(orderId) => {
                        setClientToCloseSale(null);
                        setRefreshKey(prev => prev + 1);
                    }}
                />
            )}

            {/* Remitos Modal */}
            {clientForRemitos && (
                <RemitosModal
                    client={clientForRemitos}
                    onClose={() => setClientForRemitos(null)}
                    onDownload={handleDownloadPDF}
                    onCancel={handleCancelOrder}
                />
            )}

            {/* Edit Client Modal */}
            {clientToEdit && (
                <EditClientModal
                    client={clientToEdit}
                    onClose={() => setClientToEdit(null)}
                    onSaved={(updated) => {
                        setClients(prev => prev.map(c => c.id === updated.id ? { ...c, ...updated } : c));
                        setClientToEdit(null);
                    }}
                />
            )}
        </div>
    );
}

function RemitosModal({ client, onClose, onDownload, onCancel }: { client: Client, onClose: () => void, onDownload: (id: number) => void, onCancel: (id: number) => void }) {
    const [orders, setOrders] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedYear, setSelectedYear] = useState<string>('');
    const [selectedMonth, setSelectedMonth] = useState<string>('');

    useEffect(() => {
        fetchHistory();
    }, [client.id]);

    const fetchHistory = async () => {
        try {
            const response = await apiFetch(`/sales/lead/${client.id}`);
            const data = await response.json();
            setOrders(data);
            
            if (data.length > 0) {
                // Initialize selection with the most recent order's year and month
                const recentDate = new Date(data[0].created_at || data[0].date);
                setSelectedYear(recentDate.getFullYear().toString());
                setSelectedMonth((recentDate.getMonth() + 1).toString().padStart(2, '0'));
            }
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const groupedOrders = orders.reduce<Record<string, Record<string, any[]>>>((acc, order) => {
        const dateStr = order.created_at || order.date;
        if (dateStr) {
            const date = new Date(dateStr);
            const year = date.getFullYear().toString();
            const month = (date.getMonth() + 1).toString().padStart(2, '0');
            
            if (!acc[year]) acc[year] = {};
            if (!acc[year][month]) acc[year][month] = [];
            
            acc[year][month].push(order);
        }
        return acc;
    }, {});

    const availableYears = Object.keys(groupedOrders).sort((a, b) => Number(b) - Number(a));
    const availableMonths = selectedYear && groupedOrders[selectedYear] 
        ? Object.keys(groupedOrders[selectedYear]).sort((a, b) => Number(b) - Number(a))
        : [];

    const formatMonth = (m: string) => {
        const date = new Date(2000, Number(m) - 1, 1);
        const name = new Intl.DateTimeFormat('es-AR', { month: 'long' }).format(date);
        return name.charAt(0).toUpperCase() + name.slice(1);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose}></div>
            <div className="relative bg-white w-full max-w-2xl rounded-[32px] shadow-2xl overflow-hidden border border-white translate-y-[-20px] animate-in fade-in zoom-in duration-300">
                <div className="p-8">
                    <div className="flex justify-between items-start mb-6 border-b border-slate-100 pb-6">
                        <div>
                            <h3 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
                                <FileText className="text-indigo-600" size={24} /> 
                                Remitos e Historial
                            </h3>
                            <p className="text-slate-500 font-medium mt-1">Cliente: <span className="text-slate-800 font-bold">{client.full_name}</span></p>
                        </div>
                        <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
                            <XCircle size={24} className="text-slate-400" />
                        </button>
                    </div>

                    {loading ? (
                        <div className="text-center py-10 font-bold text-slate-400">Cargando remitos...</div>
                    ) : orders.length === 0 ? (
                        <div className="text-center py-10">
                            <FileText size={48} className="text-slate-200 mx-auto mb-4" />
                            <p className="font-bold text-slate-500">Este cliente aún no tiene remitos asociados.</p>
                        </div>
                    ) : (
                        <div className="space-y-6">
                            <div className="flex items-center gap-4 bg-slate-50 p-4 rounded-2xl border border-slate-100">
                                <div className="flex-1">
                                    <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Año</label>
                                    <select 
                                        value={selectedYear} 
                                        onChange={(e) => {
                                            setSelectedYear(e.target.value);
                                            const months = Object.keys(groupedOrders[e.target.value] || {}).sort((a,b) => Number(b) - Number(a));
                                            if (months.length > 0) setSelectedMonth(months[0]);
                                        }}
                                        className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-xl font-bold text-slate-700 outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
                                    >
                                        {availableYears.map(year => <option key={year} value={year}>{year}</option>)}
                                    </select>
                                </div>
                                <div className="flex-1">
                                    <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Mes</label>
                                    <select 
                                        value={selectedMonth} 
                                        onChange={(e) => setSelectedMonth(e.target.value)}
                                        className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-xl font-bold text-slate-700 outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
                                    >
                                        {availableMonths.map(month => <option key={month} value={month}>{formatMonth(month)}</option>)}
                                    </select>
                                </div>
                            </div>

                            <div className="bg-slate-50/50 rounded-2xl border border-slate-100 p-4 max-h-[400px] overflow-y-auto">
                                <div className="space-y-3">
                                    {selectedYear && selectedMonth && groupedOrders[selectedYear]?.[selectedMonth]?.length > 0 ? (
                                        groupedOrders[selectedYear][selectedMonth].map(order => (
                                            <div key={order.id} className="flex items-center justify-between bg-white border border-slate-200 shadow-sm p-4 rounded-xl hover:border-indigo-200 transition-colors">
                                                <div className="flex items-center gap-4">
                                                    <div className="w-10 h-10 rounded-full bg-indigo-50 flex items-center justify-center border border-indigo-100">
                                                        <FileText size={18} className="text-indigo-600" />
                                                    </div>
                                                    <div>
                                                        <h4 className="font-black text-slate-900">Orden #{order.id}</h4>
                                                        <div className="flex items-center gap-2 mt-1">
                                                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wider ${order.status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-600 border border-emerald-100' : 'bg-rose-50 text-rose-600 border border-rose-100'}`}>
                                                                {order.status}
                                                            </span>
                                                            <span className="text-xs font-bold text-slate-400">
                                                                {new Date(order.created_at || order.date).toLocaleDateString('es-AR')}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>
                                                
                                                <div className="flex items-center gap-4">
                                                    <div className="text-right mr-4">
                                                        <div className="text-[10px] uppercase font-bold text-slate-400 tracking-widest mb-0.5">Total</div>
                                                        <div className="font-black text-slate-700">{formatCurrency(order.total_amount)}</div>
                                                    </div>
                                                    <div className="flex gap-2">
                                                        <button
                                                            onClick={() => onDownload(order.id)}
                                                            className="flex items-center gap-2 px-4 py-2 bg-indigo-50 hover:bg-indigo-600 text-indigo-600 hover:text-white rounded-xl transition-all font-bold text-xs"
                                                            title="Descargar Remito PDF"
                                                        >
                                                            <Download size={14} /> Descargar
                                                        </button>
                                                        {order.status === 'COMPLETED' && (
                                                            <button
                                                                onClick={() => {
                                                                    onCancel(order.id);
                                                                    onClose(); // Close modal after cancellation to trigger refresh or prevent dangling state
                                                                }}
                                                                className="p-2 bg-rose-50 hover:bg-rose-600 text-rose-600 hover:text-white rounded-xl transition-all"
                                                                title="Cancelar Venta y Devolver Stock"
                                                            >
                                                                <Trash2 size={16} />
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-center py-6 text-slate-400 font-bold italic">No hay remitos para el periodo seleccionado.</div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function EditClientModal({ client, onClose, onSaved }: { client: Client, onClose: () => void, onSaved: (updated: Partial<Client> & { id: number }) => void }) {
    const [form, setForm] = useState({
        full_name: client.full_name || "",
        email: client.email || "",
        phone: client.phone || "",
        dni_cuit: client.dni_cuit || "",
        address: client.address || "",
        locality: client.locality || "",
        province: client.province || "",
        zip_code: client.zip_code || "",
        notes: client.notes || ""
    });
    const [saving, setSaving] = useState(false);

    const handleChange = (field: keyof typeof form, value: string) =>
        setForm(prev => ({ ...prev, [field]: value }));

    const handleSave = async () => {
        setSaving(true);
        try {
            const response = await apiFetch(`/leads/${client.id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(form)
            });

            if (response.ok) {
                onSaved({ id: client.id, ...form });
            } else {
                const data = await response.json().catch(() => null);
                alert(data?.detail || "No se pudieron guardar los cambios del cliente.");
            }
        } catch (error) {
            console.error("Error al guardar cliente:", error);
            alert("Error de red al guardar los cambios.");
        } finally {
            setSaving(false);
        }
    };

    const labelClass = "block text-xs font-black text-slate-400 uppercase tracking-widest mb-2";
    const inputClass = "w-full px-4 py-2.5 bg-white border border-slate-200 rounded-xl font-bold text-slate-700 outline-none focus:ring-2 focus:ring-emerald-500 transition-all";

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose}></div>
            <div className="relative bg-white w-full max-w-2xl rounded-[32px] shadow-2xl overflow-hidden border border-white translate-y-[-20px] animate-in fade-in zoom-in duration-300">
                <div className="p-8">
                    <div className="flex justify-between items-start mb-6 border-b border-slate-100 pb-6">
                        <div>
                            <h3 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
                                <Pencil className="text-emerald-600" size={24} />
                                Editar Cliente
                            </h3>
                            <p className="text-slate-500 font-medium mt-1">Cliente: <span className="text-slate-800 font-bold">{client.full_name}</span></p>
                        </div>
                        <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
                            <XCircle size={24} className="text-slate-400" />
                        </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-h-[55vh] overflow-y-auto pr-1">
                        <div className="sm:col-span-2">
                            <label className={labelClass}>Nombre completo</label>
                            <input type="text" className={inputClass} value={form.full_name} onChange={(e) => handleChange('full_name', e.target.value)} />
                        </div>
                        <div>
                            <label className={labelClass}>Email</label>
                            <input type="email" className={inputClass} value={form.email} onChange={(e) => handleChange('email', e.target.value)} />
                        </div>
                        <div>
                            <label className={labelClass}>Teléfono</label>
                            <input type="text" className={inputClass} value={form.phone} onChange={(e) => handleChange('phone', e.target.value)} />
                        </div>
                        <div>
                            <label className={labelClass}>DNI/CUIT</label>
                            <input type="text" className={inputClass} value={form.dni_cuit} onChange={(e) => handleChange('dni_cuit', e.target.value)} />
                        </div>
                        <div>
                            <label className={labelClass}>Dirección</label>
                            <input type="text" className={inputClass} value={form.address} onChange={(e) => handleChange('address', e.target.value)} />
                        </div>
                        <div>
                            <label className={labelClass}>Localidad</label>
                            <input type="text" className={inputClass} value={form.locality} onChange={(e) => handleChange('locality', e.target.value)} />
                        </div>
                        <div>
                            <label className={labelClass}>Provincia</label>
                            <input type="text" className={inputClass} value={form.province} onChange={(e) => handleChange('province', e.target.value)} />
                        </div>
                        <div>
                            <label className={labelClass}>C.P.</label>
                            <input type="text" className={inputClass} value={form.zip_code} onChange={(e) => handleChange('zip_code', e.target.value)} />
                        </div>
                        <div className="sm:col-span-2">
                            <label className={labelClass}>Notas</label>
                            <textarea rows={3} className={`${inputClass} resize-none`} value={form.notes} onChange={(e) => handleChange('notes', e.target.value)} />
                        </div>
                    </div>

                    <div className="flex justify-end gap-3 mt-6 pt-6 border-t border-slate-100">
                        <button
                            onClick={onClose}
                            disabled={saving}
                            className="px-6 py-2.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 font-bold rounded-xl transition-all disabled:opacity-50"
                        >
                            Cancelar
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-black rounded-xl transition-all shadow-md shadow-emerald-100 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {saving ? "Guardando..." : "Guardar Cambios"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
