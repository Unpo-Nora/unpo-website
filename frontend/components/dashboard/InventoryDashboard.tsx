"use client";

import React, { useState, useEffect } from 'react';
import {
    Package,
    RefreshCcw,
    Search,
    AlertTriangle,
    CheckCircle2,
    DollarSign,
    Box,
    Layers,
    Plus,
    Edit,
    History,
    TrendingUp,
    Wallet
} from 'lucide-react';
import ProductModal from './ProductModal';

interface Product {
    sku: string;
    name: string;
    description?: string;
    category_id: number;
    stock_quantity: number;
    price_wholesale: number;
    cost_price: number;
    price_usd: number;
    iva_percent: number;
    provider_name: string;
}

export default function InventoryDashboard() {
    const [products, setProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(true);

    // Search and Filter State
    const [searchTerm, setSearchTerm] = useState('');
    const [activeTab, setActiveTab] = useState<'con_stock' | 'stock_bajo' | 'sin_stock' | 'historial'>('con_stock');
    const [currentPage, setCurrentPage] = useState(1);
    const ITEMS_PER_PAGE = 10;

    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

    // Dolar Manual State
    const [exchangeRate, setExchangeRate] = useState<string>('Cargando...');
    const [newExchangeRate, setNewExchangeRate] = useState<string>('');
    const [savingRate, setSavingRate] = useState(false);

    // Modal State
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingProduct, setEditingProduct] = useState<Product | null>(null);

    // ... (fetchProducts, useEffect, fetchExchangeRate, handleUpdateRate, handleSync, handleEditProduct, handleCreateProduct, handleModalSave remain the same) ...
    // Batch Update State
    const [pendingStock, setPendingStock] = useState<Record<string, number>>({});
    const [pendingPrice, setPendingPrice] = useState<Record<string, number>>({});
    const [auditLogs, setAuditLogs] = useState<any[]>([]);

    const hasPendingChanges = Object.keys(pendingStock).length > 0 || Object.keys(pendingPrice).length > 0 || (newExchangeRate !== exchangeRate && newExchangeRate !== '');

    const fetchProducts = async () => {
        try {
            const token = localStorage.getItem('token');
            const apiUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/`;
            const response = await fetch(apiUrl, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            setProducts(data);
            setLoading(false);
        } catch (error) {
            setLoading(false);
        }
    };

    const fetchAuditLogs = async () => {
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/audit_logs?limit=50`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setAuditLogs(data);
            }
        } catch (error) {}
    };

    useEffect(() => {
        fetchProducts();
        fetchExchangeRate();
        fetchAuditLogs();
    }, []);

    const fetchExchangeRate = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/settings/manual_exchange_rate`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setExchangeRate(data.value);
                setNewExchangeRate(data.value);
            }
        } catch (error) {}
    };

    const handleBatchSave = async () => {
        if (!confirm("¿Estás seguro de guardar todos los cambios pendientes?")) return;

        setSavingRate(true);
        try {
            const token = localStorage.getItem('token');
            const apiUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/batch_update`;
            
            const payload = {
                stock_adjustments: pendingStock,
                price_updates: pendingPrice,
                new_exchange_rate: newExchangeRate !== exchangeRate ? newExchangeRate : null
            };

            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                setMessage({ type: 'success', text: 'Cambios guardados correctamente.' });
                setPendingStock({});
                setPendingPrice({});
                fetchProducts();
                fetchExchangeRate();
                fetchAuditLogs();
            } else {
                const errorData = await response.json();
                setMessage({ type: 'error', text: errorData.detail || "Error al guardar." });
            }
        } catch (error) {
            setMessage({ type: 'error', text: "Error de red" });
        } finally {
            setSavingRate(false);
        }
    };



    const handleEditProduct = (product: Product) => {
        setEditingProduct(product);
        setIsModalOpen(true);
    };

    const handleCreateProduct = () => {
        setEditingProduct(null);
        setIsModalOpen(true);
    };

    const handleModalSave = () => {
        fetchProducts(); // Refresh list after save or archive
    };

    const handleStockAdjust = (e: React.MouseEvent, sku: string, adjustment: number) => {
        e.stopPropagation();
        
        setPendingStock(prev => {
            const currentDelta = prev[sku] || 0;
            const p = products.find(x => x.sku === sku);
            const originalStock = p?.stock_quantity || 0;
            
            const newDelta = currentDelta + adjustment;
            
            // Prevent visual negative stock
            if (originalStock + newDelta < 0) return prev;
            
            const next = {...prev, [sku]: newDelta};
            if (newDelta === 0) delete next[sku];
            return next;
        });
    };

    const handlePriceChange = (e: React.ChangeEvent<HTMLInputElement>, sku: string) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val)) {
            setPendingPrice(prev => {
                const p = products.find(x => x.sku === sku);
                if (p && val === p.price_usd) {
                    const next = {...prev};
                    delete next[sku];
                    return next;
                }
                return {...prev, [sku]: val};
            });
        } else if (e.target.value === '') {
            // Allow temporary empty string during typing
        }
    };

    // Filter by search term
    const searchedProducts = products.filter(p =>
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.sku.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // Filter by tab
    const tabFilteredProducts = searchedProducts.filter(p => {
        if (activeTab === 'con_stock') return p.stock_quantity >= 10;
        if (activeTab === 'stock_bajo') return p.stock_quantity > 0 && p.stock_quantity < 10;
        if (activeTab === 'sin_stock') return p.stock_quantity <= 0;
        return false;
    });

    // Pagination
    const totalPages = Math.ceil(tabFilteredProducts.length / ITEMS_PER_PAGE) || 1;
    const paginatedProducts = tabFilteredProducts.slice(
        (currentPage - 1) * ITEMS_PER_PAGE,
        currentPage * ITEMS_PER_PAGE
    );

    // Reset pagination when tab or search changes
    useEffect(() => {
        setCurrentPage(1);
    }, [activeTab, searchTerm]);

    if (loading) return (
        <div className="bg-white rounded-3xl p-12 flex flex-col items-center justify-center border border-slate-100 shadow-sm">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
            <p className="text-slate-500 font-medium">Cargando catálogo...</p>
        </div>
    );

    const totalCostValue = products.reduce((acc, p) => acc + ((p.cost_price || 0) * (p.stock_quantity > 0 ? p.stock_quantity : 0)), 0);
    const totalSaleValue = products.reduce((acc, p) => acc + ((p.price_usd || 0) * (p.stock_quantity > 0 ? p.stock_quantity : 0)), 0);

    return (
        <div className="space-y-6">
            {/* Value Check Summary */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white rounded-3xl p-6 border border-slate-100 shadow-sm flex items-center justify-between">
                    <div>
                        <p className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-1">Valor de Costo Invertido</p>
                        <h3 className="text-3xl font-black text-slate-800">U$D {totalCostValue.toLocaleString('es-AR', { maximumFractionDigits: 2 })}</h3>
                    </div>
                    <div className="w-14 h-14 bg-indigo-50 text-indigo-500 rounded-2xl flex items-center justify-center">
                        <Wallet size={28} />
                    </div>
                </div>
                <div className="bg-white rounded-3xl p-6 border border-slate-100 shadow-sm flex items-center justify-between">
                    <div>
                        <p className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-1">Valor de Venta Estimado</p>
                        <h3 className="text-3xl font-black text-emerald-600">U$D {totalSaleValue.toLocaleString('es-AR', { maximumFractionDigits: 2 })}</h3>
                    </div>
                    <div className="w-14 h-14 bg-emerald-50 text-emerald-500 rounded-2xl flex items-center justify-center">
                        <TrendingUp size={28} />
                    </div>
                </div>
            </div>
            {/* Pending Changes Action Bar */}
            {hasPendingChanges && (
                <div className="sticky top-4 z-40 bg-blue-600 rounded-2xl p-4 shadow-xl shadow-blue-200/50 flex flex-col md:flex-row items-center justify-between gap-4 border border-blue-500 text-white animate-in slide-in-from-top-4">
                    <div className="flex items-center gap-3">
                        <AlertTriangle className="text-blue-200" size={24} />
                        <div>
                            <h3 className="font-bold text-lg">Tienes cambios sin guardar</h3>
                            <p className="text-blue-100 text-sm">Hay ajustes de stock, precios o cotización del dólar pendientes de confirmación.</p>
                        </div>
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={() => {
                                setPendingStock({});
                                setPendingPrice({});
                                setNewExchangeRate(exchangeRate);
                            }}
                            className="px-4 py-3 bg-blue-700 hover:bg-blue-800 text-white rounded-xl font-bold transition-all"
                        >
                            Descartar
                        </button>
                        <button
                            onClick={handleBatchSave}
                            disabled={savingRate}
                            className="px-6 py-3 bg-white text-blue-600 rounded-xl font-black hover:bg-blue-50 shadow-md transition-all disabled:opacity-50"
                        >
                            {savingRate ? 'Guardando...' : 'GUARDAR CAMBIOS'}
                        </button>
                    </div>
                </div>
            )}

            {/* Audit Logs Box - Removed from top, moved to tab */}

            {/* Settings Card: Exchange Rate */}
            <div className="bg-white rounded-3xl p-6 border border-slate-100 shadow-sm flex flex-col md:flex-row items-center justify-between gap-6">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-green-50 text-green-600 flex items-center justify-center">
                        <DollarSign size={24} />
                    </div>
                    <div>
                        <h3 className="font-bold text-slate-800 text-lg">Cotización Base (Dólar UNPO)</h3>
                        <p className="text-sm text-slate-500">Valor actual en catálogo: <span className="font-bold text-slate-700">${exchangeRate}</span> ARS</p>
                    </div>
                </div>

                <div className="flex items-center gap-3 w-full md:w-auto">
                    <div className="relative">
                        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 font-bold">$</span>
                        <input
                            type="number"
                            value={newExchangeRate}
                            onChange={(e) => setNewExchangeRate(e.target.value)}
                            className="w-full md:w-32 pl-8 pr-4 py-3 bg-slate-50 border-2 border-transparent rounded-2xl focus:border-green-500 outline-none text-slate-700 font-bold"
                            placeholder="Ej: 1450"
                        />
                    </div>
                    <button
                        disabled={savingRate || newExchangeRate === exchangeRate}
                        className="px-6 py-3 bg-slate-900 text-white rounded-2xl font-bold disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed transition-all whitespace-nowrap"
                    >
                        {newExchangeRate !== exchangeRate ? 'Pendiente' : 'Al día'}
                    </button>
                </div>
            </div>

            {/* Action Bar */}
            <div className="flex flex-col md:flex-row gap-4 justify-between items-center bg-white p-6 rounded-3xl border border-slate-100 shadow-sm">
                <div className="relative flex-1 max-w-md w-full">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                    <input
                        type="text"
                        placeholder="Buscar por SKU o nombre..."
                        className="w-full pl-12 pr-6 py-3 bg-slate-50 border-none rounded-2xl focus:ring-2 focus:ring-blue-500/20 transition-all outline-none text-slate-700"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>

                <div className="flex items-center gap-3">
                    <button
                        onClick={fetchProducts}
                        className="flex items-center gap-2 px-6 py-3 rounded-2xl font-bold bg-slate-100 text-slate-600 hover:bg-slate-200 transition-all"
                    >
                        <RefreshCcw size={18} />
                        Actualizar
                    </button>
                    {/* Boton Nuevo Producto movido a Compras */}
                </div>
            </div>

            {message && (
                <div className={`p-4 rounded-2xl flex items-center gap-3 border ${message.type === 'success' ? 'bg-emerald-50 border-emerald-100 text-emerald-700' : 'bg-red-50 border-red-100 text-red-700'
                    }`}>
                    {message.type === 'success' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
                    <span className="font-medium text-sm">{message.text}</span>
                </div>
            )}

            {/* Tabs */}
            <div className="flex border-b border-slate-200 gap-6 px-2 overflow-x-auto shrink-0">
                <button
                    onClick={() => setActiveTab('con_stock')}
                    className={`pb-4 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${activeTab === 'con_stock' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                >
                    <Box size={16} />
                    Con Stock ({searchedProducts.filter(p => p.stock_quantity >= 10).length})
                </button>
                <button
                    onClick={() => setActiveTab('stock_bajo')}
                    className={`pb-4 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${activeTab === 'stock_bajo' ? 'border-amber-500 text-amber-500' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                >
                    <AlertTriangle size={16} />
                    Stock Bajo ({searchedProducts.filter(p => p.stock_quantity > 0 && p.stock_quantity < 10).length})
                </button>
                <button
                    onClick={() => setActiveTab('sin_stock')}
                    className={`pb-4 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${activeTab === 'sin_stock' ? 'border-red-600 text-red-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                >
                    <AlertTriangle size={16} />
                    Sin Stock ({searchedProducts.filter(p => p.stock_quantity <= 0).length})
                </button>
                <button
                    onClick={() => setActiveTab('historial')}
                    className={`pb-4 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${activeTab === 'historial' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                >
                    <History size={16} />
                    Historial de Modificaciones
                </button>
            </div>

            {activeTab === 'historial' ? (
                <div className="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden flex flex-col">
                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="bg-slate-50/50 border-b border-slate-100">
                                    <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider">Fecha</th>
                                    <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider">Usuario</th>
                                    <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider">Acción</th>
                                    <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider">Detalles</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {auditLogs.length > 0 ? auditLogs.map(log => (
                                    <tr key={log.id} className="hover:bg-slate-50/50">
                                        <td className="px-6 py-4 text-sm font-medium text-slate-500 whitespace-nowrap">
                                            {new Date(log.created_at).toLocaleString('es-AR')}
                                        </td>
                                        <td className="px-6 py-4 text-sm font-bold text-slate-700">
                                            {log.user_email}
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-slate-100 text-slate-600">
                                                {log.action}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-sm text-slate-700">
                                            {log.details}
                                        </td>
                                    </tr>
                                )) : (
                                    <tr><td colSpan={4} className="px-6 py-12 text-center text-slate-500">No hay registros recientes.</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            ) : (
            <div className="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden flex flex-col">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-slate-50/50 border-b border-slate-100">
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider text-center">SKU</th>
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider">Producto</th>
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider text-center">Stock</th>
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider text-right">Precio USD</th>
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider text-right">Precio ARS (Act.)</th>
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider text-center">IVA</th>
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider text-center">Acciones</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {paginatedProducts.map((p) => (
                                <tr
                                    key={p.sku}
                                    onClick={() => handleEditProduct(p)}
                                    className="hover:bg-slate-50/50 transition-colors group cursor-pointer"
                                >
                                    <td className="px-6 py-5 text-center">
                                        <span className="text-[11px] font-mono font-bold text-slate-400 bg-slate-100 px-2 py-1 rounded">
                                            {p.sku}
                                        </span>
                                    </td>
                                    <td className="px-6 py-5">
                                        <div>
                                            <div className="font-bold text-slate-800 text-sm group-hover:text-blue-600 transition-colors">{p.name}</div>
                                            {p.description && (
                                                <div className="text-[11px] text-slate-500 mt-1 line-clamp-2 leading-relaxed max-w-sm">{p.description}</div>
                                            )}
                                            <div className="text-[10px] text-slate-400 mt-1.5 uppercase tracking-wide font-medium">{p.provider_name || 'Sin Proveedor'}</div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-5 text-center" onClick={(e) => e.stopPropagation()}>
                                        <div className="flex items-center justify-center gap-2">
                                            <button
                                                type="button"
                                                onClick={(e) => handleStockAdjust(e, p.sku, -1)}
                                                disabled={p.stock_quantity + (pendingStock[p.sku] || 0) <= 0}
                                                className="w-7 h-7 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-600 flex items-center justify-center font-bold disabled:opacity-50 transition-colors"
                                            >
                                                -
                                            </button>
                                            <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${p.stock_quantity + (pendingStock[p.sku] || 0) > 10
                                                ? 'bg-emerald-50 text-emerald-600'
                                                : p.stock_quantity + (pendingStock[p.sku] || 0) > 0
                                                    ? 'bg-amber-50 text-amber-600'
                                                    : 'bg-red-50 text-red-600'
                                                }`}>
                                                <Box size={14} />
                                                {p.stock_quantity + (pendingStock[p.sku] || 0)}
                                            </div>
                                            <button
                                                type="button"
                                                onClick={(e) => handleStockAdjust(e, p.sku, 1)}
                                                className="w-7 h-7 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-600 flex items-center justify-center font-bold transition-colors"
                                            >
                                                +
                                            </button>
                                        </div>
                                    </td>
                                    <td className="px-6 py-5 text-right" onClick={(e) => e.stopPropagation()}>
                                        <div className="relative flex items-center justify-end font-bold">
                                            <span className="text-slate-400 mr-1">US$</span>
                                            <input 
                                                type="number"
                                                step="0.01"
                                                min="0"
                                                value={pendingPrice[p.sku] !== undefined ? pendingPrice[p.sku] : p.price_usd}
                                                onChange={(e) => handlePriceChange(e, p.sku)}
                                                className={`w-20 text-right bg-transparent border-b-2 outline-none transition-colors ${pendingPrice[p.sku] !== undefined ? 'border-amber-400 text-amber-600' : 'border-transparent text-slate-900 focus:border-blue-300'}`}
                                            />
                                        </div>
                                    </td>
                                    <td className="px-6 py-5 text-right">
                                        <div className="text-sm font-bold text-slate-500">
                                            ${p.price_usd && !isNaN(Number(newExchangeRate)) ? (Number(pendingPrice[p.sku] !== undefined ? pendingPrice[p.sku] : p.price_usd) * Number(newExchangeRate)).toLocaleString('es-AR', { maximumFractionDigits: 0 }) : 'N/A'}
                                        </div>
                                    </td>
                                    <td className="px-6 py-5 text-center">
                                        <span className="text-[10px] font-bold text-slate-500">{p.iva_percent}%</span>
                                    </td>
                                    <td className="px-6 py-5 text-center" onClick={(e) => { e.stopPropagation(); handleEditProduct(p); }}>
                                        <button
                                            type="button"
                                            className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-colors inline-flex items-center justify-center"
                                            title="Editar Producto"
                                        >
                                            <Edit size={16} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Pagination Controls */}
                <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between">
                    <span className="text-sm font-bold text-slate-500">
                        Mostrando {paginatedProducts.length} de {tabFilteredProducts.length}
                    </span>
                    <div className="flex items-center gap-2">
                        <button
                            disabled={currentPage === 1}
                            onClick={(e) => { e.stopPropagation(); setCurrentPage(1) }}
                            className="px-3 py-2 bg-white border border-slate-200 text-slate-600 rounded-lg text-sm font-bold hover:bg-slate-50 disabled:opacity-50 transition-colors"
                            title="Primera página"
                        >
                            &laquo;
                        </button>
                        <button
                            disabled={currentPage === 1}
                            onClick={(e) => { e.stopPropagation(); setCurrentPage(prev => Math.max(1, prev - 1)) }}
                            className="px-4 py-2 bg-white border border-slate-200 text-slate-600 rounded-lg text-sm font-bold hover:bg-slate-50 disabled:opacity-50 transition-colors"
                        >
                            Anterior
                        </button>
                        <span className="px-4 py-2 text-sm font-bold text-slate-700">
                            Página {currentPage} de {totalPages}
                        </span>
                        <button
                            disabled={currentPage === totalPages}
                            onClick={(e) => { e.stopPropagation(); setCurrentPage(prev => Math.min(totalPages, prev + 1)) }}
                            className="px-4 py-2 bg-white border border-slate-200 text-slate-600 rounded-lg text-sm font-bold hover:bg-slate-50 disabled:opacity-50 transition-colors"
                        >
                            Siguiente
                        </button>
                        <button
                            disabled={currentPage === totalPages}
                            onClick={(e) => { e.stopPropagation(); setCurrentPage(totalPages) }}
                            className="px-3 py-2 bg-white border border-slate-200 text-slate-600 rounded-lg text-sm font-bold hover:bg-slate-50 disabled:opacity-50 transition-colors"
                            title="Última página"
                        >
                            &raquo;
                        </button>
                    </div>
                </div>
            </div>
            )}

            <ProductModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                onSave={handleModalSave}
                product={editingProduct}
            />
        </div >
    );
}
