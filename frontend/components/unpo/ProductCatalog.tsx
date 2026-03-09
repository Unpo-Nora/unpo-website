"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { Search, Package, ShoppingCart, Filter, ArrowRight, ListFilter, X, ChevronRight, Hash } from 'lucide-react';
import ProductModal from './ProductModal';

interface Category {
    id: number;
    name: string;
}

interface Product {
    sku: string;
    name: string;
    price_wholesale: number;
    price_usd: number;
    stock_quantity: number;
    category_id?: number;
    provider_name?: string;
    description?: string;
    images?: string[];
}

export default function ProductCatalog() {
    const [products, setProducts] = useState<Product[]>([]);
    const [categories, setCategories] = useState<Category[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
    const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [exchangeRate, setExchangeRate] = useState<number>(1450); // Default fallback

    const fetchExchangeRate = async () => {
        try {
            const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
            const response = await fetch(`http://${host}:8000/settings/manual_exchange_rate`);
            if (response.ok) {
                const data = await response.json();
                setExchangeRate(Number(data.value));
            }
        } catch (error) {
            console.error("Error fetching exchange rate:", error);
        }
    };

    const fetchCategories = async () => {
        try {
            const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
            const response = await fetch(`http://${host}:8000/products/categories`);
            if (response.ok) {
                const data = await response.json();
                setCategories(data);
            }
        } catch (error) {
            console.error("Error fetching categories:", error);
        }
    };

    const fetchProducts = async () => {
        try {
            setLoading(true);
            const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
            // Fetch more products to handle local filtering better if needed, 
            // but the user wants it organized.
            let apiUrl = `http://${host}:8000/products/?limit=200`;

            const response = await fetch(apiUrl);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const data = await response.json();
            setProducts(Array.isArray(data) ? data : []);
            setLoading(false);
        } catch (error) {
            console.error("Error fetching catalog:", error);
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchExchangeRate();
        fetchCategories();
        fetchProducts();
    }, []);

    // Local filtering for better UX responsiveness, excluding out of stock items
    const filteredProducts = useMemo(() => {
        return products.filter(p => {
            const hasStock = p.stock_quantity > 0;
            const matchesSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase());
            const matchesCategory = selectedCategoryId ? p.category_id === selectedCategoryId : true;
            return hasStock && matchesSearch && matchesCategory;
        });
    }, [products, searchTerm, selectedCategoryId]);

    // Only show categories that have products in the current list
    const activeCategories = useMemo(() => {
        const productCategoryIds = new Set(products.map(p => p.category_id));
        return categories.filter(cat => productCategoryIds.has(cat.id));
    }, [categories, products]);

    const getCategoryName = (id?: number) => {
        return categories.find(c => c.id === id)?.name || "General";
    };

    const handleCategoryChange = (categoryId: number | null) => {
        setSelectedCategoryId(categoryId);
        const catalogElement = document.getElementById('catalog');
        if (catalogElement) {
            catalogElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };

    return (
        <section id="catalog" className="py-24 bg-slate-50 scroll-mt-24 border-y border-slate-200">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                {/* Header Section */}
                <div className="flex flex-col md:flex-row md:items-end justify-between mb-16 gap-8">
                    <div className="max-w-2xl">
                        <div className="inline-flex items-center gap-2 px-3 py-1 bg-blue-100 text-blue-700 text-[10px] font-black uppercase tracking-widest rounded-full mb-4">
                            <Hash size={12} />
                            Inventario en tiempo real
                        </div>
                        <h2 className="text-4xl md:text-5xl font-black text-slate-900 tracking-tighter italic">
                            NUESTRO <span className="text-blue-600">CATÁLOGO</span>
                        </h2>
                        <p className="text-slate-500 mt-4 text-lg font-medium max-w-lg leading-relaxed">
                            Stock inmediato y precios actualizados para distribuidores mayoristas en todo el país.
                        </p>
                    </div>

                    <div className="relative w-full md:w-96 shadow-2xl shadow-blue-100">
                        <Search className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                        <input
                            type="text"
                            placeholder="Buscar por nombre..."
                            className="w-full pl-14 pr-6 py-5 bg-white border-2 border-transparent rounded-[24px] focus:border-blue-500 transition-all outline-none text-slate-700 font-bold shadow-sm placeholder:text-slate-300"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                        {searchTerm && (
                            <button
                                onClick={() => setSearchTerm('')}
                                className="absolute right-5 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500 transition-colors"
                            >
                                <X size={20} />
                            </button>
                        )}
                    </div>
                </div>

                <div className="flex flex-col lg:flex-row gap-12">
                    {/* Filter Sidebar (Desktop) / Filter Bar (Mobile) */}
                    <div className="w-full lg:w-64 flex-shrink-0">
                        <div className="sticky top-32">
                            <div className="flex items-center gap-2 mb-6 text-slate-900 font-black uppercase tracking-widest text-sm">
                                <ListFilter size={18} className="text-blue-600" />
                                Filtrar Categoría
                            </div>

                            <div className="flex flex-row lg:flex-col gap-2 overflow-x-auto lg:overflow-visible pb-4 lg:pb-0 scrollbar-hide">
                                <button
                                    onClick={() => handleCategoryChange(null)}
                                    className={`flex-shrink-0 px-5 py-3 rounded-2xl text-sm font-black transition-all text-left flex items-center justify-between group ${!selectedCategoryId ? 'bg-blue-600 text-white shadow-xl shadow-blue-200' : 'bg-white text-slate-500 border border-slate-100 hover:border-blue-200 hover:text-blue-600 hover:translate-x-1'}`}
                                >
                                    <span>Todos</span>
                                    {!selectedCategoryId && <ChevronRight size={14} />}
                                </button>

                                {activeCategories.map((cat) => (
                                    <button
                                        key={cat.id}
                                        onClick={() => handleCategoryChange(cat.id)}
                                        className={`flex-shrink-0 px-5 py-3 rounded-2xl text-sm font-black transition-all text-left flex items-center justify-between group ${selectedCategoryId === cat.id ? 'bg-blue-600 text-white shadow-xl shadow-blue-200' : 'bg-white text-slate-500 border border-slate-100 hover:border-blue-200 hover:text-blue-600 hover:translate-x-1'}`}
                                    >
                                        <span className="truncate pr-2">{cat.name}</span>
                                        {selectedCategoryId === cat.id && <ChevronRight size={14} />}
                                    </button>
                                ))}
                            </div>

                            <div className="mt-8 hidden lg:block p-6 bg-slate-900 rounded-[32px] text-white">
                                <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">Ayuda</p>
                                <p className="text-xs font-medium leading-relaxed mb-4">¿No encontrás lo que buscás? Consultanos vía WhatsApp.</p>
                                <a
                                    href="#contact"
                                    className="inline-flex items-center gap-2 text-xs font-black text-blue-400 hover:text-blue-300 transition-colors uppercase tracking-widest"
                                >
                                    Contactar ahora
                                    <ArrowRight size={12} />
                                </a>
                            </div>
                        </div>
                    </div>

                    {/* Products Grid */}
                    <div className="flex-1 min-h-[80vh]">
                        {loading ? (
                            <div className="flex flex-col items-center justify-center py-32 space-y-6">
                                <div className="relative">
                                    <div className="w-16 h-16 border-4 border-blue-100 border-t-blue-600 rounded-full animate-spin"></div>
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <Package size={24} className="text-blue-600" />
                                    </div>
                                </div>
                                <p className="text-slate-400 font-black uppercase tracking-widest text-xs">Sincronizando Stock...</p>
                            </div>
                        ) : filteredProducts.length > 0 ? (
                            <div>
                                <div className="mb-8 flex items-center justify-between">
                                    <p className="text-slate-400 text-sm font-bold">
                                        Mostrando <span className="text-slate-900">{filteredProducts.length}</span> productos
                                        {selectedCategoryId && <> en <span className="text-blue-600">{getCategoryName(selectedCategoryId)}</span></>}
                                    </p>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
                                    {filteredProducts.map((product) => (
                                        <div
                                            key={product.sku}
                                            onClick={() => {
                                                setSelectedProduct(product);
                                                setIsModalOpen(true);
                                            }}
                                            className="bg-white rounded-[32px] border border-slate-100 shadow-sm hover:shadow-2xl hover:shadow-blue-500/10 transition-all duration-500 group overflow-hidden flex flex-col h-full active:scale-[0.98] cursor-pointer"
                                        >
                                            {/* Image Container */}
                                            <div className="aspect-square relative overflow-hidden bg-slate-50">
                                                {product.images?.[0] ? (
                                                    <img
                                                        src={(() => {
                                                            const currentHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
                                                            const baseUrl = `http://${currentHost}:8000`;
                                                            return product.images[0].startsWith('http')
                                                                ? product.images[0]
                                                                : `${baseUrl}${product.images[0]}`;
                                                        })()}
                                                        alt={product.name}
                                                        className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700"
                                                        onError={(e) => {
                                                            const target = e.target as HTMLImageElement;
                                                            target.src = 'https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?q=80&w=400';
                                                        }}
                                                    />
                                                ) : (
                                                    <div className="w-full h-full flex items-center justify-center text-slate-200">
                                                        <Package size={64} strokeWidth={1} />
                                                    </div>
                                                )}

                                                {/* Category Tag Overlay */}
                                                <div className="absolute top-4 left-4">
                                                    <span className="px-3 py-1 bg-white/90 backdrop-blur-sm text-slate-900 text-[10px] font-black uppercase tracking-widest rounded-full shadow-sm">
                                                        {getCategoryName(product.category_id)}
                                                    </span>
                                                </div>
                                            </div>

                                            <div className="p-8 flex flex-col flex-1">
                                                <h3 className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors mb-3 line-clamp-2 min-h-[3rem] text-lg tracking-tight">
                                                    {product.name}
                                                </h3>

                                                <p className="text-slate-500 text-sm line-clamp-3 mb-8 font-medium leading-relaxed">
                                                    {product.description || 'Consulta detalles técnicos y embalaje con un asesor de ventas especializado.'}
                                                </p>

                                                <div className="mt-auto flex flex-col justify-end pt-5 border-t border-slate-50 gap-2">
                                                    <div>
                                                        <p className="text-[10px] text-slate-400 font-black uppercase tracking-[0.2em] mb-1">PRECIO MAYORISTA UNITARIO</p>

                                                        {product.price_usd ? (
                                                            <div className="flex flex-col">
                                                                <div className="flex items-baseline gap-1">
                                                                    <span className="text-xl font-black text-slate-900 tracking-tighter italic">US$ {product.price_usd}</span>
                                                                    <span className="text-[10px] font-bold text-slate-400">+ IVA</span>
                                                                </div>
                                                                <span className="text-xs font-bold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md inline-block max-w-max mt-1">
                                                                    Aprox. ${(product.price_usd * exchangeRate).toLocaleString('es-AR', { maximumFractionDigits: 0 })} ARS
                                                                </span>
                                                            </div>
                                                        ) : (
                                                            <p className="text-xl font-black text-slate-900 tracking-tighter italic">
                                                                ${Number(product.price_wholesale).toLocaleString()} <span className="text-[10px] font-bold text-slate-400 not-italic">+ IVA</span>
                                                            </p>
                                                        )}
                                                    </div>
                                                    {product.stock_quantity > 0 ? (
                                                        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 text-emerald-600 text-[10px] font-black uppercase tracking-widest rounded-xl border border-emerald-100">
                                                            <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></div>
                                                            STOCK
                                                        </div>
                                                    ) : (
                                                        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 text-slate-400 text-[10px] font-black uppercase tracking-widest rounded-xl border border-slate-200">
                                                            <div className="w-1.5 h-1.5 bg-slate-300 rounded-full"></div>
                                                            SIN STOCK
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center py-32 bg-white rounded-[40px] border border-dashed border-slate-200">
                                <div className="p-6 bg-slate-50 rounded-full mb-6">
                                    <Search className="text-slate-300" size={48} />
                                </div>
                                <h3 className="text-2xl font-black text-slate-900 tracking-tighter italic uppercase mb-2">Sin resultados</h3>
                                <p className="text-slate-400 font-medium mb-8">No encontramos productos que coincidan con tu búsqueda.</p>
                                <button
                                    onClick={() => { setSearchTerm(''); setSelectedCategoryId(null); }}
                                    className="px-8 py-3 bg-blue-600 text-white text-sm font-black rounded-2xl shadow-xl shadow-blue-100 hover:scale-105 transition-all"
                                >
                                    VER TODOS LOS PRODUCTOS
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <ProductModal
                product={selectedProduct}
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                categoryName={getCategoryName(selectedProduct?.category_id)}
            />
        </section>
    );
}
