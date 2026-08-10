"use client";

import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { User, Lock, Loader2, AlertCircle, RotateCcw } from 'lucide-react';
import { API_URL } from '@/lib/api';

export default function NoraLoginPage() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            const formData = new URLSearchParams();
            formData.append('username', email);
            formData.append('password', password);

            const response = await fetch(`${API_URL}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData,
            });

            if (response.ok) {
                const data = await response.json();
                await login(data.access_token, "/nora-admin");
            } else {
                let detail: string | undefined;
                try {
                    const data = await response.json();
                    detail = data.detail;
                } catch {
                    // cuerpo no-JSON: se usa el mensaje por defecto
                }
                setError(detail || "Email o contraseña incorrectos");
            }
        } catch (err) {
            setError("No se pudo conectar con el servidor de autenticación");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
            <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 border border-slate-100">
                <div className="text-center mb-8">
                    <div className="w-12 h-12 bg-slate-900 text-white rounded-lg flex items-center justify-center font-serif font-bold text-xl mx-auto mb-4">
                        N
                    </div>
                    <h2 className="text-3xl font-serif font-medium text-slate-900">CRM NORA</h2>
                    <p className="text-slate-500 mt-2">Ingresá tus credenciales para continuar</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
                        <div className="relative">
                            <User className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                            <input
                                type="email"
                                required
                                className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-slate-200 focus:border-slate-400 outline-none transition-all"
                                placeholder="tu@email.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Contraseña</label>
                        <div className="relative">
                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                            <input
                                type="password"
                                required
                                className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-slate-200 focus:border-slate-400 outline-none transition-all"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                            />
                        </div>
                    </div>

                    {error && (
                        <div className="p-3 bg-red-50 border border-red-100 rounded-lg flex items-center gap-2 text-red-600 text-sm">
                            <AlertCircle size={16} />
                            <span>{error}</span>
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full py-3 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-xl transition-all shadow-lg flex items-center justify-center"
                    >
                        {loading ? <Loader2 className="animate-spin" /> : "Iniciar Sesión"}
                    </button>
                </form>

                <div className="mt-8 text-center pt-6 border-t border-slate-100">
                    <button
                        onClick={() => window.location.href = '/nora'}
                        className="text-slate-400 hover:text-slate-900 text-sm font-medium transition-colors flex items-center justify-center gap-2 mx-auto"
                    >
                        <RotateCcw size={14} />
                        Volver a NORA
                    </button>
                </div>
            </div>
        </div>
    );
}
