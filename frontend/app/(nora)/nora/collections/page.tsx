import Navbar from '../../../../components/nora/Navbar';
import Link from 'next/link';
import Image from 'next/image';

export default function CollectionsNora() {
    return (
        <main className="min-h-screen bg-white">
            <Navbar />

            <section className="pt-32 pb-20 max-w-7xl mx-auto px-6 text-center">
                <span className="text-sm uppercase tracking-[0.2em] font-bold text-slate-400 mb-4 block">Colecciones 2026</span>
                <h1 className="text-5xl md:text-7xl font-serif text-slate-900 mb-8 tracking-tight">
                    Serie Smart Living
                </h1>
                <p className="text-xl text-slate-500 max-w-2xl mx-auto font-light leading-relaxed">
                    Nuestra colección insignia fusiona el minimalismo atemporal con la última tecnología en refrigeración, audio y carga inalámbrica.
                </p>
            </section>

            <section className="max-w-7xl mx-auto px-6 pb-24">
                <div className="grid md:grid-cols-2 gap-8">
                    {/* Collection 1 */}
                    <Link href="/nora/shop" className="group block relative h-[600px] rounded-3xl overflow-hidden bg-slate-100">
                        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent z-10 transition-opacity group-hover:opacity-90 pointer-events-none"></div>
                        <div className="absolute inset-0 flex items-center justify-center group-hover:scale-105 transition-transform duration-700">
                            <Image src="/nora/images/TB135.PNG" alt="Pro Series NORA" fill className="object-contain p-12 pb-32" sizes="(max-width: 768px) 100vw, 50vw" />
                        </div>
                        <div className="absolute bottom-0 left-0 p-12 z-20 w-full">
                            <span className="text-white/70 text-sm uppercase tracking-widest mb-3 block font-semibold">Tecnología Computarizada</span>
                            <h2 className="text-4xl font-serif text-white mb-4">Pro Series</h2>
                            <p className="text-white/90 text-lg font-light max-w-sm">Modelos TB135, TB90 y TB65 equipados con paneles Touch LED, Bluetooth 5.0 y carga inalámbrica 15W.</p>
                            <span className="inline-block mt-6 border-b border-white text-white pb-1 font-medium tracking-wide">Descubrir Modelos</span>
                        </div>
                    </Link>

                    {/* Collection 2 */}
                    <Link href="/nora/shop" className="group block relative h-[600px] rounded-3xl overflow-hidden bg-slate-900">
                        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent z-10 transition-opacity group-hover:opacity-90 pointer-events-none"></div>
                        <div className="absolute inset-0 flex items-center justify-center group-hover:scale-105 transition-transform duration-700">
                            <Image src="/nora/images/coffee_table_fridge_135.PNG" alt="Classic Series NORA" fill className="object-contain p-12 pb-32" sizes="(max-width: 768px) 100vw, 50vw" />
                        </div>
                        <div className="absolute bottom-0 left-0 p-12 z-20 w-full">
                            <span className="text-white/70 text-sm uppercase tracking-widest mb-3 block font-semibold">Pura Funcionalidad</span>
                            <h2 className="text-4xl font-serif text-white mb-4">Classic Series</h2>
                            <p className="text-white/90 text-lg font-light max-w-sm">Nuestras Coffee Table Fridges de 135L y 65L con diseño mecánico, puras, efectivas y elegantes.</p>
                            <span className="inline-block mt-6 border-b border-white text-white pb-1 font-medium tracking-wide">Descubrir Modelos</span>
                        </div>
                    </Link>
                </div>
            </section>
        </main>
    );
}
