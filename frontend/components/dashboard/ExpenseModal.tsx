import React, { useState, useEffect } from 'react';
import { X, DollarSign, Plus, Trash2 } from 'lucide-react';

export default function ExpenseModal({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
    const [amount, setAmount] = useState('');
    const [description, setDescription] = useState('');
    const [expenses, setExpenses] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);

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
        if (isOpen) {
            fetchExpenses();
        }
    }, [isOpen]);

    const handleAdd = async (e: React.FormEvent) => {
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
                body: JSON.stringify({ amount: parseFloat(amount), description })
            });
            if (res.ok) {
                setAmount('');
                setDescription('');
                fetchExpenses();
            }
        } catch (error) {}
        setLoading(false);
    };

    const handleDelete = async (id: number) => {
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

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-3xl w-full max-w-xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
                <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-slate-50">
                    <h2 className="text-xl font-black text-slate-800 flex items-center gap-2">
                        <DollarSign className="text-red-500" />
                        Registro de Gastos
                    </h2>
                    <button onClick={onClose} className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-colors">
                        <X size={20} />
                    </button>
                </div>
                
                <div className="p-6 overflow-y-auto">
                    <form onSubmit={handleAdd} className="flex flex-col sm:flex-row gap-4 mb-6">
                        <div className="flex-1 space-y-1">
                            <label className="text-xs font-bold text-slate-400 uppercase">Gasto / Motivo</label>
                            <input 
                                required 
                                type="text"
                                value={description}
                                onChange={e => setDescription(e.target.value)}
                                placeholder="Ej: Flete, Alquiler..."
                                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:border-red-500 outline-none font-medium"
                            />
                        </div>
                        <div className="w-full sm:w-32 space-y-1">
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
                        <div className="flex items-end">
                            <button 
                                disabled={loading}
                                type="submit" 
                                className="h-[46px] px-4 bg-red-600 hover:bg-red-700 text-white rounded-xl font-bold flex items-center gap-2 disabled:opacity-50"
                            >
                                <Plus size={18} /> Añadir
                            </button>
                        </div>
                    </form>

                    <h3 className="font-bold text-sm text-slate-500 mb-3 uppercase tracking-wider">Historial de Gastos</h3>
                    <div className="space-y-2">
                        {expenses.length === 0 && <p className="text-sm text-slate-400">No hay gastos registrados.</p>}
                        {expenses.map(e => (
                            <div key={e.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
                                <div>
                                    <div className="font-bold text-slate-800">{e.description}</div>
                                    <div className="text-xs text-slate-400">{new Date(e.date).toLocaleDateString('es-AR')}</div>
                                </div>
                                <div className="flex items-center gap-4">
                                    <div className="font-black text-red-600">-$ {Number(e.amount).toLocaleString('es-AR')}</div>
                                    <button 
                                        onClick={() => handleDelete(e.id)} 
                                        className="text-slate-300 hover:text-red-500 transition-colors"
                                        title="Eliminar gasto"
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
