"use client";

import { useState } from 'react';
import { Send, Loader2, CheckCircle } from 'lucide-react';

export default function ContactForm() {
    const [isLoading, setIsLoading] = useState(false);
    const [isSuccess, setIsSuccess] = useState(false);
    const [formData, setFormData] = useState({
        full_name: '',
        email: '',
        phone: '',
        business_type: '',
        purchase_volume: '',
        category_interest: '',
        experience_level: '',
        notes: ''
    });

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!formData.full_name || !formData.email || !formData.phone || !formData.business_type || !formData.category_interest || !formData.purchase_volume || !formData.experience_level || !formData.notes) {
            alert("Por favor completa todos los campos obligatorios antes de enviar.");
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
                    source: 'WEB_UNPO'
                }),
            });

            if (response.ok) {
                setIsSuccess(true);
                setFormData({
                    full_name: '',
                    email: '',
                    phone: '',
                    business_type: '',
                    purchase_volume: '',
                    category_interest: '',
                    experience_level: '',
                    notes: ''
                });
            } else {
                alert("Hubo un error al enviar el formulario. Por favor intenta nuevamente.");
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
            <div className="bg-green-50 p-8 rounded-2xl border border-green-200 text-center">
                <div className="flex justify-center mb-4">
                    <CheckCircle className="w-16 h-16 text-green-500" />
                </div>
                <h3 className="text-2xl font-bold text-green-800 mb-2">¡Mensaje Enviado!</h3>
                <p className="text-green-700">
                    Gracias por contactarnos. Un asesor comercial revisará tu perfil y te contactará a la brevedad.
                </p>
                <button
                    onClick={() => setIsSuccess(false)}
                    className="mt-6 text-green-600 hover:text-green-800 font-medium underline"
                >
                    Enviar otro mensaje
                </button>
            </div>
        );
    }

    return (
        <section id="contact" className="py-24 bg-white">
            <div className="max-w-3xl mx-auto px-6">
                <div className="text-center mb-12">
                    <h2 className="text-4xl font-bold text-slate-900 mb-4">Empecemos a Trabajar Juntos</h2>
                    <p className="text-lg text-slate-600">
                        Completa el formulario para que podamos asignarte un asesor especializado en tu rubro.
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6 bg-slate-50 p-8 rounded-2xl shadow-sm border border-slate-100">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">Nombre Completo</label>
                            <input
                                required
                                name="full_name"
                                value={formData.full_name}
                                onChange={handleChange}
                                type="text"
                                className="w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none transition-all"
                                placeholder="Juan Pérez"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">Email Profesional</label>
                            <input
                                required
                                name="email"
                                value={formData.email}
                                onChange={handleChange}
                                type="email"
                                className="w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none transition-all"
                                placeholder="juan@empresa.com"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">Teléfono / WhatsApp</label>
                            <input
                                required
                                name="phone"
                                value={formData.phone}
                                onChange={handleChange}
                                type="tel"
                                className="w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none transition-all"
                                placeholder="+54 9 11..."
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">Tipo de Negocio</label>
                            <select
                                required
                                name="business_type"
                                value={formData.business_type}
                                onChange={handleChange}
                                className="w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none transition-all bg-white"
                            >
                                <option value="">Selecciona una opción</option>
                                <option value="Local físico (Bazar/Deco)">Local físico (Bazar/Deco)</option>
                                <option value="Tienda Online / E-commerce">Tienda Online / E-commerce</option>
                                <option value="Showroom">Showroom</option>
                                <option value="Distribuidora">Distribuidora</option>
                                <option value="Revendedor Independiente">Revendedor Independiente</option>
                            </select>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">Categoría Principal</label>
                            <select
                                required
                                name="category_interest"
                                value={formData.category_interest}
                                onChange={handleChange}
                                className="w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none transition-all bg-white"
                            >
                                <option value="">Selecciona una opción</option>
                                <option value="Tecnología">Tecnología</option>
                                <option value="Hogar y Deco">Hogar y Deco</option>
                                <option value="Audio">Audio</option>
                                <option value="Mix Completo">Mix Completo</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700 mb-2">Volumen de Compra Est.</label>
                            <select
                                required
                                name="purchase_volume"
                                value={formData.purchase_volume}
                                onChange={handleChange}
                                className="w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none transition-all bg-white"
                            >
                                <option value="">Selecciona una opción</option>
                                <option value="Menos de $500.000">Menos de $500.000</option>
                                <option value="$500.000 - $1.500.000">$500.000 - $1.500.000</option>
                                <option value="Más de $1.500.000">Más de $1.500.000</option>
                            </select>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">Experiencia en el Rubro</label>
                        <div className="flex space-x-6 mt-2">
                            <label className="flex items-center space-x-2 cursor-pointer">
                                <input
                                    type="radio"
                                    name="experience_level"
                                    value="Soy nuevo"
                                    checked={formData.experience_level === 'Soy nuevo'}
                                    onChange={handleChange}
                                    className="text-blue-600 focus:ring-blue-500"
                                />
                                <span>Soy nuevo</span>
                            </label>
                            <label className="flex items-center space-x-2 cursor-pointer">
                                <input
                                    required
                                    type="radio"
                                    name="experience_level"
                                    value="Menos de 2 años"
                                    checked={formData.experience_level === 'Menos de 2 años'}
                                    onChange={handleChange}
                                    className="text-blue-600 focus:ring-blue-500"
                                />
                                <span>Menos de 2 años</span>
                            </label>
                            <label className="flex items-center space-x-2 cursor-pointer">
                                <input
                                    required
                                    type="radio"
                                    name="experience_level"
                                    value="Más de 2 años"
                                    checked={formData.experience_level === 'Más de 2 años'}
                                    onChange={handleChange}
                                    className="text-blue-600 focus:ring-blue-500"
                                />
                                <span>Más de 2 años</span>
                            </label>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">Mensaje / Consulta</label>
                        <textarea
                            required
                            name="notes"
                            value={formData.notes}
                            onChange={handleChange}
                            rows={4}
                            className="w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none transition-all"
                            placeholder="Cuéntanos más sobre tu negocio o qué productos estás buscando..."
                        ></textarea>
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
                                <span>Solicitar Asesoramiento</span>
                                <Send className="w-5 h-5" />
                            </>
                        )}
                    </button>

                    <p className="text-xs text-slate-400 text-center mt-4">
                        Al enviar este formulario aceptas ser contactado por el equipo de UNPO vía WhatsApp o Email.
                    </p>
                </form>
            </div>
        </section>
    );
}
