"use client";

import React, { useEffect, useState } from 'react';
import {
    Users,
    TrendingUp,
    AlertTriangle,
    MessageSquare,
    BarChart3,
    ArrowRight,
    Package,
    ShoppingCart,
    Award,
    Star,
    CalendarDays,
    Download
} from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
    LineChart, Line
} from 'recharts';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';
import { useAuth } from '@/context/AuthContext';

interface AnalyticsData {
    leads: {
        total: number;
        new: number;
        contacted: number;
        conversion_rate: number;
    };
    sellers: { email: string; count: number }[];
    stock_alerts: { sku: string; name: string; stock: number }[];
    category_interest: { category: string; count: number }[];
    product_interest: { product: string; count: number }[];
    seller_sales: { seller: string; sales_count: number; total_amount: number }[];
    top_clients: { client_name: string; purchases: number; total_amount: number }[];
    top_products_sold: { product_name: string; category: string; quantity_sold: number }[];
    monthly_metrics: {
        leads_per_day: { day: string; leads: number }[];
        top_products_interest: { product: string; count: number }[];
        top_products_sold: { product_name: string; quantity_sold: number }[];
    };
}

export default function AnalyticsDashboard() {
    const [data, setData] = useState<AnalyticsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<'GENERAL' | 'MENSUAL' | 'PRODUCTOS'>('GENERAL');
    const [isExporting, setIsExporting] = useState(false);
    const { user } = useAuth();

    useEffect(() => {
        const fetchAnalytics = async () => {
            try {
                const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
                const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';

                const response = await fetch(`http://${host}:8000/analytics/summary`, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });

                if (response.ok) {
                    const result = await response.json();
                    setData(result);
                }
            } catch (error) {
                console.error("Error fetching analytics:", error);
            } finally {
                setLoading(false);
            }
        };

        fetchAnalytics();
    }, []);

    if (loading) return (
        <div className="flex items-center justify-center min-h-[400px]">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600"></div>
        </div>
    );

    if (!data) return <div className="p-8 text-center text-slate-500">No se pudieron cargar las estadísticas.</div>;

    const handleExportPDF = async () => {
        setIsExporting(true);
        try {
            const element = document.getElementById('analytics-content');
            if (!element) return;

            const canvas = await html2canvas(element, {
                scale: 2,
                backgroundColor: '#f8fafc',
                logging: false,
                useCORS: true
            } as any);

            const imgData = canvas.toDataURL('image/png');
            const pdf = new jsPDF({
                orientation: 'portrait',
                unit: 'mm',
                format: 'a4'
            });

            const pdfWidth = pdf.internal.pageSize.getWidth();
            const pdfHeight = (canvas.height * pdfWidth) / canvas.width;

            // Header for PDF
            pdf.setFontSize(22);
            pdf.setFont("helvetica", "bolditalic");
            pdf.text(`Reporte UNPO - ${activeTab}`, 14, 20);
            pdf.setFontSize(10);
            pdf.setFont("helvetica", "normal");
            pdf.text(`Generado el: ${new Date().toLocaleDateString('es-AR')} a las ${new Date().toLocaleTimeString('es-AR')}`, 14, 28);

            // Image Placement (offset below title)
            pdf.addImage(imgData, 'PNG', 0, 35, pdfWidth, pdfHeight);

            pdf.save(`UNPO_Reporte_${activeTab}_${new Date().toISOString().split('T')[0]}.pdf`);
        } catch (error) {
            console.error("Error generating PDF:", error);
            alert("Hubo un problema al generar el PDF.");
        } finally {
            setIsExporting(false);
        }
    };

    return (
        <div className="space-y-8 animate-in fade-in duration-700">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-3xl font-black text-slate-900 italic tracking-tighter">Panel Gerencial</h2>
                    <p className="text-slate-500 font-medium">Métricas de rendimiento y control del ecosistema comercial.</p>
                </div>

                <div className="flex items-center gap-4">
                    {/* Tabs Container */}
                    <div className="flex bg-white rounded-2xl p-1 shadow-sm border border-slate-100 self-start">
                        <button
                            onClick={() => setActiveTab('GENERAL')}
                            className={`px-5 py-2 rounded-xl text-sm font-bold transition-all ${activeTab === 'GENERAL' ? 'bg-slate-900 text-white shadow-md' : 'text-slate-500 hover:bg-slate-50'}`}
                        >
                            General
                        </button>
                        <button
                            onClick={() => setActiveTab('MENSUAL')}
                            className={`px-5 py-2 rounded-xl text-sm font-bold transition-all flex items-center gap-2 ${activeTab === 'MENSUAL' ? 'bg-blue-600 text-white shadow-md' : 'text-slate-500 hover:bg-slate-50'}`}
                        >
                            Tendencia Mensual
                        </button>
                        <button
                            onClick={() => setActiveTab('PRODUCTOS')}
                            className={`px-5 py-2 rounded-xl text-sm font-bold transition-all ${activeTab === 'PRODUCTOS' ? 'bg-emerald-600 text-white shadow-md' : 'text-slate-500 hover:bg-slate-50'}`}
                        >
                            Productos & Stock
                        </button>
                    </div>

                    <button
                        onClick={handleExportPDF}
                        disabled={isExporting}
                        className="px-5 py-2 flex items-center justify-center gap-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-sm tracking-wide rounded-2xl transition-all shadow-sm disabled:opacity-50"
                    >
                        {isExporting ? 'Procesando...' : <><Download size={18} /> Exportar PDF</>}
                    </button>
                </div>
            </div>

            {/* Content Container (For PDF Export Targeting) */}
            <div id="analytics-content" className="space-y-8 bg-slate-50 p-4 -m-4 rounded-3xl">

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <StatCard title="Leads Totales" value={data.leads.total.toString()} icon={<Users className="text-blue-600" />} color="bg-blue-50" />
                    <StatCard title="Tasa de Contacto" value={`${data.leads.conversion_rate}%`} subtitle={`${data.leads.contacted} contactados`} icon={<TrendingUp className="text-emerald-600" />} color="bg-emerald-50" />
                    <StatCard title="Nuevos Leads" value={data.leads.new.toString()} subtitle="Pendientes de asignación" icon={<MessageSquare className="text-orange-600" />} color="bg-orange-50" />
                    <StatCard title="Alertas de Stock" value={data.stock_alerts.length.toString()} subtitle="Productos bajo crítico" icon={<AlertTriangle className="text-red-600" />} color="bg-red-50" />
                </div>

                {activeTab === 'GENERAL' && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-in slide-in-from-left-4 fade-in duration-500">
                        {/* Seller Performance */}
                        <div className="bg-white p-8 rounded-[32px] shadow-md shadow-slate-200/40 border border-slate-100">
                            <div className="flex items-center justify-between mb-6">
                                <h3 className="text-xl font-black text-slate-900 italic flex items-center gap-2">
                                    <BarChart3 size={20} className="text-blue-600" />
                                    Gestión de Contactos por Vendedor
                                </h3>
                            </div>
                            <div className="space-y-6">
                                {data.sellers.length > 0 ? data.sellers.map((seller, idx) => (
                                    <div key={idx} className="space-y-2">
                                        <div className="flex justify-between text-sm font-bold">
                                            <span className="text-slate-700">{seller.email}</span>
                                            <span className="text-blue-600">{seller.count} leads</span>
                                        </div>
                                        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                            <div className="h-full bg-blue-600 transition-all" style={{ width: `${(seller.count / data.leads.total) * 100}%` }} />
                                        </div>
                                    </div>
                                )) : <p className="text-slate-400 italic text-sm">No hay datos.</p>}
                            </div>
                        </div>

                        {/* Sales by Seller */}
                        <div className="bg-white p-8 rounded-[32px] shadow-md shadow-slate-200/40 border border-slate-100">
                            <div className="flex items-center justify-between mb-6">
                                <h3 className="text-xl font-black text-slate-900 italic flex items-center gap-2">
                                    <ShoppingCart size={20} className="text-indigo-600" />
                                    Ventas Cerradas por Vendedor
                                </h3>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-left">
                                    <thead>
                                        <tr className="text-[10px] font-black uppercase tracking-widest text-slate-400 border-b border-slate-50">
                                            <th className="pb-4 px-4">Vendedor</th>
                                            <th className="pb-4 px-4 text-center">Cant. Ventas</th>
                                            <th className="pb-4 px-4 text-right">Monto Total</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-50">
                                        {data.seller_sales.map((s, idx) => (
                                            <tr key={idx} className="hover:bg-slate-50/50 transition-colors">
                                                <td className="py-4 px-4 font-bold text-slate-900">{s.seller}</td>
                                                <td className="py-4 px-4 text-center font-medium text-slate-600">{s.sales_count}</td>
                                                <td className="py-4 px-4 text-right font-black text-indigo-600">
                                                    $ {s.total_amount.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                                </td>
                                            </tr>
                                        ))}
                                        {data.seller_sales.length === 0 && (
                                            <tr><td colSpan={3} className="py-4 px-4 text-slate-400 italic text-sm text-center">Sin ventas.</td></tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Top Clients */}
                        <div className="bg-white p-8 rounded-[32px] shadow-md shadow-slate-200/40 border border-slate-100 lg:col-span-2">
                            <div className="flex items-center justify-between mb-6">
                                <h3 className="text-xl font-black text-slate-900 italic flex items-center gap-2">
                                    <Star size={20} className="text-yellow-500" />
                                    Top Clientes (Histórico General)
                                </h3>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {data.top_clients.map((c, idx) => (
                                    <div key={idx} className="flex items-center justify-between p-5 bg-slate-50 rounded-2xl hover:bg-slate-100 transition-colors">
                                        <div>
                                            <p className="font-bold text-slate-900 truncate max-w-[200px]" title={c.client_name}>{c.client_name}</p>
                                            <p className="text-xs font-bold text-slate-400 uppercase mt-1">{c.purchases} compras</p>
                                        </div>
                                        <div className="text-right flex-shrink-0 ml-2">
                                            <p className="font-black text-yellow-600 text-lg">
                                                $ {c.total_amount.toLocaleString('es-AR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                                            </p>
                                        </div>
                                    </div>
                                ))}
                                {data.top_clients.length === 0 && <p className="text-slate-400 italic text-sm">Sin compras.</p>}
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'MENSUAL' && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-in slide-in-from-right-4 fade-in duration-500">
                        {/* Leads per day */}
                        <div className="bg-white p-8 rounded-[32px] shadow-md shadow-blue-200/20 border border-blue-50 lg:col-span-2">
                            <div className="flex items-center justify-between mb-8">
                                <div>
                                    <h3 className="text-xl font-black text-slate-900 italic flex items-center gap-2">
                                        <CalendarDays size={20} className="text-blue-600" />
                                        Ingreso de Leads por Día (Mes Actual)
                                    </h3>
                                    <p className="text-sm text-slate-500 font-medium mt-1">
                                        Flujo de tráfico y alcance de las campañas.
                                    </p>
                                </div>
                            </div>
                            <div className="h-[350px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={data.monthly_metrics?.leads_per_day || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                        <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12, fontWeight: 'bold' }} dy={10} />
                                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12, fontWeight: 'bold' }} />
                                        <RechartsTooltip
                                            contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)', fontWeight: 'bold' }}
                                            cursor={{ fill: '#f8fafc', strokeWidth: 2 }}
                                        />
                                        <Line type="monotone" dataKey="leads" name="Nuevos Leads" stroke="#2563eb" strokeWidth={4} dot={{ r: 4, fill: '#2563eb', strokeWidth: 2, stroke: '#ffffff' }} activeDot={{ r: 6 }} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Top Monthly Interests */}
                        <div className="bg-white p-8 rounded-[32px] shadow-md shadow-orange-200/20 border border-orange-50">
                            <div className="flex items-center justify-between mb-8">
                                <div>
                                    <h3 className="text-xl font-black text-slate-900 italic flex items-center gap-2">
                                        <Package size={20} className="text-orange-600" />
                                        Más Pedidos del Mes
                                    </h3>
                                    <p className="text-sm text-slate-500 font-medium mt-1">Por cantidad de consultas (Interés).</p>
                                </div>
                            </div>
                            <div className="h-[350px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={data.monthly_metrics?.top_products_interest || []} layout="vertical" margin={{ top: 0, right: 30, left: -20, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                                        <XAxis type="number" hide />
                                        <YAxis dataKey="product" type="category" axisLine={false} tickLine={false} tick={{ fill: '#475569', fontSize: 11, fontWeight: '900' }} width={120} />
                                        <RechartsTooltip cursor={{ fill: '#f8fafc' }} contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                                        <Bar dataKey="count" name="Consultas" fill="#f97316" radius={[0, 4, 4, 0]} barSize={24} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Top Monthly Sold */}
                        <div className="bg-white p-8 rounded-[32px] shadow-md shadow-purple-200/20 border border-purple-50">
                            <div className="flex items-center justify-between mb-8">
                                <div>
                                    <h3 className="text-xl font-black text-slate-900 italic flex items-center gap-2">
                                        <ShoppingCart size={20} className="text-purple-600" />
                                        Más Vendidos del Mes
                                    </h3>
                                    <p className="text-sm text-slate-500 font-medium mt-1">Por unidades en ventas cerradas.</p>
                                </div>
                            </div>
                            <div className="h-[350px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={data.monthly_metrics?.top_products_sold || []} layout="vertical" margin={{ top: 0, right: 30, left: -20, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                                        <XAxis type="number" hide />
                                        <YAxis dataKey="product_name" type="category" axisLine={false} tickLine={false} tick={{ fill: '#475569', fontSize: 11, fontWeight: '900' }} width={150} />
                                        <RechartsTooltip cursor={{ fill: '#f8fafc' }} contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                                        <Bar dataKey="quantity_sold" name="Unidades" fill="#9333ea" radius={[0, 4, 4, 0]} barSize={24} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'PRODUCTOS' && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-in slide-in-from-right-4 fade-in duration-500">
                        {/* Categories of Interest */}
                        <div className="bg-white p-8 rounded-[32px] shadow-md shadow-emerald-200/20 border border-emerald-50">
                            <div className="flex items-center justify-between mb-6">
                                <h3 className="text-xl font-black text-slate-900 italic flex items-center gap-2">
                                    <TrendingUp size={20} className="text-emerald-600" />
                                    Histórico Interés por Categoría
                                </h3>
                            </div>
                            <div className="space-y-4">
                                {data.category_interest.map((cat, idx) => (
                                    <div key={idx} className="flex items-center justify-between p-4 bg-emerald-50/30 rounded-2xl">
                                        <span className="font-bold text-emerald-900 uppercase text-xs tracking-wider">{cat.category}</span>
                                        <div className="flex items-center gap-2">
                                            <span className="text-lg font-black text-emerald-700">{cat.count}</span>
                                            <span className="text-[10px] font-bold text-emerald-600/60 uppercase">Consultas</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Stock Alerts Table */}
                        <div className="bg-white p-8 rounded-[32px] shadow-md shadow-red-200/20 border border-red-50">
                            <div className="flex items-center justify-between mb-8">
                                <h3 className="text-xl font-black text-slate-900 italic flex items-center gap-2">
                                    <AlertTriangle size={20} className="text-red-600" />
                                    Alertas de Reposición (Stock Crítico)
                                </h3>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead>
                                        <tr className="text-left text-[10px] font-black uppercase tracking-widest text-slate-400 border-b border-slate-50">
                                            <th className="pb-4 px-4">SKU</th>
                                            <th className="pb-4 px-4">Producto</th>
                                            <th className="pb-4 px-4 text-center">Stock</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-50">
                                        {data.stock_alerts.map((item, idx) => (
                                            <tr key={idx} className="group hover:bg-slate-50/50 transition-colors">
                                                <td className="py-4 px-4 font-mono text-sm text-slate-500">{item.sku}</td>
                                                <td className="py-4 px-4 font-bold text-slate-900 max-w-[150px] truncate" title={item.name}>{item.name}</td>
                                                <td className="py-4 px-4 text-center">
                                                    <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase inline-block ${item.stock === 0 ? 'bg-red-100 text-red-600' : 'bg-orange-100 text-orange-600'}`}>
                                                        {item.stock} UNID.
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                        {data.stock_alerts.length === 0 && (
                                            <tr><td colSpan={3} className="py-8 text-center text-sm font-medium text-emerald-600">Todo el inventario cuenta con stock saludable. ✅</td></tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

function StatCard({ title, value, icon, color, subtitle }: { title: string; value: string; icon: React.ReactNode; color: string; subtitle?: string }) {
    return (
        <div className="bg-white p-6 rounded-[32px] shadow-sm border border-slate-100 flex flex-col justify-between">
            <div className="flex items-start justify-between mb-4">
                <div className={`p-3 ${color} rounded-2xl`}>
                    {icon}
                </div>
            </div>
            <div>
                <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-1">{title}</p>
                <p className="text-3xl font-black text-slate-900 italic tracking-tighter">{value}</p>
                {subtitle && <p className="text-xs text-slate-500 font-medium mt-1">{subtitle}</p>}
            </div>
        </div>
    );
}
