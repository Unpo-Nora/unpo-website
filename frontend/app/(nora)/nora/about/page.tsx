import Navbar from '../../../../components/nora/Navbar';
import Image from 'next/image';

export default function AboutNora() {
    return (
        <main className="min-h-screen bg-slate-50">
            <Navbar />

            <section className="pt-32 pb-20 max-w-5xl mx-auto px-6 text-center">
                <h1 className="text-5xl md:text-6xl font-serif text-slate-900 mb-8 tracking-tight">
                    El futuro del living
                </h1>
                <p className="text-xl md:text-2xl text-slate-600 font-light max-w-3xl mx-auto leading-relaxed">
                    NORA es el puente entre el confort absoluto y la innovación estética.
                    Somos curadores de tecnología aplicada al diseño para transformar tu espacio
                    en un ecosistema inteligente, elegante y minimalista.
                </p>
            </section>

            <section className="py-20 bg-white">
                <div className="max-w-7xl mx-auto px-6 grid md:grid-cols-2 gap-16 items-center">
                    <div className="relative aspect-square md:aspect-[4/5] bg-slate-100 rounded-3xl overflow-hidden shadow-2xl">
                        <Image
                            src="/nora/nora_hero.jpg"
                            alt="Estilo NORA"
                            fill
                            className="object-cover"
                        />
                    </div>
                    <div>
                        <h2 className="text-3xl font-serif text-slate-900 mb-6">Sofisticación y Tecnología</h2>
                        <div className="space-y-6 text-lg text-slate-600 font-light leading-relaxed">
                            <p>
                                Diseñamos para quienes buscan exclusividad. Nuestro "Smart Living" elimina
                                la interrupción: no te levantes del sillón para buscar una bebida fría y no
                                busques cables para cargar tu celular.
                            </p>
                            <p>
                                Todo lo que necesitas para tu universo privado está centralizado en un mueble
                                estético, diseñado bajo las premisas del "Quiet Luxury". Elevamos tu living
                                o quincho VIP, aportando estatus y funcionalidad.
                            </p>
                            <p>
                                NORA es el centro de tu universo privado. El lugar donde todo sucede sin
                                que tengas que moverte.
                            </p>
                        </div>
                    </div>
                </div>
            </section>
        </main>
    );
}
