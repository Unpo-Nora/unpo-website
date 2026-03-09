"use client";

import React, { useState, useEffect } from 'react';
import { X, ChevronLeft, ChevronRight, Package, Hash, AlertCircle } from 'lucide-react';

interface Product {
    sku: string;
    name: string;
    price_wholesale: number;
    stock_quantity: number;
    category_id?: number;
    description?: string;
    images?: string[];
    videos?: string[];
}

interface ProductModalProps {
    product: Product | null;
    isOpen: boolean;
    onClose: () => void;
    categoryName: string;
}

export default function ProductModal({ product, isOpen, onClose, categoryName }: ProductModalProps) {
    const [activeMediaIndex, setActiveMediaIndex] = useState(0);
    const [isClosing, setIsClosing] = useState(false);

    useEffect(() => {
        if (isOpen) {
            setActiveMediaIndex(0);
            setIsClosing(false);
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'unset';
        }
    }, [isOpen]);

    if (!isOpen || !product) return null;

    const handleClose = () => {
        setIsClosing(true);
        setTimeout(onClose, 300);
    };

    const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
    const baseUrl = `http://${host}:8000`;

    // Combinar imágenes y videos en una sola lista multimedia
    const media = [
        ...(product.images || []).map(url => ({ type: 'image', url: url.startsWith('http') ? url : `${baseUrl}${url}` })),
        ...(product.videos || []).map(url => ({ type: 'video', url: url.startsWith('http') ? url : `${baseUrl}${url}` }))
    ];

    const safeMediaIndex = activeMediaIndex < media.length ? activeMediaIndex : 0;

    const nextMedia = () => setActiveMediaIndex((prev) => (prev + 1) % media.length);
    const prevMedia = () => setActiveMediaIndex((prev) => (prev - 1 + media.length) % media.length);

    return (
        <div className={`fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 transition-all duration-300 ${isClosing ? 'opacity-0' : 'opacity-100'}`}>
            {/* Backdrop */}
            <div
                className={`absolute inset-0 bg-slate-900/60 backdrop-blur-md transition-opacity duration-300 ${isClosing ? 'opacity-0' : 'opacity-100'}`}
                onClick={handleClose}
            />

            {/* Modal Content */}
            <div className={`relative bg-white w-full max-w-6xl max-h-[90vh] overflow-hidden rounded-[40px] shadow-2xl flex flex-col md:flex-row transform transition-all duration-500 scale-100 ${isClosing ? 'scale-95 opacity-0' : 'scale-100 opacity-100'}`}>

                {/* Close Button */}
                <button
                    onClick={handleClose}
                    className="absolute top-6 right-6 z-10 p-3 bg-white/80 backdrop-blur-md text-slate-900 rounded-full shadow-lg hover:bg-white hover:scale-110 transition-all border border-slate-100"
                >
                    <X size={24} />
                </button>

                {/* Left: Media Gallery */}
                <div className="w-full md:w-3/5 bg-slate-50 relative flex flex-col items-center justify-center min-h-[400px]">
                    <div className="w-full h-full relative overflow-hidden group flex items-center justify-center">
                        {media.length > 0 ? (
                            <>
                                {media[safeMediaIndex].type === 'image' ? (
                                    <img
                                        src={media[safeMediaIndex].url}
                                        alt={product.name}
                                        className="w-full h-full object-contain p-8 transition-opacity duration-500"
                                    />
                                ) : (
                                    <video
                                        src={media[safeMediaIndex].url}
                                        controls
                                        autoPlay
                                        muted
                                        className="w-full h-full object-contain p-8"
                                    />
                                )}

                                {media.length > 1 && (
                                    <>
                                        <button
                                            onClick={prevMedia}
                                            className="absolute left-6 top-1/2 -translate-y-1/2 p-4 bg-white/90 text-slate-900 rounded-full shadow-xl opacity-0 group-hover:opacity-100 transition-all hover:bg-blue-600 hover:text-white z-10"
                                        >
                                            <ChevronLeft size={24} />
                                        </button>
                                        <button
                                            onClick={nextMedia}
                                            className="absolute right-6 top-1/2 -translate-y-1/2 p-4 bg-white/90 text-slate-900 rounded-full shadow-xl opacity-0 group-hover:opacity-100 transition-all hover:bg-blue-600 hover:text-white z-10"
                                        >
                                            <ChevronRight size={24} />
                                        </button>
                                    </>
                                )}
                            </>
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-slate-200">
                                <Package size={120} strokeWidth={1} />
                            </div>
                        )}
                    </div>

                    {/* Thumbnails */}
                    {media.length > 1 && (
                        <div className="absolute bottom-8 flex gap-3 px-6 py-3 bg-white/50 backdrop-blur-md rounded-2xl shadow-sm border border-white/20 max-w-[90%] overflow-x-auto scrollbar-hide">
                            {media.map((item, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => setActiveMediaIndex(idx)}
                                    className={`w-14 h-14 min-w-[3.5rem] rounded-xl overflow-hidden border-2 transition-all relative ${safeMediaIndex === idx ? 'border-blue-600 scale-110 shadow-lg' : 'border-transparent opacity-60 hover:opacity-100'}`}
                                >
                                    {item.type === 'image' ? (
                                        <img src={item.url} className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="w-full h-full bg-slate-800 flex items-center justify-center text-white">
                                            <Hash size={20} />
                                            <span className="absolute inset-0 flex items-center justify-center bg-black/20 text-[10px] font-black underline">VIDEO</span>
                                        </div>
                                    )}
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* Right: Product Info */}
                <div className="w-full md:w-2/5 p-8 md:p-12 overflow-y-auto bg-white flex flex-col">
                    <div className="mb-4 flex items-center justify-between">
                        <span className="px-3 py-1 bg-blue-50 text-blue-600 text-[10px] font-black uppercase tracking-widest rounded-full">
                            {categoryName}
                        </span>
                    </div>

                    <h2 className="text-3xl md:text-4xl font-black text-slate-900 leading-[1.1] mb-6 tracking-tighter italic">
                        {product.name}
                    </h2>

                    <div className="mb-8 p-6 bg-slate-50 rounded-[32px] border border-slate-100/50">
                        <p className="text-[10px] text-slate-400 font-black uppercase tracking-[0.2em] mb-1">PRECIO MAYORISTA (ARS)</p>
                        <div className="flex items-baseline gap-2">
                            <p className="text-4xl font-black text-slate-900 tracking-tighter italic">
                                ${Number(product.price_wholesale).toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                                <span className="text-[10px] font-bold text-slate-400 ml-2 not-italic">+ IVA</span>
                            </p>
                        </div>
                    </div>

                    <div className="space-y-6 mb-10">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center">
                                <Package size={20} />
                            </div>
                            <div>
                                <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">Estado de Stock</p>
                                <p className="text-sm font-black text-emerald-600 uppercase">Disponible para Entrega Inmediata</p>
                            </div>
                        </div>

                        <div className="pt-6 border-t border-slate-100">
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-4 flex items-center gap-2">
                                <AlertCircle size={12} className="text-blue-500" />
                                Descripción del Producto
                            </p>
                            <div className="text-slate-600 text-base leading-relaxed font-medium">
                                {product.description ? (
                                    <p className="whitespace-pre-line">{product.description}</p>
                                ) : (
                                    <p className="italic text-slate-400">Sin descripción técnica disponible actualmente.</p>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="mt-auto pt-8 border-t border-slate-100">
                        <p className="text-[10px] text-center text-slate-400 font-bold uppercase tracking-widest">
                            Consulta por stock y disponibilidad con tu asesor comercial
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
