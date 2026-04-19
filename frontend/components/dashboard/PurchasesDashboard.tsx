"use client";

import React, { useState, useEffect } from 'react';
import { DollarSign, Plus, Trash2, Box, PackagePlus, Users, ArrowRightLeft, Calendar, FileText, CheckCircle, AlertTriangle, ExternalLink } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';

type TabType = 'flujo' | 'compras' | 'cuentas' | 'proveedores';

export default function PurchasesDashboard() {
    const { user } = useAuth();
    const router = useRouter();
    const [activeTab, setActiveTab] = useState<TabType>('flujo');
    const [exchangeRate, setExchangeRate] = useState(1450);
    const [loading, setLoading] = useState(true);

    const [transactions, setTransactions] = useState<any[]>([]);
    const [purchases, setPurchases] = useState<any[]>([]);
    const [suppliers, setSuppliers] = useState<any[]>([]);
    const [financeMetrics, setFinanceMetrics] = useState<any>(null);

    // Form states
    const [txForm, setTxForm] = useState({ tipo: 'EGRESO', categoria: 'OPERATIVO', descripcion: '', monto: '', moneda: 'ARS', fecha: '' });
    const [supplierForm, setSupplierForm] = useState({ nombre: '', contacto: '', telefono: '', email: '' });
    
    // Purchase Form State
    const [isPurchaseModalOpen, setIsPurchaseModalOpen] = useState(false);
    const [purchaseForm, setPurchaseForm] = useState({ proveedor_id: '', descripcion: '', cantidad_total: '', moneda: 'ARS', tipo_pago: 'CONTADO', cost_producto: '', cost_flete: '', cost_impuestos: '', cost_otros: '' });

    const fetchAllData = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const headers = { 'Authorization': `Bearer ${token}` };
            
            const [exRes, pRes, sRes, txRes, dRes] = await Promise.all([
                fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/settings/manual_exchange_rate`, { headers }),
                fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/finance/purchases`, { headers }),
                fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/finance/suppliers`, { headers }),
                fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/finance/financial-transactions`, { headers }),
                fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/finance/dashboard/finance`, { headers })
            ]);

            if(exRes.ok) { const d = await exRes.json(); setExchangeRate(Number(d.value) || 1450); }
            if(pRes.ok) setPurchases(await pRes.json());
            if(sRes.ok) setSuppliers(await sRes.json());
            if(txRes.ok) setTransactions(await txRes.json());
            if(dRes.ok) setFinanceMetrics(await dRes.json());
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    };

    useEffect(() => {
        fetchAllData();
    }, []);

    const handleMontoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        let val = e.target.value.replace(/\D/g, ''); // Solo números
        if (val) {
            // Formatear con separadores de miles
            val = new Intl.NumberFormat('es-AR').format(parseInt(val, 10));
        }
        setTxForm({...txForm, monto: val});
    };

    const handleCreateTransaction = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/finance/financial-transactions`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tipo_movimiento: txForm.tipo,
                    categoria: txForm.categoria,
                    descripcion: txForm.descripcion,
                    monto: parseFloat(txForm.monto.replace(/\./g, '')), // Quitar puntos de miles
                    moneda: txForm.moneda,
                    fecha: txForm.fecha ? new Date(txForm.fecha + 'T12:00:00').toISOString() : undefined
                })
            });
            if(res.ok) {
                setTxForm({ tipo: 'EGRESO', categoria: 'OPERATIVO', descripcion: '', monto: '', moneda: 'ARS', fecha: '' });
                fetchAllData();
            }
        } catch(e) {}
    };

    const handleCreateSupplier = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/finance/suppliers`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(supplierForm)
            });
            if(res.ok) {
                setSupplierForm({ nombre: '', contacto: '', telefono: '', email: '' });
                fetchAllData();
            }
        } catch(e) {}
    };

    const handleCreatePurchase = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const token = localStorage.getItem('token');
            const cost_details = [];
            if (purchaseForm.cost_producto) cost_details.push({ tipo_costo: 'PRODUCTO', monto: parseFloat(purchaseForm.cost_producto)});
            if (purchaseForm.cost_flete) cost_details.push({ tipo_costo: 'FLETE', monto: parseFloat(purchaseForm.cost_flete)});
            if (purchaseForm.cost_impuestos) cost_details.push({ tipo_costo: 'IMPUESTOS', monto: parseFloat(purchaseForm.cost_impuestos)});
            if (purchaseForm.cost_otros) cost_details.push({ tipo_costo: 'OTROS', monto: parseFloat(purchaseForm.cost_otros)});

            const payload = {
                proveedor_id: purchaseForm.proveedor_id ? parseInt(purchaseForm.proveedor_id) : null,
                descripcion: purchaseForm.descripcion,
                cantidad_total: parseInt(purchaseForm.cantidad_total) || 0,
                moneda: purchaseForm.moneda,
                tipo_pago: purchaseForm.tipo_pago,
                cost_details: cost_details,
                items: []
            };

            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/finance/purchases`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if(res.ok) {
                setIsPurchaseModalOpen(false);
                setPurchaseForm({ proveedor_id: '', descripcion: '', cantidad_total: '', moneda: 'ARS', tipo_pago: 'CONTADO', cost_producto: '', cost_flete: '', cost_impuestos: '', cost_otros: '' });
                fetchAllData();
            }
        } catch(e) {}
    };

    const handlePayPurchase = async (id: number) => {
        if(!confirm("¿Confirmar el pago total de esta cuenta y registrarlo en caja?")) return;
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/finance/purchases/${id}/pay`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if(res.ok) {
                alert("Pago registrado exitosamente");
                fetchAllData();
            } else {
                alert("Error al registrar pago");
            }
        } catch(e) {}
    };

    const formatCurrency = (amount: number, currency: string) => {
        return new Intl.NumberFormat('es-AR', { style: 'currency', currency: currency }).format(amount);
    };

    const formatStatus = (status: string) => {
        if (status === 'PAGADO') return <span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-bold rounded-md">PAGADO</span>;
        if (status === 'PENDIENTE') return <span className="px-2 py-1 bg-yellow-100 text-yellow-700 text-xs font-bold rounded-md">PENDIENTE</span>;
        if (status === 'VENCIDO') return <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-bold rounded-md">VENCIDO</span>;
        return <span className="px-2 py-1 bg-slate-100 text-slate-700 text-xs font-bold rounded-md">{status}</span>;
    };

    const formatType = (type: string) => {
        if (type === 'INGRESO') return <span className="text-green-600 font-black">+ {type}</span>;
        if (type === 'EGRESO' || type === 'PAGO') return <span className="text-red-500 font-black">- {type}</span>;
        return <span className="text-slate-500 font-bold">{type}</span>;
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-2">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Finanzas y Compras</h1>
                    <p className="text-slate-500 mt-1">Control de flujo de caja, cuentas por pagar y mercadería.</p>
                </div>
                {user?.role === 'admin' && (
                    <button
                        onClick={() => router.push('/admin/inventory')}
                        className="flex items-center gap-2 px-6 py-3 rounded-2xl font-bold bg-slate-900 text-white hover:bg-slate-800 shadow-lg shadow-slate-200 transition-all"
                        title="Ir al módulo de Inventario para dar de alta un producto nuevo"
                    >
                        <PackagePlus size={20} />
                        Ir a Inventario <ExternalLink size={16} className="ml-1 opacity-50" />
                    </button>
                )}
            </div>

            {/* Metrics Dashboard */}
            {financeMetrics && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
                        <div className="text-slate-500 text-sm font-bold uppercase tracking-wider mb-2">Balance General (ARS)</div>
                        <div className={`text-3xl font-black ${financeMetrics.balance_ars >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {formatCurrency(financeMetrics.balance_ars, 'ARS')}
                        </div>
                    </div>
                    <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
                        <div className="text-slate-500 text-sm font-bold uppercase tracking-wider mb-2">Ingresos Totales</div>
                        <div className="text-2xl font-bold text-slate-800">{formatCurrency(financeMetrics.ingresos_ars, 'ARS')}</div>
                    </div>
                    <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between">
                        <div className="text-slate-500 text-sm font-bold uppercase tracking-wider mb-2">Egresos Reales</div>
                        <div className="text-2xl font-bold text-slate-800">{formatCurrency(financeMetrics.egresos_ars, 'ARS')}</div>
                    </div>
                    <div className="bg-orange-50 p-5 rounded-2xl border border-orange-100 shadow-sm flex flex-col justify-between">
                        <div className="text-orange-600 text-sm font-bold uppercase tracking-wider mb-2">Cuentas por Pagar</div>
                        <div className="text-2xl font-black text-orange-700">{formatCurrency(financeMetrics.cuentas_por_pagar_pendientes_ars + financeMetrics.cuentas_por_pagar_vencidas_ars, 'ARS')}</div>
                    </div>
                </div>
            )}

            {/* Tabs */}
            <div className="flex flex-wrap gap-2 mb-6 border-b border-slate-200 pb-4">
                <button onClick={() => setActiveTab('flujo')} className={`px-5 py-2.5 rounded-xl font-bold transition-all flex items-center gap-2 ${activeTab === 'flujo' ? 'bg-blue-600 text-white shadow-md' : 'bg-white text-slate-600 hover:bg-slate-50'}`}>
                    <ArrowRightLeft size={18} /> Flujo de Movimientos
                </button>
                <button onClick={() => setActiveTab('cuentas')} className={`px-5 py-2.5 rounded-xl font-bold transition-all flex items-center gap-2 ${activeTab === 'cuentas' ? 'bg-blue-600 text-white shadow-md' : 'bg-white text-slate-600 hover:bg-slate-50'}`}>
                    <AlertTriangle size={18} /> Cuentas por Pagar
                </button>
                <button onClick={() => setActiveTab('compras')} className={`px-5 py-2.5 rounded-xl font-bold transition-all flex items-center gap-2 ${activeTab === 'compras' ? 'bg-blue-600 text-white shadow-md' : 'bg-white text-slate-600 hover:bg-slate-50'}`}>
                    <Box size={18} /> Compras de Mercadería
                </button>
                <button onClick={() => setActiveTab('proveedores')} className={`px-5 py-2.5 rounded-xl font-bold transition-all flex items-center gap-2 ${activeTab === 'proveedores' ? 'bg-blue-600 text-white shadow-md' : 'bg-white text-slate-600 hover:bg-slate-50'}`}>
                    <Users size={18} /> Proveedores
                </button>
            </div>

            <div className="bg-white rounded-3xl p-6 border border-slate-100 shadow-sm min-h-[500px]">
                {loading ? (
                    <div className="flex justify-center items-center h-40 text-slate-400">Cargando datos...</div>
                ) : (
                    <>
                        {/* TAB: FLUJO */}
                        {activeTab === 'flujo' && (
                            <div>
                                <h2 className="text-xl font-black text-slate-800 flex items-center gap-2 mb-6">
                                    <DollarSign className="text-blue-500" /> Nuevo Ingreso/Egreso Manual
                                </h2>
                                <form onSubmit={handleCreateTransaction} className="grid grid-cols-1 md:grid-cols-6 gap-4 mb-8 bg-slate-50 p-6 rounded-2xl border border-slate-100">
                                    <div className="space-y-1">
                                        <label className="text-xs font-bold text-slate-400 uppercase">Tipo</label>
                                        <select value={txForm.tipo} onChange={e => setTxForm({...txForm, tipo: e.target.value})} className="w-full p-3 bg-white border border-slate-200 rounded-xl outline-none font-bold text-slate-700">
                                            <option value="INGRESO">Ingreso (+)</option>
                                            <option value="EGRESO">Egreso (-)</option>
                                        </select>
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-xs font-bold text-slate-400 uppercase">Categoría</label>
                                        <select value={txForm.categoria} onChange={e => setTxForm({...txForm, categoria: e.target.value})} className="w-full p-3 bg-white border border-slate-200 rounded-xl outline-none font-bold text-slate-700">
                                            <option value="OPERATIVO">OPERATIVO</option>
                                            <option value="MERCADERIA">MERCADERIA</option>
                                            <option value="LOGISTICA">LOGISTICA</option>
                                            <option value="DEPOSITO">DEPOSITO</option>
                                            <option value="IMPUESTOS">IMPUESTOS</option>
                                            <option value="OTROS">OTROS</option>
                                        </select>
                                    </div>
                                    <div className="space-y-1 md:col-span-2">
                                        <label className="text-xs font-bold text-slate-400 uppercase">Descripción</label>
                                        <input required value={txForm.descripcion} onChange={e => setTxForm({...txForm, descripcion: e.target.value})} placeholder="Ej: Pago alquiler, Venta extra..." className="w-full p-3 bg-white border border-slate-200 rounded-xl outline-none font-medium text-slate-700" />
                                    </div>
                                    <div className="md:col-span-6 bg-white p-5 rounded-2xl border border-slate-200 mt-2 mb-2 shadow-sm">
                                        <div className="flex flex-col md:flex-row gap-6 items-start md:items-center">
                                            <div className="flex-1 w-full">
                                                <label className="text-xs font-bold text-slate-400 uppercase mb-2 block">Monto del Movimiento</label>
                                                <div className="relative flex items-center">
                                                    <span className="absolute left-6 text-2xl font-black text-slate-400">$</span>
                                                    <input required type="text" value={txForm.monto} onChange={handleMontoChange} placeholder="0" className="w-full pl-12 pr-6 py-4 bg-slate-50 border-2 border-slate-200 focus:border-blue-500 rounded-xl outline-none text-3xl md:text-5xl font-black text-right text-slate-800 transition-colors" />
                                                </div>
                                            </div>
                                            <div className="w-full md:w-56">
                                                <label className="text-xs font-bold text-slate-400 uppercase mb-2 block">Moneda</label>
                                                <select value={txForm.moneda} onChange={e => setTxForm({...txForm, moneda: e.target.value})} className="w-full px-6 py-4 bg-slate-50 border-2 border-slate-200 focus:border-blue-500 rounded-xl outline-none text-2xl font-black text-slate-700 h-[76px] md:h-[90px] transition-colors">
                                                    <option value="ARS">ARS</option>
                                                    <option value="USD">USD</option>
                                                </select>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-xs font-bold text-slate-400 uppercase">Fecha (Opcional)</label>
                                        <input type="date" value={txForm.fecha} onChange={e => setTxForm({...txForm, fecha: e.target.value})} className="w-full p-3 bg-white border border-slate-200 rounded-xl outline-none font-medium text-slate-700" />
                                    </div>
                                    <div className="md:col-span-6 flex justify-end mt-2">
                                        <button type="submit" disabled={!txForm.monto || !txForm.descripcion} className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold flex items-center gap-2 disabled:opacity-50 transition-colors">
                                            <Plus size={18} /> Registrar Movimiento
                                        </button>
                                    </div>
                                </form>

                                <h3 className="font-bold text-sm text-slate-500 mb-4 uppercase tracking-wider">Historial de Movimientos Reales</h3>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left border-collapse">
                                        <thead>
                                            <tr className="border-b-2 border-slate-100 text-slate-400 text-xs uppercase tracking-wider">
                                                <th className="py-3 px-2 font-bold">Fecha</th>
                                                <th className="py-3 px-2 font-bold">Concepto</th>
                                                <th className="py-3 px-2 font-bold">Categoría</th>
                                                <th className="py-3 px-2 font-bold text-right">Monto Original</th>
                                                <th className="py-3 px-2 font-bold text-right">Total Estimado ARS</th>
                                                <th className="py-3 px-2 font-bold text-center">Estado</th>
                                            </tr>
                                        </thead>
                                        <tbody className="text-sm">
                                            {transactions.filter(t => t.tipo_movimiento !== 'CUENTA_POR_PAGAR').map(tx => (
                                                <tr key={tx.id} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                                                    <td className="py-3 px-2 text-slate-500 font-medium">{new Date(tx.fecha).toLocaleDateString('es-AR')}</td>
                                                    <td className="py-3 px-2 font-bold text-slate-800">{formatType(tx.tipo_movimiento)} <span className="text-slate-600 font-normal ml-2">{tx.descripcion}</span></td>
                                                    <td className="py-3 px-2 text-slate-500 font-medium">{tx.categoria}</td>
                                                    <td className="py-3 px-2 text-right font-bold text-slate-700">
                                                        {formatCurrency(tx.monto, tx.moneda)}
                                                    </td>
                                                    <td className="py-3 px-2 text-right text-slate-500 font-medium">
                                                        {tx.moneda === 'USD' ? formatCurrency(tx.monto * exchangeRate, 'ARS') : '-'}
                                                    </td>
                                                    <td className="py-3 px-2 text-center">{formatStatus(tx.estado)}</td>
                                                </tr>
                                            ))}
                                            {transactions.filter(t => t.tipo_movimiento !== 'CUENTA_POR_PAGAR').length === 0 && (
                                                <tr><td colSpan={6} className="text-center py-8 text-slate-400">No hay movimientos registrados.</td></tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}

                        {/* TAB: CUENTAS POR PAGAR */}
                        {activeTab === 'cuentas' && (
                            <div>
                                <h3 className="font-bold text-sm text-slate-500 mb-4 uppercase tracking-wider">Cuentas por Pagar (Deudas Activas)</h3>
                                <div className="space-y-4">
                                    {transactions.filter(t => t.tipo_movimiento === 'CUENTA_POR_PAGAR' && t.estado !== 'PAGADO').map(tx => (
                                        <div key={tx.id} className={`flex items-center justify-between p-5 rounded-2xl border ${tx.estado === 'VENCIDO' ? 'bg-red-50 border-red-100' : 'bg-white border-slate-200'} shadow-sm`}>
                                            <div className="flex gap-4 items-center">
                                                <div className={`p-3 rounded-xl ${tx.estado === 'VENCIDO' ? 'bg-red-100 text-red-600' : 'bg-orange-100 text-orange-600'}`}>
                                                    <AlertTriangle size={24} />
                                                </div>
                                                <div>
                                                    <h4 className="font-black text-slate-800 text-lg">{tx.descripcion}</h4>
                                                    <div className="flex items-center gap-3 mt-1 text-sm text-slate-500 font-medium">
                                                        <span className="flex items-center gap-1"><Calendar size={14} /> Creado: {new Date(tx.fecha).toLocaleDateString('es-AR')}</span>
                                                        <span className={`flex items-center gap-1 font-bold ${tx.estado === 'VENCIDO' ? 'text-red-600' : 'text-slate-600'}`}>
                                                            Vence: {tx.fecha_vencimiento ? new Date(tx.fecha_vencimiento).toLocaleDateString('es-AR') : '-'}
                                                        </span>
                                                        {formatStatus(tx.estado)}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-6">
                                                <div className="text-right">
                                                    <div className="font-black text-slate-800 text-xl">{formatCurrency(tx.monto, tx.moneda)}</div>
                                                    {tx.moneda === 'USD' && <div className="text-xs text-slate-400 font-medium">~ {formatCurrency(tx.monto * exchangeRate, 'ARS')} ARS</div>}
                                                </div>
                                                {tx.compra_id && (
                                                    <button onClick={() => handlePayPurchase(tx.compra_id)} className="px-5 py-2 bg-green-600 hover:bg-green-700 text-white font-bold rounded-xl transition-colors shadow-sm">
                                                        Registrar Pago
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                    {transactions.filter(t => t.tipo_movimiento === 'CUENTA_POR_PAGAR' && t.estado !== 'PAGADO').length === 0 && (
                                        <div className="text-center py-12 text-slate-400 bg-slate-50 rounded-2xl border border-dashed border-slate-200">
                                            No tienes cuentas por pagar pendientes. ¡Excelente!
                                        </div>
                                    )}
                                </div>
                                
                                <h3 className="font-bold text-sm text-slate-500 mt-8 mb-4 uppercase tracking-wider">Historial de Deudas Saldadas</h3>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left border-collapse">
                                        <thead>
                                            <tr className="border-b-2 border-slate-100 text-slate-400 text-xs uppercase tracking-wider">
                                                <th className="py-3 px-2 font-bold">Fecha Pago</th>
                                                <th className="py-3 px-2 font-bold">Concepto</th>
                                                <th className="py-3 px-2 font-bold text-right">Monto</th>
                                                <th className="py-3 px-2 font-bold text-center">Estado</th>
                                            </tr>
                                        </thead>
                                        <tbody className="text-sm">
                                            {transactions.filter(t => t.tipo_movimiento === 'CUENTA_POR_PAGAR' && t.estado === 'PAGADO').map(tx => (
                                                <tr key={tx.id} className="border-b border-slate-50">
                                                    <td className="py-3 px-2 text-slate-500 font-medium">{new Date(tx.fecha).toLocaleDateString('es-AR')}</td>
                                                    <td className="py-3 px-2 font-bold text-slate-700">{tx.descripcion}</td>
                                                    <td className="py-3 px-2 text-right font-bold text-slate-700">{formatCurrency(tx.monto, tx.moneda)}</td>
                                                    <td className="py-3 px-2 text-center">{formatStatus(tx.estado)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}

                        {/* TAB: COMPRAS / MERCADERIA */}
                        {activeTab === 'compras' && (
                            <div>
                                <div className="flex justify-between items-center mb-6">
                                    <h3 className="font-bold text-sm text-slate-500 uppercase tracking-wider">Registro de Compras (Lotes/Contenedores)</h3>
                                    <button onClick={() => setIsPurchaseModalOpen(true)} className="px-5 py-2 bg-slate-900 text-white font-bold rounded-xl hover:bg-slate-800 transition-colors flex items-center gap-2">
                                        <Plus size={16} /> Nueva Compra
                                    </button>
                                </div>

                                {/* Formulario en In-line Modal o simple Div colapsable */}
                                {isPurchaseModalOpen && (
                                    <div className="bg-slate-50 p-6 rounded-2xl border border-slate-200 mb-8 shadow-inner">
                                        <h4 className="font-black text-lg text-slate-800 mb-4 tracking-tight">Registrar Lote de Mercadería</h4>
                                        <form onSubmit={handleCreatePurchase}>
                                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                                                <div className="space-y-1 lg:col-span-2">
                                                    <label className="text-xs font-bold text-slate-500 uppercase">Descripción / Referencia</label>
                                                    <input required value={purchaseForm.descripcion} onChange={e => setPurchaseForm({...purchaseForm, descripcion: e.target.value})} placeholder="Ej: Importación China Lote 44" className="w-full p-2.5 bg-white border border-slate-300 rounded-lg outline-none focus:border-blue-500 font-medium text-slate-700" />
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-xs font-bold text-slate-500 uppercase">Proveedor</label>
                                                    <select value={purchaseForm.proveedor_id} onChange={e => setPurchaseForm({...purchaseForm, proveedor_id: e.target.value})} className="w-full p-2.5 bg-white border border-slate-300 rounded-lg outline-none font-medium text-slate-700">
                                                        <option value="">-- Seleccionar --</option>
                                                        {suppliers.map(s => <option key={s.id} value={s.id}>{s.nombre}</option>)}
                                                    </select>
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-xs font-bold text-slate-500 uppercase">Unidades Totales</label>
                                                    <input required type="number" value={purchaseForm.cantidad_total} onChange={e => setPurchaseForm({...purchaseForm, cantidad_total: e.target.value})} placeholder="Ej: 5000" className="w-full p-2.5 bg-white border border-slate-300 rounded-lg outline-none font-bold text-slate-800 text-right" />
                                                </div>
                                                
                                                <div className="space-y-1 lg:col-span-2">
                                                    <label className="text-xs font-bold text-slate-500 uppercase">Modo de Pago</label>
                                                    <select required value={purchaseForm.tipo_pago} onChange={e => setPurchaseForm({...purchaseForm, tipo_pago: e.target.value})} className="w-full p-2.5 bg-white border border-slate-300 rounded-lg outline-none font-bold text-slate-800">
                                                        <option value="CONTADO">Contado (Afecta caja inmediato)</option>
                                                        <option value="30_DIAS">Cuenta por Pagar a 30 Días</option>
                                                        <option value="60_DIAS">Cuenta por Pagar a 60 Días</option>
                                                    </select>
                                                </div>
                                                <div className="space-y-1 lg:col-span-2">
                                                    <label className="text-xs font-bold text-slate-500 uppercase">Moneda Base</label>
                                                    <select required value={purchaseForm.moneda} onChange={e => setPurchaseForm({...purchaseForm, moneda: e.target.value})} className="w-full p-2.5 bg-white border border-slate-300 rounded-lg outline-none font-bold text-slate-800">
                                                        <option value="ARS">ARS - Pesos</option>
                                                        <option value="USD">USD - Dólares</option>
                                                    </select>
                                                </div>
                                            </div>

                                            <div className="bg-white p-4 rounded-xl border border-slate-200 mb-6">
                                                <h5 className="font-bold text-slate-700 mb-3 flex items-center gap-2"><DollarSign size={16}/> Composición del Costo Real</h5>
                                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                                                    <div>
                                                        <label className="text-xs font-bold text-slate-400 uppercase">Costo Mercadería</label>
                                                        <input required type="number" step="0.01" value={purchaseForm.cost_producto} onChange={e => setPurchaseForm({...purchaseForm, cost_producto: e.target.value})} placeholder="0.00" className="w-full p-2 border-b-2 border-slate-200 focus:border-blue-500 outline-none text-right font-bold" />
                                                    </div>
                                                    <div>
                                                        <label className="text-xs font-bold text-slate-400 uppercase">Logística / Flete</label>
                                                        <input type="number" step="0.01" value={purchaseForm.cost_flete} onChange={e => setPurchaseForm({...purchaseForm, cost_flete: e.target.value})} placeholder="0.00" className="w-full p-2 border-b-2 border-slate-200 focus:border-blue-500 outline-none text-right font-bold" />
                                                    </div>
                                                    <div>
                                                        <label className="text-xs font-bold text-slate-400 uppercase">Impuestos / Aduana</label>
                                                        <input type="number" step="0.01" value={purchaseForm.cost_impuestos} onChange={e => setPurchaseForm({...purchaseForm, cost_impuestos: e.target.value})} placeholder="0.00" className="w-full p-2 border-b-2 border-slate-200 focus:border-blue-500 outline-none text-right font-bold" />
                                                    </div>
                                                    <div>
                                                        <label className="text-xs font-bold text-slate-400 uppercase">Otros Gastos</label>
                                                        <input type="number" step="0.01" value={purchaseForm.cost_otros} onChange={e => setPurchaseForm({...purchaseForm, cost_otros: e.target.value})} placeholder="0.00" className="w-full p-2 border-b-2 border-slate-200 focus:border-blue-500 outline-none text-right font-bold" />
                                                    </div>
                                                </div>
                                                <div className="mt-4 p-3 bg-blue-50 text-blue-800 rounded-lg text-sm flex justify-between font-bold">
                                                    <span>Total Estimado de la Compra:</span>
                                                    <span>{formatCurrency((parseFloat(purchaseForm.cost_producto||'0') + parseFloat(purchaseForm.cost_flete||'0') + parseFloat(purchaseForm.cost_impuestos||'0') + parseFloat(purchaseForm.cost_otros||'0')), purchaseForm.moneda)}</span>
                                                </div>
                                            </div>

                                            <div className="flex justify-end gap-3">
                                                <button type="button" onClick={() => setIsPurchaseModalOpen(false)} className="px-5 py-2.5 text-slate-500 font-bold hover:text-slate-700">Cancelar</button>
                                                <button type="submit" disabled={!purchaseForm.descripcion || !purchaseForm.cantidad_total || !purchaseForm.cost_producto} className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition-colors">Guardar Compra</button>
                                            </div>
                                        </form>
                                    </div>
                                )}

                                <div className="space-y-4">
                                    {purchases.map(p => (
                                        <div key={p.id} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex flex-col lg:flex-row gap-6 justify-between items-start lg:items-center">
                                            <div>
                                                <h4 className="font-black text-slate-800 text-lg flex items-center gap-2">
                                                    {p.descripcion}
                                                </h4>
                                                <div className="flex flex-wrap gap-4 mt-2 text-sm text-slate-500">
                                                    <span className="font-bold">Total: {formatCurrency(p.monto_total, p.moneda)}</span>
                                                    <span>Cantidad: {p.cantidad_total} u</span>
                                                    <span>Fecha: {new Date(p.fecha_compra).toLocaleDateString('es-AR')}</span>
                                                    <span>Pago: {p.tipo_pago.replace('_', ' ')}</span>
                                                    {formatStatus(p.estado)}
                                                </div>
                                            </div>
                                            
                                            <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 min-w-[200px] text-right">
                                                <div className="text-xs font-bold text-slate-400 uppercase mb-1">Costo Real Unitario Final</div>
                                                <div className="text-2xl font-black text-blue-600 mr-1">
                                                    {formatCurrency(p.costo_real_unitario, p.moneda)}
                                                </div>
                                                <div className="text-[10px] text-slate-400 uppercase mt-1 px-1">Producto + Costos / Unidades</div>
                                            </div>
                                        </div>
                                    ))}
                                    {purchases.length === 0 && <p className="text-slate-400 p-4 text-center">No hay compras registradas.</p>}
                                </div>
                            </div>
                        )}

                        {/* TAB: PROVEEDORES */}
                        {activeTab === 'proveedores' && (
                            <div>
                                <h3 className="font-bold text-sm text-slate-500 mb-4 uppercase tracking-wider">Gestión de Proveedores</h3>
                                
                                <form onSubmit={handleCreateSupplier} className="flex flex-wrap items-end gap-4 p-5 bg-slate-50 border border-slate-200 rounded-xl mb-6">
                                    <div className="flex-1 min-w-[200px] space-y-1">
                                        <label className="text-xs font-bold text-slate-400 uppercase">Razón Social / Nombre</label>
                                        <input required value={supplierForm.nombre} onChange={e => setSupplierForm({...supplierForm, nombre: e.target.value})} className="w-full p-2 border-b-2 border-slate-200 focus:border-blue-500 outline-none bg-transparent font-bold text-slate-800" />
                                    </div>
                                    <div className="w-[150px] space-y-1">
                                        <label className="text-xs font-bold text-slate-400 uppercase">Contacto (Persona)</label>
                                        <input value={supplierForm.contacto} onChange={e => setSupplierForm({...supplierForm, contacto: e.target.value})} className="w-full p-2 border-b-2 border-slate-200 focus:border-blue-500 outline-none bg-transparent text-slate-700" />
                                    </div>
                                    <div className="w-[150px] space-y-1">
                                        <label className="text-xs font-bold text-slate-400 uppercase">Teléfono</label>
                                        <input value={supplierForm.telefono} onChange={e => setSupplierForm({...supplierForm, telefono: e.target.value})} className="w-full p-2 border-b-2 border-slate-200 focus:border-blue-500 outline-none bg-transparent text-slate-700" />
                                    </div>
                                    <div className="w-[200px] space-y-1">
                                        <label className="text-xs font-bold text-slate-400 uppercase">Email</label>
                                        <input type="email" value={supplierForm.email} onChange={e => setSupplierForm({...supplierForm, email: e.target.value})} className="w-full p-2 border-b-2 border-slate-200 focus:border-blue-500 outline-none bg-transparent text-slate-700" />
                                    </div>
                                    <button type="submit" disabled={!supplierForm.nombre} className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition-colors disabled:opacity-50">
                                        Agregar Proveedor
                                    </button>
                                </form>

                                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                                    {suppliers.map(s => (
                                        <div key={s.id} className="bg-white border border-slate-200 p-5 rounded-2xl shadow-sm">
                                            <div className="font-black text-slate-800 text-lg mb-2">{s.nombre}</div>
                                            <div className="space-y-1 text-sm text-slate-600">
                                                {s.contacto && <div><span className="font-bold mr-1">Contacto:</span> {s.contacto}</div>}
                                                {s.telefono && <div><span className="font-bold mr-1">Tel:</span> {s.telefono}</div>}
                                                {s.email && <div><span className="font-bold mr-1">Email:</span> {s.email}</div>}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
