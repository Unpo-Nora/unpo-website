"use client";

import React, { useState, useEffect } from 'react';
import { DollarSign, Plus, Trash2, Box, PackagePlus } from 'lucide-react';
import ProductModal from './ProductModal';
import { useAuth } from '@/context/AuthContext';

export default function PurchasesDashboard() {
    const { user } = useAuth();
    const [amount, setAmount] = useState('');
    const [description, setDescription] = useState('');
    const [date, setDate] = useState('');
    const [expenses, setExpenses] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    
    const [isProductModalOpen, setIsProductModalOpen] = useState(false);

    const fetchExpenses = async () => {
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/analytics/expenses`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setExpenses(data);
            }
        } catch (e) {}
    };

    useEffect(() => {
        fetchExpenses();
    }, []);

    const handleAddExpense = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/analytics/expenses`, {
                method: 'POST',
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ amount: parseFloat(amount), description, date: date ? new Date(date).toISOString() : undefined })
            });
            if (res.ok) {
                setAmount('');
                setDescription('');
                setDate('');
                fetchExpenses();
            }
        } catch (error) {}
        setLoading(false);
    };

    const handleDeleteExpense = async (id: number) => {
        if (!confirm("¿Borrar gasto?")) return;
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/analytics/expenses/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                fetchExpenses();
            }
        } catch (error) {}
    };

    return (
        <div className="space-y-6">
            
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Compras y Gastos</h1>
                    <p className="text-slate-500 mt-1">Registra importaciones, nuevos productos, limpieza, comisiones, etc.</p>
                </div>
                {/* Nuevo Producto goes here! */}
                {user?.role === 'admin' && (
                    <button
                        onClick={() => setIsProductModalOpen(true)}
                        className="flex items-center gap-2 px-6 py-3 rounded-2xl font-bold bg-green-600 text-white hover:bg-green-700 shadow-lg shadow-green-200 transition-all"
                    >
                        <PackagePlus size={20} />
                        Crear Nuevo Producto
                    </button>
                )}
            </div>

            <div className="bg-white rounded-3xl p-6 border border-slate-100 shadow-sm">
                <h2 className="text-xl font-black text-slate-800 flex items-center gap-2 mb-6">
                    <DollarSign className="text-red-500" />
                    Registrar Gasto o Egreso
                </h2>
                
                <form onSubmit={handleAddExpense} className="flex flex-col sm:flex-row gap-4 mb-8">
                    <div className="flex-1 space-y-1">
                        <label className="text-xs font-bold text-slate-400 uppercase">Detalle / Motivo</label>
                        <input 
                            required 
                            type="text"
                            value={description}
                            onChange={e => setDescription(e.target.value)}
                            placeholder="Ej: Despachante, Artículos limpieza..."
                            className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:border-red-500 outline-none font-medium"
                        />
                    </div>
                    <div className="w-full sm:w-40 space-y-1">
                        <label className="text-xs font-bold text-slate-400 uppercase">Monto ($)</label>
                        <input 
                            required 
                            type="number" 
                            min="1"
                            value={amount}
                            onChange={e => setAmount(e.target.value)}
                            className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:border-red-500 outline-none font-bold text-right"
                        />
                    </div>
                    <div className="w-full sm:w-40 space-y-1">
                        <label className="text-xs font-bold text-slate-400 uppercase">Fecha</label>
                        <input 
                            type="date"
                            value={date}
                            onChange={e => setDate(e.target.value)}
                            className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:border-red-500 outline-none font-medium text-slate-700"
                        />
                    </div>
                    <div className="flex items-end">
                        <button 
                            disabled={loading || !amount || !description}
                            type="submit" 
                            className="h-[46px] px-6 bg-red-600 hover:bg-red-700 text-white rounded-xl font-bold flex items-center gap-2 disabled:opacity-50"
                        >
                            <Plus size={18} /> Añadir Gasto
                        </button>
                    </div>
                </form>

                <h3 className="font-bold text-sm text-slate-500 mb-4 uppercase tracking-wider">Historial Reciente de Gastos</h3>
                <div className="space-y-3">
                    {expenses.length === 0 && <p className="text-sm text-slate-400">No hay gastos registrados por el momento.</p>}
                    {expenses.map(e => (
                        <div key={e.id} className="flex items-center justify-between p-4 bg-slate-50 rounded-2xl border border-slate-100 hover:bg-slate-100 transition-colors">
                            <div>
                                <div className="font-bold text-slate-800 text-base">{e.description}</div>
                                <div className="text-xs text-slate-400 font-medium whitespace-nowrap">
                                    {new Date(e.date).toLocaleString('es-AR')}
                                    {e.user_email && <span className="ml-2 text-indigo-400">por {e.user_email}</span>}
                                </div>
                            </div>
                            <div className="flex items-center gap-6">
                                <div className="font-black text-red-600 text-lg">-$ {Number(e.amount).toLocaleString('es-AR')}</div>
                                <button 
                                    onClick={() => handleDeleteExpense(e.id)} 
                                    className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                    title="Eliminar gasto"
                                >
                                    <Trash2 size={18} />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <ProductModal
                isOpen={isProductModalOpen}
                onClose={() => setIsProductModalOpen(false)}
                onSave={() => setIsProductModalOpen(false)}
                product={null} // ProductModal checks if product is null, it means 'create'
            />
        </div>
    );
}
