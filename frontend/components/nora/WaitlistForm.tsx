"use client";

import { useState } from 'react';
import { Send, Loader2, CheckCircle } from 'lucide-react';

export default function WaitlistForm() {
    const [isLoading, setIsLoading] = useState(false);
    const [isSuccess, setIsSuccess] = useState(false);
    const [formData, setFormData] = useState({
        full_name: '',
        email: '',
        phone: '',
        product_interest: '',
        notes: ''
    });

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!formData.full_name || !formData.email || !formData.phone.trim() || !formData.product_interest) {
            alert("Por favor, completá tu nombre, email, teléfono y el producto de interés para que un asesor de NORA te contacte.");
            return;
        }

        setIsLoading(true);

        try {
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/leads/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    ...formData,
                    source: 'WEB_NORA',
                    platform: 'web'
                }),
            });

            if (response.ok) {
                const text = `Hola! Quiero recibir asesoramiento sobre NORA. Mi nombre es *${formData.full_name}* y me interesó la opción: *${formData.product_interest}*.`;
                const encodedText = encodeURIComponent(text);
                window.open(`https://wa.me/5491131488378?text=${encodedText}`, '_blank');

                setIsSuccess(true);
                setFormData({
                    full_name: '',
                    email: '',
                    phone: '',
                    product_interest: '',
                    notes: ''
                });
            } else {
                alert("Hubo un error al enviar tus datos. Por favor intentá nuevamente.");
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
                <h3 className="text-2xl font-bold text-white mb-2">¡Recibimos tus datos!</h3>
                <p className="text-slate-300">
                    Un asesor de NORA te va a contactar a la brevedad.
                </p>
            </div>
        );
    }

    return (
        <section id="waitlist" className="py-24 bg-slate-900">
            <div className="max-w-xl mx-auto px-6">
                <div className="text-center mb-12">
                    <span className="text-blue-400 text-sm font-bold tracking-widest uppercase mb-2 block">Asesoramiento NORA</span>
                    <h2 className="text-4xl font-bold text-white mb-4">Consultá por NORA</h2>
                    <p className="text-lg text-slate-400">
                        Dejanos tus datos y un asesor de NORA te contacta para ayudarte a elegir tu equipo.
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
                        <label className="block text-sm font-medium text-slate-300 mb-2">Teléfono / WhatsApp</label>
                        <input
                            required
                            name="phone"
                            value={formData.phone}
                            onChange={handleChange}
                            type="tel"
                            className="w-full px-4 py-3 rounded-lg bg-white/10 border border-white/20 text-white placeholder-slate-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                            placeholder="Ej: 11 2345 6789"
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
                                <span>Enviando...</span>
                            </>
                        ) : (
                            <>
                                <span>Quiero que me contacten</span>
                                <Send className="w-5 h-5" />
                            </>
                        )}
                    </button>
                </form>
            </div>
        </section>
    );
}
