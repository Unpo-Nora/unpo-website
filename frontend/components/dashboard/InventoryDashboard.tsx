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
    Plus
} from 'lucide-react';
import ProductModal from './ProductModal';

interface Product {
    sku: string;
    name: string;
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
    const [syncing, setSyncing] = useState(false);
    // Search and Filter State
    const [searchTerm, setSearchTerm] = useState('');
    const [activeTab, setActiveTab] = useState<'con_stock' | 'sin_stock'>('con_stock');
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
    const fetchProducts = async () => {
        try {
            const token = localStorage.getItem('token');
            const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
            const apiUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/`;

            console.log("Fetching inventory from:", apiUrl);
            const response = await fetch(apiUrl, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            console.log("Inventory data received:", data.length, "items");
            setProducts(data);
            setLoading(false);
        } catch (error) {
            console.error("Error fetching products:", error);
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchProducts();
        fetchExchangeRate();
    }, []);

    const fetchExchangeRate = async () => {
        try {
            const token = localStorage.getItem('token');
            const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/settings/manual_exchange_rate`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setExchangeRate(data.value);
                setNewExchangeRate(data.value);
            }
        } catch (error) {
            console.error("Error fetching exchange rate:", error);
        }
    };

    const handleUpdateRate = async () => {
        const password = window.prompt("Por seguridad, ingresá tu contraseña para confirmar el cambio de Dólar:");
        if (!password) return;

        setSavingRate(true);
        try {
            const token = localStorage.getItem('token');
            const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/settings/manual_exchange_rate`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ value: newExchangeRate, password })
            });

            if (response.ok) {
                const data = await response.json();
                setExchangeRate(data.value);
                setMessage({ type: 'success', text: 'Cotización actualizada correctamente.' });
            } else {
                const errorData = await response.json();
                setMessage({ type: 'error', text: errorData.detail || "Error al actualizar." });
            }
        } catch (error) {
            setMessage({ type: 'error', text: "Error de red" });
        } finally {
            setSavingRate(false);
        }
    };

    const handleSync = async () => {
        if (!confirm("¿Estás seguro de sincronizar con el Excel maestro? Esto actualizará todos los precios y stocks.")) return;

        setSyncing(true);
        setMessage(null);
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/sync`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const result = await response.json();

            if (response.ok) {
                setMessage({
                    type: 'success',
                    text: `Sincronización exitosa: ${result.counts.created} nuevos, ${result.counts.updated} actualizados.`
                });
                fetchProducts();
            } else {
                setMessage({ type: 'error', text: result.detail || "Error en la sincronización" });
            }
        } catch (error) {
            setMessage({ type: 'error', text: "Error de conexión con el servidor" });
        } finally {
            setSyncing(false);
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

    const handleStockAdjust = async (e: React.MouseEvent, sku: string, adjustment: number) => {
        e.stopPropagation();
        
        // Optimistic update
        setProducts(prev => prev.map(p => {
            if (p.sku === sku) {
                return { ...p, stock_quantity: Math.max(0, p.stock_quantity + adjustment) };
            }
            return p;
        }));

        try {
            const token = localStorage.getItem('token');
            const apiUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/${sku}/stock`;
            const response = await fetch(apiUrl, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ adjustment })
            });

            if (!response.ok) {
                const errorData = await response.json();
                fetchProducts(); // Revert
                setMessage({ type: 'error', text: errorData.detail || 'Error al actualizar stock' });
            }
        } catch (error) {
            fetchProducts(); // Revert
            setMessage({ type: 'error', text: 'Error de red al actualizar stock' });
        }
    };

    // Filter by search term
    const searchedProducts = products.filter(p =>
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.sku.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // Filter by tab
    const tabFilteredProducts = searchedProducts.filter(p =>
        activeTab === 'con_stock' ? p.stock_quantity > 0 : p.stock_quantity <= 0
    );

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

    return (
        <div className="space-y-6">
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
                        onClick={handleUpdateRate}
                        disabled={savingRate || newExchangeRate === exchangeRate}
                        className="px-6 py-3 bg-slate-900 text-white rounded-2xl font-bold hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed transition-all whitespace-nowrap"
                    >
                        {savingRate ? '...' : 'Actualizar'}
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
                        onClick={handleCreateProduct}
                        className="flex items-center gap-2 px-6 py-3 rounded-2xl font-bold bg-green-600 text-white hover:bg-green-700 shadow-lg shadow-green-200 transition-all"
                    >
                        <Plus size={18} />
                        Nuevo Producto
                    </button>

                    <button
                        onClick={handleSync}
                        disabled={syncing}
                        className={`flex items-center gap-2 px-6 py-3 rounded-2xl font-bold transition-all ${syncing
                            ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                            : 'bg-blue-600 text-white hover:bg-blue-700 shadow-lg shadow-blue-200'
                            }`}
                    >
                        <RefreshCcw size={18} className={syncing ? 'animate-spin' : ''} />
                        {syncing ? 'Sincronizando...' : 'Excel'}
                    </button>
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
            <div className="flex border-b border-slate-200 gap-6 px-2">
                <button
                    onClick={() => setActiveTab('con_stock')}
                    className={`pb-4 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'con_stock' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                >
                    <Box size={16} />
                    Con Stock ({searchedProducts.filter(p => p.stock_quantity > 0).length})
                </button>
                <button
                    onClick={() => setActiveTab('sin_stock')}
                    className={`pb-4 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'sin_stock' ? 'border-red-600 text-red-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                >
                    <AlertTriangle size={16} />
                    Sin Stock ({searchedProducts.filter(p => p.stock_quantity <= 0).length})
                </button>
            </div>

            {/* Inventory Table */}
            <div className="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden flex flex-col">
                <div className="overflow-x_auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-slate-50/50 border-b border-slate-100">
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider text-center">SKU</th>
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider">Producto</th>
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider text-center">Stock</th>
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider text-right">Precio USD</th>
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider text-right">Precio ARS (Act.)</th>
                                <th className="px-6 py-5 text-[11px] font-bold text-slate-400 uppercase tracking-wider text-center">IVA</th>
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
                                            <div className="text-[10px] text-slate-400 mt-0.5 uppercase tracking-wide font-medium">{p.provider_name || 'Sin Proveedor'}</div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-5 text-center" onClick={(e) => e.stopPropagation()}>
                                        <div className="flex items-center justify-center gap-2">
                                            <button
                                                type="button"
                                                onClick={(e) => handleStockAdjust(e, p.sku, -1)}
                                                disabled={p.stock_quantity <= 0}
                                                className="w-7 h-7 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-600 flex items-center justify-center font-bold disabled:opacity-50 transition-colors"
                                            >
                                                -
                                            </button>
                                            <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${p.stock_quantity > 10
                                                ? 'bg-emerald-50 text-emerald-600'
                                                : p.stock_quantity > 0
                                                    ? 'bg-amber-50 text-amber-600'
                                                    : 'bg-red-50 text-red-600'
                                                }`}>
                                                <Box size={14} />
                                                {p.stock_quantity}
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
                                    <td className="px-6 py-5 text-right">
                                        <div className="text-sm font-bold text-slate-900 group-hover:text-green-600 transition-colors">
                                            US$ {p.price_usd ? Number(p.price_usd).toLocaleString() : 'N/A'}
                                        </div>
                                    </td>
                                    <td className="px-6 py-5 text-right">
                                        <div className="text-sm font-bold text-slate-500">
                                            ${p.price_usd && !isNaN(Number(exchangeRate)) ? (Number(p.price_usd) * Number(exchangeRate)).toLocaleString('es-AR', { maximumFractionDigits: 0 }) : 'N/A'}
                                        </div>
                                    </td>
                                    <td className="px-6 py-5 text-center">
                                        <span className="text-[10px] font-bold text-slate-500">{p.iva_percent}%</span>
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

            <ProductModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                onSave={handleModalSave}
                product={editingProduct}
            />
        </div >
    );
}
