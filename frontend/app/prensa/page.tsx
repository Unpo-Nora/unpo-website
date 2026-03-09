import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { Instagram, Facebook, Download } from 'lucide-react';
import Link from 'next/link';

export default function PrensaPage() {
    return (
        <main className="min-h-screen bg-white">
            <Navbar />

            <section className="pt-32 pb-16 bg-slate-50 border-b border-slate-200">
                <div className="max-w-4xl mx-auto px-6 text-center">
                    <h1 className="text-5xl font-bold text-slate-900 mb-6 tracking-tight">Prensa & Medios</h1>
                    <p className="text-xl text-slate-600 leading-relaxed">
                        Conoce más sobre UNPO S.A., nuestro proceso logístico, la calidad de nuestros productos
                        y mantente al tanto de todas las novedades en nuestras redes sociales.
                    </p>
                </div>
            </section>

            <section className="py-20">
                <div className="max-w-6xl mx-auto px-6">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

                        {/* Video Section */}
                        <div className="space-y-6">
                            <h2 className="text-3xl font-bold text-slate-900">Nuestros Comienzos</h2>
                            <p className="text-lg text-slate-600">
                                Desde la apertura de nuestro primer contenedor hasta la consolidación
                                como líderes en distribución mayorista. Te invitamos a ver cómo empezó todo
                                y el cuidado que ponemos en cada importación.
                            </p>
                            <div className="aspect-video bg-black rounded-2xl overflow-hidden shadow-lg border border-slate-100 flex items-center justify-center">
                                <video
                                    src="/videos/UNPO.mp4"
                                    className="w-full h-full object-cover"
                                    controls
                                    controlsList="nodownload"
                                    preload="metadata"
                                >
                                    Tu navegador no soporta la reproducción de videos.
                                </video>
                            </div>
                        </div>

                        {/* Social Media & Media Kit */}
                        <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100 space-y-10">

                            <div>
                                <h3 className="text-2xl font-bold text-slate-900 mb-4">Síguenos en las Redes</h3>
                                <p className="text-slate-600 mb-6">
                                    Únete a nuestra comunidad. Compartimos nuevos ingresos, procesos
                                    operativos y contenido exclusivo para nuestros clientes B2B.
                                </p>
                                <div className="flex flex-col sm:flex-row gap-4">
                                    <a
                                        href="https://instagram.com/unpo_oficial" // Update with real link
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center justify-center gap-3 px-6 py-4 bg-gradient-to-r from-purple-500 via-pink-500 to-orange-500 text-white rounded-xl font-medium hover:opacity-90 transition-opacity"
                                    >
                                        <Instagram className="w-5 h-5" />
                                        <span>Instagram</span>
                                    </a>

                                    <a
                                        href="https://facebook.com/unposa" // Update with real link
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center justify-center gap-3 px-6 py-4 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors"
                                    >
                                        <Facebook className="w-5 h-5" />
                                        <span>Facebook</span>
                                    </a>
                                </div>
                            </div>

                            <div className="pt-8 border-t border-slate-100">
                                <h3 className="text-2xl font-bold text-slate-900 mb-4">Media Kit</h3>
                                <p className="text-slate-600 mb-6">
                                    ¿Escribes sobre nosotros o quieres promocionar la marca UNPO?
                                    Descarga nuestro logo en alta resolución y fotos oficiales.
                                </p>
                                <a
                                    href="/Media_Kit_UNPO.jpg"
                                    download="Logo_UNPO.jpg"
                                    className="flex items-center justify-center gap-3 w-full px-6 py-4 border-2 border-slate-200 text-slate-700 rounded-xl font-medium hover:bg-slate-50 hover:border-slate-300 transition-all"
                                >
                                    <Download className="w-5 h-5" />
                                    <span>Descargar Logo de Prensa (JPG)</span>
                                </a>
                                <p className="text-xs text-center text-slate-400 mt-4">
                                    Logos vectoriales (AI, EPS, SGV), PNGs transparentes y paleta de colores oficial.
                                </p>
                            </div>

                        </div>
                    </div>
                </div>
            </section>

            <Footer />
        </main>
    );
}
