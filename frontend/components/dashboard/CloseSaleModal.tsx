"use client";

import React, { useState, useEffect } from 'react';
import { X, ShoppingCart, Truck, CheckCircle2, Package, Search, ChevronRight, User } from 'lucide-react';

interface Product {
    sku: string;
    name: string;
    price_wholesale: number;
    stock_quantity: number;
    images?: string[];
}

interface OrderItem {
    product_sku: string;
    quantity: number;
    unit_price: number;
    total_price: number;
    product_name: string;
    product_image?: string;
}

interface CloseSaleModalProps {
    lead: any;
    onClose: () => void;
    onSuccess: (orderId: number) => void;
}

export default function CloseSaleModal({ lead, onClose, onSuccess }: CloseSaleModalProps) {
    const [step, setStep] = useState<1 | 2>(1);
    const [products, setProducts] = useState<Product[]>([]);
    const [searchTerm, setSearchTerm] = useState("");
    const [cart, setCart] = useState<OrderItem[]>([]);

    // Step 2 Form State
    const [formData, setFormData] = useState({
        dni_cuit: lead.dni_cuit || "",
        address: lead.address || "",
        locality: lead.locality || "",
        province: lead.province || "",
        zip_code: lead.zip_code || "",
        transport_name: "",
        transport_dni: "",
        license_plate: "",
        delivery_address: "",
        delivery_date: ""
    });

    const [loading, setLoading] = useState(false);

    useEffect(() => {
        fetchProducts();
    }, []);

    const fetchProducts = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/?limit=1000`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            setProducts(data);
        } catch (error) {
            console.error("Error fetching products:", error);
        }
    };

    const handleAddToCart = (item: Product) => {
        if (item.stock_quantity <= 0) return;
        const price = Number(item.price_wholesale) || 0;
        const existing = cart.find(c => c.product_sku === item.sku);
        if (existing) {
            if (existing.quantity >= item.stock_quantity) return; // cannot exceed stock
            setCart(cart.map(c =>
                c.product_sku === item.sku
                    ? { ...c, quantity: c.quantity + 1, total_price: (c.quantity + 1) * price }
                    : c
            ));
        } else {
            const imgUrl = item.images && item.images.length > 0 ? item.images[0] : undefined;
            setCart([...cart, {
                product_sku: item.sku,
                product_name: item.name,
                product_image: imgUrl,
                quantity: 1,
                unit_price: price,
                total_price: price
            }]);
        }
    };

    const handleRemoveFromCart = (sku: string) => {
        const existing = cart.find(c => c.product_sku === sku);
        if (existing && existing.quantity > 1) {
            setCart(cart.map(c =>
                c.product_sku === sku
                    ? { ...c, quantity: c.quantity - 1, total_price: (c.quantity - 1) * c.unit_price }
                    : c
            ));
        } else {
            setCart(cart.filter(c => c.product_sku !== sku));
        }
    };

    const totalAmount = cart.reduce((acc, current) => acc + current.total_price, 0);
    const minMonto = 100000;
    const canProceed = totalAmount >= minMonto;

    const filteredProducts = products.filter(p =>
        p.stock_quantity > 0 &&
        (p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            p.sku.toLowerCase().includes(searchTerm.toLowerCase()))
    );

    const handleSubmit = async () => {
        if (!formData.dni_cuit.trim() || !formData.address.trim() || !formData.locality.trim() || !formData.province.trim() || !formData.zip_code.trim()) {
            alert("Error: Por favor completa todos los Datos de Facturación del cliente (DNI/CUIT, Dirección, Localidad, C.P, Provincia).");
            return;
        }

        setLoading(true);
        try {
            const payload = {
                lead_id: lead.id,
                total_amount: totalAmount,
                status: "COMPLETED",
                ...formData,
                items: cart.map(c => ({
                    product_sku: c.product_sku,
                    quantity: c.quantity,
                    unit_price: c.unit_price,
                    total_price: c.total_price
                }))
            };

            const token = localStorage.getItem('token');
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/sales/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const orderData = await response.json();

                // Immediately trigger PDF download safely
                window.open(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/sales/${orderData.id}/pdf`, '_blank');

                onSuccess(orderData.id);
            } else {
                const err = await response.json();
                alert(`Error: ${err.detail}`);
            }
        } catch (error) {
            console.error("Error creating sale:", error);
            alert("Error de conexión");
        } finally {
            setLoading(false);
        }
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-slate-900/80 backdrop-blur-sm" onClick={onClose}></div>
            <div className="relative bg-white w-full max-w-5xl h-[90vh] rounded-[32px] shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-300 flex flex-col">

                {/* Header */}
                <div className="px-8 py-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50 shrink-0">
                    <div>
                        <h3 className="text-2xl font-black text-slate-900">Cerrar Venta</h3>
                        <p className="text-slate-500 font-medium">Cliente: <span className="text-blue-600">{lead.full_name}</span></p>
                    </div>

                    <div className="flex items-center gap-8">
                        {/* Stepper */}
                        <div className="flex items-center gap-4">
                            <div className={`flex items-center gap-2 ${step === 1 ? 'text-blue-600' : 'text-slate-400'}`}>
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${step === 1 ? 'bg-blue-100 text-blue-700' : 'bg-slate-100'}`}>1</div>
                                <span className="font-bold text-sm">Productos</span>
                            </div>
                            <div className="w-8 h-px bg-slate-200"></div>
                            <div className={`flex items-center gap-2 ${step === 2 ? 'text-blue-600' : 'text-slate-400'}`}>
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${step === 2 ? 'bg-blue-100 text-blue-700' : 'bg-slate-100'}`}>2</div>
                                <span className="font-bold text-sm">Envío y Facturación</span>
                            </div>
                        </div>

                        <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full transition-colors text-slate-400">
                            <X size={24} />
                        </button>
                    </div>
                </div>

                {/* Body Content */}
                <div className="flex-1 overflow-y-auto p-8">
                    {step === 1 ? (
                        <div className="flex h-full gap-8">
                            {/* Product List */}
                            <div className="flex-1 border-r border-slate-100 pr-8 flex flex-col">
                                <div className="relative mb-6">
                                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                                    <input
                                        type="text"
                                        placeholder="Buscar productos en stock..."
                                        className="w-full pl-12 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-blue-100 outline-none transition-all font-medium"
                                        value={searchTerm}
                                        onChange={e => setSearchTerm(e.target.value)}
                                    />
                                </div>
                                <div className="flex-1 overflow-y-auto space-y-3 pr-2">
                                    {filteredProducts.map(p => {
                                        const imgUrl = p.images && p.images.length > 0 ? p.images[0] : null;
                                        return (
                                            <div key={p.sku} className="p-4 border border-slate-100 rounded-2xl flex items-center justify-between hover:border-blue-200 hover:shadow-md transition-all group">
                                                <div className="flex items-center gap-4">
                                                    {/* Thumbnail */}
                                                    <div className="w-14 h-14 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center shrink-0 overflow-hidden">
                                                        {imgUrl ? (
                                                            <img src={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${imgUrl}`} alt={p.name} className="w-full h-full object-cover" />
                                                        ) : (
                                                            <Package size={24} className="text-slate-300" />
                                                        )}
                                                    </div>

                                                    <div className="flex-1 min-w-0 pr-4">
                                                        <div className="flex justify-between items-center mb-1 gap-2">
                                                            <span className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors truncate block">
                                                                {p.name}
                                                            </span>
                                                            <span className={`text-xs font-black shrink-0 ${p.stock_quantity > 0 ? 'text-emerald-600' : 'text-slate-400'}`}>
                                                                {p.stock_quantity > 0 ? `${p.stock_quantity} EN STOCK` : 'SIN STOCK'}
                                                            </span>
                                                        </div>
                                                        <span className="text-sm font-black text-emerald-600">${p.price_wholesale?.toLocaleString()}</span>
                                                    </div>
                                                </div>
                                                <button
                                                    onClick={() => handleAddToCart(p)}
                                                    className="w-10 h-10 shrink-0 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center group-hover:bg-blue-600 group-hover:text-white transition-colors font-bold text-lg"
                                                >+</button>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Cart Summary */}
                            <div className="w-[350px] shrink-0 flex flex-col bg-slate-50/50 rounded-3xl p-6 border border-slate-100">
                                <h4 className="font-black tracking-tight text-lg mb-6 flex items-center gap-2"><ShoppingCart size={20} className="text-blue-600" /> Carrito Actual</h4>

                                <div className="flex-1 overflow-y-auto space-y-4">
                                    {cart.length === 0 ? (
                                        <div className="text-center text-slate-400 py-10 italic text-sm">El carrito está vacío</div>
                                    ) : (
                                        cart.map(c => (
                                            <div key={c.product_sku} className="bg-white p-3 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between gap-3">
                                                {/* Cart Item Thumbnail */}
                                                <div className="w-10 h-10 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center shrink-0 overflow-hidden">
                                                    {c.product_image ? (
                                                        <img src={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${c.product_image}`} alt={c.product_name} className="w-full h-full object-cover" />
                                                    ) : (
                                                        <Package size={16} className="text-slate-300" />
                                                    )}
                                                </div>

                                                <div className="flex-1 min-w-0 pr-2">
                                                    <p className="font-bold text-sm text-slate-800 truncate">{c.product_name}</p>
                                                    <p className="text-xs text-slate-500 font-medium">${c.total_price.toLocaleString()}</p>
                                                </div>
                                                <div className="flex items-center gap-3 bg-slate-50 rounded-lg p-1 border border-slate-100 shrink-0">
                                                    <button onClick={() => handleRemoveFromCart(c.product_sku)} className="w-6 h-6 rounded flex items-center justify-center font-bold text-slate-500 hover:bg-white">-</button>
                                                    <span className="text-sm font-black w-4 text-center">{c.quantity}</span>
                                                    <button onClick={() => {
                                                        const p = products.find(x => x.sku === c.product_sku);
                                                        if (p) handleAddToCart(p);
                                                    }} className="w-6 h-6 rounded flex items-center justify-center font-bold text-slate-500 hover:bg-white">+</button>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>

                                <div className="pt-6 border-t border-slate-200 mt-6">
                                    <div className="flex justify-between items-end mb-6">
                                        <span className="text-slate-500 font-bold uppercase tracking-widest text-xs">Total</span>
                                        <span className={`text-3xl font-black ${canProceed ? 'text-emerald-600' : 'text-slate-400'}`}>
                                            ${totalAmount.toLocaleString()}
                                        </span>
                                    </div>

                                    {!canProceed && (
                                        <p className="text-xs text-rose-500 font-bold text-center mb-4 bg-rose-50 p-2 rounded-lg">
                                            Mínimo de compra: $100.000 (Faltan ${(100000 - totalAmount).toLocaleString()})
                                        </p>
                                    )}

                                    <button
                                        disabled={!canProceed}
                                        onClick={() => setStep(2)}
                                        className="w-full py-4 bg-slate-900 disabled:bg-slate-300 disabled:cursor-not-allowed hover:bg-slate-800 text-white font-black rounded-2xl transition-all shadow-xl shadow-slate-200 flex items-center justify-center gap-2"
                                    >
                                        Continuar a Datos <ChevronRight size={18} />
                                    </button>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="max-w-4xl mx-auto grid grid-cols-2 gap-12">
                            {/* Billing Info */}
                            <div className="space-y-6">
                                <h4 className="text-lg font-black tracking-tight flex items-center gap-2 text-slate-800 border-b border-slate-100 pb-4">
                                    <User size={20} className="text-blue-600" /> Datos de Facturación
                                </h4>
                                <div className="space-y-4">
                                    <div><label className="text-xs font-bold text-slate-500 uppercase">DNI / CUIT</label><input name="dni_cuit" value={formData.dni_cuit} onChange={handleInputChange} className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl" /></div>
                                    <div><label className="text-xs font-bold text-slate-500 uppercase">Dirección Completa</label><input name="address" value={formData.address} onChange={handleInputChange} className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl" /></div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div><label className="text-xs font-bold text-slate-500 uppercase">Localidad</label><input name="locality" value={formData.locality} onChange={handleInputChange} className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl" /></div>
                                        <div><label className="text-xs font-bold text-slate-500 uppercase">C.P</label><input name="zip_code" value={formData.zip_code} onChange={handleInputChange} className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl" /></div>
                                    </div>
                                    <div><label className="text-xs font-bold text-slate-500 uppercase">Provincia</label><input name="province" value={formData.province} onChange={handleInputChange} className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl" /></div>
                                </div>
                            </div>

                            {/* Transport Info */}
                            <div className="space-y-6">
                                <h4 className="text-lg font-black tracking-tight flex items-center gap-2 text-slate-800 border-b border-slate-100 pb-4">
                                    <Truck size={20} className="text-blue-600" /> Datos del Envío
                                </h4>
                                <div className="space-y-4">
                                    <div><label className="text-xs font-bold text-slate-500 uppercase">Nombre Transportista</label><input name="transport_name" value={formData.transport_name} onChange={handleInputChange} className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl" /></div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div><label className="text-xs font-bold text-slate-500 uppercase">DNI</label><input name="transport_dni" value={formData.transport_dni} onChange={handleInputChange} className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl" /></div>
                                        <div><label className="text-xs font-bold text-slate-500 uppercase">Patente</label><input name="license_plate" value={formData.license_plate} onChange={handleInputChange} className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl" /></div>
                                    </div>
                                    <div><label className="text-xs font-bold text-slate-500 uppercase">Lugar de Entrega</label><input name="delivery_address" value={formData.delivery_address} onChange={handleInputChange} className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl" /></div>
                                    <div><label className="text-xs font-bold text-slate-500 uppercase">Fecha de Entrega Aprox</label><input type="date" name="delivery_date" value={formData.delivery_date} onChange={handleInputChange} className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl" /></div>
                                </div>

                                <div className="pt-8">
                                    <button
                                        disabled={loading}
                                        onClick={handleSubmit}
                                        className="w-full py-4 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-black text-lg rounded-2xl transition-all shadow-xl shadow-emerald-200 flex items-center justify-center gap-2"
                                    >
                                        {loading ? 'Procesando...' : (
                                            <><CheckCircle2 size={24} /> Generar Remito y Finalizar</>
                                        )}
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
