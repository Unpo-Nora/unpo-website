import Link from 'next/link';
import Image from 'next/image';

export default function Hero() {
    return (
        <section id="about" className="relative bg-slate-900 overflow-hidden min-h-[600px] flex items-center">
            {/* Background Image with Overlay */}
            <div className="absolute inset-0 z-0">
                <Image
                    src="https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?q=80&w=2070&auto=format&fit=crop"
                    alt="Centro de distribución moderno con estanterías altas"
                    fill
                    className="object-cover"
                    priority
                />
                <div className="absolute inset-0 bg-slate-900/85 mix-blend-multiply" />
            </div>

            <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-32">
                <div className="max-w-4xl mx-auto text-center">
                    <h1 className="text-5xl md:text-6xl font-extrabold text-white tracking-tight mb-8 leading-tight drop-shadow-sm">
                        Distribución Mayorista de <br />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-400">
                            Tecnología Premium
                        </span>
                    </h1>

                    <p className="mt-4 text-xl text-slate-200 max-w-2xl mx-auto mb-10 leading-relaxed drop-shadow-sm">
                        Abastecemos a los principales retailers y revendedores del país.
                        Garantía oficial, stock permanente y logística consolidada para tu negocio.
                    </p>

                    <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
                        <Link
                            href="#contact"
                            className="w-full sm:w-auto px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white text-lg font-semibold rounded-xl shadow-lg shadow-blue-600/30 transition-all transform hover:-translate-y-1 hover:shadow-blue-600/40"
                        >
                            Quiero ser cliente
                        </Link>
                        <Link
                            href="/catalogo"
                            className="w-full sm:w-auto px-8 py-4 bg-transparent text-white border-2 border-white/30 hover:border-white hover:bg-white/10 text-lg font-semibold rounded-xl transition-all backdrop-blur-sm"
                        >
                            Ver Catálogo
                        </Link>
                    </div>

                    <div className="mt-12 flex items-center justify-center gap-8 text-sm text-slate-300 font-medium">
                        <div className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-green-400 shadow-[0_0_10px_rgba(74,222,128,0.5)]"></span>
                            Stock en tiempo real
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_10px_rgba(96,165,250,0.5)]"></span>
                            Envíos a todo el país
                        </div>
                    </div>
                </div>
            </div>

            {/* Decorative elements - adjust opacity for dark background */}
            <div className="absolute -top-24 -right-24 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl" />
            <div className="absolute top-48 -left-24 w-72 h-72 bg-indigo-500/20 rounded-full blur-3xl" />
        </section>
    );
}
