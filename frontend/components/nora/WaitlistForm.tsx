"use client";

import { useState } from 'react';
import { Send, Loader2, CheckCircle } from 'lucide-react';

export default function WaitlistForm() {
    const [isLoading, setIsLoading] = useState(false);
    const [isSuccess, setIsSuccess] = useState(false);
    const [formData, setFormData] = useState({
        full_name: '',
        email: '',
        product_interest: '',
        notes: ''
    });

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!formData.full_name || !formData.email || !formData.product_interest) {
            alert("Por favor, completa todos los campos del formulario para unirte a la Waitlist.");
            return;
        }

        setIsLoading(true);

        try {
            const response = await fetch('http://localhost:8000/leads/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    ...formData,
                    source: 'WEB_NORA'
                }),
            });

            if (response.ok) {
                setIsSuccess(true);
                setFormData({
                    full_name: '',
                    email: '',
                    product_interest: '',
                    notes: ''
                });
            } else {
                alert("Hubo un error al unirte a la lista. Por favor intenta nuevamente.");
            }
        } catch (error) {
            console.error(error);
            alert("Error de conexión con el servidor.");
        } finally {
            setIsLoading(false);
        }
    };

    if (isSuccess) {
        return (
            <div className="bg-white/10 backdrop-blur-md p-8 rounded-2xl border border-white/20 text-center">
                <div className="flex justify-center mb-4">
                    <CheckCircle className="w-16 h-16 text-green-400" />
                </div>
                <h3 className="text-2xl font-bold text-white mb-2">¡Estás en la lista!</h3>
                <p className="text-slate-300">
                    Te avisaremos apenas NORA esté disponible en tu zona.
                </p>
            </div>
        );
    }

    return (
        <section className="py-24 bg-slate-900">
            <div className="max-w-xl mx-auto px-6">
                <div className="text-center mb-12">
                    <span className="text-blue-400 text-sm font-bold tracking-widest uppercase mb-2 block">Premium Waitlist</span>
                    <h2 className="text-4xl font-bold text-white mb-4">Sé el Primero en Tener NORA</h2>
                    <p className="text-lg text-slate-400">
                        Únete a la lista de espera exclusiva y recibe beneficios especiales de lanzamiento.
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6 bg-white/5 backdrop-blur-sm p-8 rounded-2xl border border-white/10">
                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">Nombre Completo</label>
                        <input
                            required
                            name="full_name"
                            value={formData.full_name}
                            onChange={handleChange}
                            type="text"
                            className="w-full px-4 py-3 rounded-lg bg-white/10 border border-white/20 text-white placeholder-slate-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                            placeholder="Tu nombre"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">Email</label>
                        <input
                            required
                            name="email"
                            value={formData.email}
                            onChange={handleChange}
                            type="email"
                            className="w-full px-4 py-3 rounded-lg bg-white/10 border border-white/20 text-white placeholder-slate-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                            placeholder="tu@email.com"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">¿Qué producto te interesa más?</label>
                        <select
                            required
                            name="product_interest"
                            value={formData.product_interest}
                            onChange={handleChange}
                            className="w-full px-4 py-3 rounded-lg bg-white/10 border border-white/20 text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                        >
                            <option value="" className="bg-slate-800">Selecciona una opción</option>
                            <option value="Pro Series (TB135/TB90/TB65)" className="bg-slate-800">Pro Series (Smart Dual Zone)</option>
                            <option value="Classic Series (Coffee Table)" className="bg-slate-800">Classic Series (Mesa Neutra)</option>
                            <option value="Aún no lo sé, busco asesoramiento" className="bg-slate-800">Aún no lo sé, busco asesoramiento</option>
                        </select>
                    </div>

                    <button
                        type="submit"
                        disabled={isLoading}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 rounded-xl transition-all flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                <span>Uniendo...</span>
                            </>
                        ) : (
                            <>
                                <span>Unirme a la Waitlist</span>
                                <Send className="w-5 h-5" />
                            </>
                        )}
                    </button>
                </form>
            </div>
        </section>
    );
}
