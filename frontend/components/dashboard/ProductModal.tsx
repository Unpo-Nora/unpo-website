import React, { useState, useEffect, useRef } from 'react';
import { X, Save, Box, DollarSign, ArchiveRestore, Archive, UploadCloud, ImageIcon, Trash2 } from 'lucide-react';

interface ProductModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: () => void;
    product?: any | null;
}

export default function ProductModal({ isOpen, onClose, onSave, product }: ProductModalProps) {
    const [formData, setFormData] = useState({
        sku: '',
        name: '',
        category_id: 0, // 0 to force user selection
        description: '',
        stock_quantity: 0,
        cost_price: 0,
        price_usd: 0,
        iva_percent: 21,
        is_active: true,
        price_breakdown: {} as any
    });

    const [priceOrigin, setPriceOrigin] = useState<'argentina' | 'importado'>('argentina');
    const [purchaseCost, setPurchaseCost] = useState(0);
    const [importTaxes, setImportTaxes] = useState(0);
    const [profitMargin, setProfitMargin] = useState(30);
    const [exchangeRate, setExchangeRate] = useState(1);

    const [nextSku, setNextSku] = useState("");
    const [categories, setCategories] = useState<{id: number, name: string}[]>([]);

    useEffect(() => {
        const fetchExchange = async () => {
             const token = localStorage.getItem('token');
             try {
                const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/settings/manual_exchange_rate`, { headers: { 'Authorization': `Bearer ${token}` } });
                if(res.ok) {
                    const data = await res.json();
                    setExchangeRate(Number(data.value) || 1);
                }
             } catch(e) {}
        };
        fetchExchange();
        
        if (!product && isOpen) {
            const fetchNextSku = async () => {
                 const token = localStorage.getItem('token');
                 try {
                     const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/next-sku`, { headers: { 'Authorization': `Bearer ${token}` }});
                     if (res.ok) {
                         const data = await res.json();
                         setNextSku(data.next_sku);
                     }
                 } catch (e) {}
            };
            fetchNextSku();
        }

        const fetchCategories = async () => {
             const token = localStorage.getItem('token');
             try {
                 const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/categories`, { headers: { 'Authorization': `Bearer ${token}` }});
                 if (res.ok) {
                     let data = await res.json();
                     const allowed = ["DECORACION", "HOGAR", "MARROQUINERIA", "BAZAR", "TECNOLOGIA", "JUGUETE"];
                     
                     const missing = allowed.filter(allowName => !data.some((c: any) => c.name.trim().toUpperCase() === allowName));
                     for (const m of missing) {
                         try {
                             const cRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/categories`, {
                                 method: 'POST',
                                 headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                                 body: JSON.stringify({name: m})
                             });
                             if(cRes.ok) {
                                 data.push(await cRes.json());
                             }
                         } catch (e) {}
                     }
                     
                     // Filter to ONLY show the allowed ones and sort them matching exactly
                     const finalCategories = data.filter((c: any) => allowed.includes(c.name.trim().toUpperCase()));
                     setCategories(finalCategories);
                 }
             } catch (e) {}
        };
        fetchCategories();
    }, [isOpen, product]);

    // Calculator useEffect
    useEffect(() => {
        let baseCost = purchaseCost;
        if (priceOrigin === 'importado') {
            baseCost += importTaxes;
        }
        
        const finalArs = baseCost * (1 + formData.iva_percent / 100) * (1 + profitMargin / 100);
        const calcUsd = finalArs / exchangeRate;

        if (purchaseCost > 0) {
            setFormData(prev => ({
                ...prev,
                cost_price: baseCost,
                price_usd: Number(calcUsd.toFixed(2)),
                price_breakdown: {
                    origin: priceOrigin,
                    purchase_cost: purchaseCost,
                    import_taxes: importTaxes,
                    profit_margin: profitMargin,
                    exchange_rate_used: exchangeRate
                }
            }));
        }
    }, [priceOrigin, purchaseCost, importTaxes, profitMargin, formData.iva_percent, exchangeRate]);

    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    // Image Upload State
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [existingImages, setExistingImages] = useState<string[]>([]);
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (product) {
            setFormData({
                sku: product.sku,
                name: product.name,
                category_id: product.category_id || 0,
                description: product.description || '',
                stock_quantity: product.stock_quantity,
                cost_price: product.cost_price || 0,
                price_usd: product.price_usd || 0,
                iva_percent: product.iva_percent || 21,
                is_active: product.is_active !== false,
                price_breakdown: product.price_breakdown || {}
            });
            if (product.price_breakdown) {
                 setPriceOrigin(product.price_breakdown.origin || 'argentina');
                 setPurchaseCost(product.price_breakdown.purchase_cost || 0);
                 setImportTaxes(product.price_breakdown.import_taxes || 0);
                 setProfitMargin(product.price_breakdown.profit_margin || 30);
            }
            setExistingImages(product.images || []);
        } else {
            setFormData({ sku: '', name: '', category_id: 0, description: '', stock_quantity: 0, cost_price: 0, price_usd: 0, iva_percent: 21, is_active: true, price_breakdown: {} });
            setExistingImages([]);
        }
        setSelectedFiles([]);
        setIsDragging(false);
    }, [product, isOpen]);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!formData.description.trim()) {
            setError("La descripción del producto es obligatoria.");
            return;
        }

        if (!formData.category_id) {
            setError("Debe seleccionar una categoría.");
            return;
        }



        setSaving(true);
        setError('');

        try {
            const token = localStorage.getItem('token');
            const url = product
                ? `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/${product.sku}`
                : `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/`;

            const method = product ? 'PUT' : 'POST';

            let response;
            let retries = 3;
            while(retries > 0) {
                try {
                    response = await fetch(url, {
                        method,
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(formData)
                    });
                    
                    // If network succeeded (even if 4xx/5xx), break out of retry loop
                    break;
                } catch (netErr) {
                    retries--;
                    if (retries === 0) throw netErr;
                    await new Promise(r => setTimeout(r, 1000)); // wait 1s before retry
                }
            }

            if (response && response.ok) {
                // Return data has generated sku
                const savedProduct = await response.json();
                
                // Upload images if any
                const sku = product ? product.sku : (savedProduct.sku || formData.sku);
                if (selectedFiles.length > 0) {
                    setSaving(true);
                    for (const file of selectedFiles) {
                        const imageFormData = new FormData();
                        imageFormData.append('file', file);

                        try {
                            await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/${sku}/images`, {
                                method: 'POST',
                                headers: { 'Authorization': `Bearer ${token}` },
                                body: imageFormData
                            });
                        } catch (imgError) {
                            console.error("Error uploading image:", imgError);
                        }
                    }
                }

                onSave();
                onClose();
            } else if (response) {
                // Not a network error, but a 4xx or 5xx HTTP error
                try {
                    const data = await response.json();
                    setError(data.detail || 'Error al guardar el producto (Backend Error)');
                } catch (parseErr) {
                    // Happens if backend returns HTML (e.g. 502 Bad Gateway)
                    setError('Error interno del servidor. Intente nuevamente.');
                }
            } else {
                setError('No se pudo establecer conexión con el servidor.');
            }
        } catch (err) {
            setError('Error de conexión con el servidor tras varios intentos.');
        } finally {
            setSaving(false);
        }
    };

    const handleFileDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
        if (files.length) setSelectedFiles(prev => [...prev, ...files]);
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            const files = Array.from(e.target.files).filter(f => f.type.startsWith('image/'));
            if (files.length) setSelectedFiles(prev => [...prev, ...files]);
        }
    };

    const handleArchive = async () => {
        if (!product) return;
        if (!confirm('¿Estás seguro de archivar/desactivar este producto? Desaparecerá del catálogo público pero conservará su historial.')) return;

        setSaving(true);
        try {
            const token = localStorage.getItem('token');
            const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/${product.sku}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                onSave();
                onClose();
            } else {
                setError('Error al archivar el producto');
            }
        } catch (err) {
            setError('Error de conexión');
        } finally {
            setSaving(false);
        }
    };

    const handleHardDelete = async () => {
        if (!product) return;
        if (!confirm('⚠️ ATENCIÓN: Esta acción eliminará el producto DEFINITIVAMENTE de la base de datos. Solo úselo para borrar pruebas. ¿Proceder?')) return;

        setSaving(true);
        try {
            const token = localStorage.getItem('token');
            const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/products/${product.sku}/hard`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                onSave();
                onClose();
            } else {
                setError('Error al eliminar permanentemente el producto');
            }
        } catch (err) {
            setError('Error de conexión');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-3xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
                <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <h2 className="text-xl font-black text-slate-800 tracking-tight flex items-center gap-2">
                        <Box className="text-blue-600" />
                        {product ? 'Editar Producto' : 'Nuevo Producto'}
                    </h2>
                    <button onClick={onClose} className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <div className="p-6 overflow-y-auto flex-1">
                    {error && (
                        <div className="mb-6 p-4 bg-red-50 border border-red-100 text-red-600 rounded-2xl text-sm font-medium">
                            {error}
                        </div>
                    )}

                    <form id="product-form" onSubmit={handleSubmit} className="space-y-6">
                        <div className="grid grid-cols-2 gap-6">
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">SKU</label>
                                <input
                                    required={!!product} // not required if it's new
                                    disabled={true} // always disabled. Auto on new, uneditable on update.
                                    type="text"
                                    value={product ? formData.sku : (nextSku || "Cargando...")}
                                    onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl outline-none text-slate-500 font-bold disabled:opacity-50"
                                    title="El SKU se generará automáticamente"
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">Nombre del Producto</label>
                                <input
                                    required
                                    type="text"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:border-blue-500 outline-none text-slate-700 font-bold"
                                />
                            </div>
                        </div>
                        
                        <div className="space-y-2 flex-grow">
                                <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">Categoría <span className="text-red-500">*</span></label>
                                <select
                                    required
                                    value={formData.category_id || ''}
                                    onChange={(e) => setFormData({ ...formData, category_id: parseInt(e.target.value) })}
                                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:border-blue-500 outline-none text-slate-700 font-bold"
                                >
                                     <option value="" disabled>Seleccione una categoría</option>
                                    {categories
                                        .filter(c => ['DECORACION', 'HOGAR', 'MARROQUINERIA', 'BAZAR', 'TECNOLOGIA', 'JUGUETE'].includes(c.name.trim().toUpperCase()))
                                        .sort((a,b) => a.name.localeCompare(b.name))
                                        .map(c => (
                                        <option key={c.id} value={c.id}>{c.name.trim().toUpperCase()}</option>
                                    ))}
                                </select>
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">Descripción Breve <span className="text-red-500">*</span></label>
                            <textarea
                                required
                                rows={3}
                                value={formData.description}
                                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:border-blue-500 outline-none text-slate-700 resize-none"
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-6 p-4 bg-blue-50/50 border border-blue-100 rounded-2xl">
                            <div className="space-y-2">
                                <label className="text-xs font-bold text-blue-600 uppercase tracking-wider flex items-center gap-1">
                                    <Box size={14} /> Stock Real
                                </label>
                                <input
                                    required
                                    type="number"
                                    min="0"
                                    value={formData.stock_quantity}
                                    onChange={(e) => setFormData({ ...formData, stock_quantity: parseInt(e.target.value) || 0 })}
                                    className="w-full px-4 py-3 bg-white border border-blue-200 rounded-xl focus:border-blue-500 outline-none text-slate-700 font-bold text-lg"
                                />
                            </div>
                            <div className="col-span-2 space-y-4 pt-4 border-t border-blue-200">
                                <h3 className="font-bold text-blue-800 flex items-center gap-2">
                                    <DollarSign size={18} /> Construcción del Precio final
                                </h3>
                                
                                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                     <div className="space-y-1">
                                        <label className="text-[10px] font-bold text-blue-600 uppercase tracking-wider">Origen</label>
                                        <select value={priceOrigin} onChange={e => setPriceOrigin(e.target.value as any)} className="w-full px-3 py-2 bg-white border border-blue-200 rounded-lg text-sm font-bold text-slate-700 outline-none">
                                            <option value="argentina">Argentina</option>
                                            <option value="importado">Importado</option>
                                        </select>
                                     </div>
                                     <div className="space-y-1">
                                        <label className="text-[10px] font-bold text-blue-600 uppercase tracking-wider">Costo Compra (ARS)</label>
                                        <input type="number" min="0" value={purchaseCost} onChange={e => setPurchaseCost(parseFloat(e.target.value)||0)} className="w-full px-3 py-2 bg-white border border-blue-200 rounded-lg text-sm font-bold text-slate-700 outline-none" />
                                     </div>
                                     {priceOrigin === 'importado' && (
                                         <div className="space-y-1">
                                            <label className="text-[10px] font-bold text-blue-600 uppercase tracking-wider">Impuestos Imp. (ARS)</label>
                                            <input type="number" min="0" value={importTaxes} onChange={e => setImportTaxes(parseFloat(e.target.value)||0)} className="w-full px-3 py-2 bg-white border border-blue-200 rounded-lg text-sm font-bold text-slate-700 outline-none" />
                                         </div>
                                     )}
                                     <div className="space-y-1">
                                        <label className="text-[10px] font-bold text-blue-600 uppercase tracking-wider">Ganancia (%)</label>
                                        <input type="number" min="0" value={profitMargin} onChange={e => setProfitMargin(parseFloat(e.target.value)||0)} className="w-full px-3 py-2 bg-white border border-blue-200 rounded-lg text-sm font-bold text-slate-700 outline-none" />
                                     </div>
                                </div>
                            </div>
                            
                            <div className="col-span-2 grid grid-cols-2 gap-6 mt-2">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">IVA (%)</label>
                                    <input
                                        required
                                        type="number"
                                        min="0"
                                        value={formData.iva_percent}
                                        onChange={(e) => setFormData({ ...formData, iva_percent: parseFloat(e.target.value) || 0 })}
                                        className="w-full px-4 py-3 bg-white border border-blue-200 rounded-xl focus:border-blue-500 outline-none text-slate-700 font-bold"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-green-600 uppercase tracking-wider flex items-center gap-1">
                                        <DollarSign size={14} /> Precio Final Venta (USD)
                                    </label>
                                    <div className="relative">
                                        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-green-500 font-bold">U$D</span>
                                        <input
                                            required
                                            type="number"
                                            min="0"
                                            step="0.01"
                                            value={formData.price_usd}
                                            onChange={(e) => setFormData({ ...formData, price_usd: parseFloat(e.target.value) || 0 })}
                                            className="w-full pl-12 pr-4 py-3 bg-white border border-green-300 shadow-inner rounded-xl focus:border-green-500 outline-none text-green-700 font-black text-lg"
                                        />
                                    </div>
                                    <p className="text-[10px] text-slate-500 text-right mt-1 font-medium">Cotización Actual Dólar: ${exchangeRate}</p>
                                </div>
                            </div>
                        </div>

                        {/* Image Upload Zone */}
                        <div className="space-y-3">
                            <label className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                                <ImageIcon size={14} /> Galería de Imágenes {!product && <span className="text-red-500">*</span>}
                            </label>

                            {/* Drag & Drop Area */}
                            <div
                                className={`w-full p-8 border-2 border-dashed rounded-2xl text-center cursor-pointer transition-all ${isDragging ? 'border-blue-500 bg-blue-50 text-blue-600' : 'border-slate-200 bg-slate-50 text-slate-500 hover:border-slate-300 hover:bg-slate-100'
                                    }`}
                                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                                onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
                                onDrop={handleFileDrop}
                                onClick={() => fileInputRef.current?.click()}
                            >
                                <UploadCloud size={32} className="mx-auto mb-3 opacity-50" />
                                <p className="font-bold text-sm">Arrastra y suelta imágenes aquí</p>
                                <p className="text-xs mt-1 font-medium opacity-70">o haz clic para explorar tus archivos</p>
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    className="hidden"
                                    multiple
                                    accept="image/*"
                                    onChange={handleFileSelect}
                                />
                            </div>

                            {/* Previews */}
                            {(existingImages.length > 0 || selectedFiles.length > 0) && (
                                <div className="grid grid-cols-4 sm:grid-cols-5 gap-3 mt-4">
                                    {/* Existing Images */}
                                    {existingImages.map((imgUrl, idx) => (
                                        <div key={`existing-${idx}`} className="relative group aspect-square rounded-xl bg-slate-100 border border-slate-200 overflow-hidden flex items-center justify-center">
                                            <img src={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${imgUrl}`} alt="Product snapshot" className="w-full h-full object-cover" />
                                        </div>
                                    ))}

                                    {/* Selected New Images */}
                                    {selectedFiles.map((file, idx) => (
                                        <div key={`new-${idx}`} className="relative group aspect-square rounded-xl bg-blue-50 border border-blue-200 overflow-hidden flex items-center justify-center">
                                            <img src={URL.createObjectURL(file)} alt="Preview" className="w-full h-full object-cover opacity-90" />
                                            <div className="absolute inset-0 bg-slate-900/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                                <button
                                                    type="button"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setSelectedFiles(files => files.filter((_, i) => i !== idx));
                                                    }}
                                                    className="w-8 h-8 rounded-full bg-red-500 text-white flex items-center justify-center hover:bg-red-600"
                                                >
                                                    <Trash2 size={14} />
                                                </button>
                                            </div>
                                            <span className="absolute bottom-1 right-1 bg-blue-600 text-white text-[9px] font-black px-1.5 py-0.5 rounded shadow-sm">NUEVO</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </form>
                </div>

                <div className="p-6 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
                    {product ? (
                        <div className="flex gap-2">
                            <button
                                type="button"
                                onClick={handleArchive}
                                disabled={saving}
                                className="flex items-center gap-2 px-4 py-2.5 text-sm font-bold text-red-600 bg-red-50 hover:bg-red-100 rounded-xl transition-colors disabled:opacity-50"
                            >
                                <Archive size={16} />
                                Archivar Producto
                            </button>
                            <button
                                type="button"
                                onClick={handleHardDelete}
                                disabled={saving}
                                className="flex items-center gap-2 px-3 py-2.5 text-sm font-bold text-slate-400 bg-white hover:bg-red-600 hover:text-white border border-slate-200 hover:border-red-600 rounded-xl transition-all disabled:opacity-50"
                                title="Borrar Definitivamente"
                            >
                                <Trash2 size={16} />
                            </button>
                        </div>
                    ) : (
                        <div /> // Spacer
                    )}

                    <div className="flex gap-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-6 py-2.5 font-bold text-slate-500 hover:bg-slate-200 rounded-xl transition-all"
                        >
                            Cancelar
                        </button>
                        <button
                            type="submit"
                            form="product-form"
                            disabled={saving}
                            className="flex items-center gap-2 px-6 py-2.5 font-bold text-white bg-blue-600 hover:bg-blue-700 shadow-md shadow-blue-200 rounded-xl transition-all disabled:opacity-50"
                        >
                            <Save size={18} />
                            {saving ? 'Guardando...' : 'Guardar Producto'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
