import Image from 'next/image';

export default function ProductShowcase() {
    return (
        <section className="bg-slate-50 py-24">

            {/* Introduction */}
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-32">
                <div className="text-center max-w-3xl mx-auto">
                    <h2 className="text-4xl md:text-5xl font-serif text-slate-900 mb-6">El Centro de tu Living</h2>
                    <p className="text-lg text-slate-600 font-light leading-relaxed">
                        Olvidate del desorden y los cables.
                        La Mesa Inteligente NORA integra refrigeración, carga y audio de alta fidelidad
                        en una pieza de mobiliario que estarás orgulloso de exhibir.
                    </p>
                </div>
            </div>

            {/* Feature 1: Refrigerated Drawers */}
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-32">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-16 items-center">
                    <div className="relative h-[500px] w-full bg-white rounded-2xl overflow-hidden shadow-2xl">
                        <Image
                            src="/nora/smart_table_2.png" // Using existing image
                            alt="Cajones Refrigerados"
                            fill
                            className="object-cover"
                        />
                    </div>
                    <div>
                        <span className="text-indigo-600 font-bold tracking-widest uppercase text-xs mb-4 block">Refrigeración Inteligente</span>
                        <h3 className="text-3xl md:text-4xl font-serif text-slate-900 mb-6">Siempre Fresco. Para Bebidas y Cosméticos.</h3>
                        <p className="text-slate-600 mb-8 font-light leading-relaxed">
                            Cajones refrigerados dobles mantienen tus bebidas, snacks o productos de cuidado personal
                            a la temperatura perfecta. Ajustable de 3°C a 12°C mediante el panel táctil.
                        </p>
                        <ul className="space-y-4">
                            <li className="flex items-center text-slate-700">
                                <span className="w-2 h-2 bg-indigo-500 rounded-full mr-3"></span>
                                Control de Temperatura Independiente
                            </li>
                            <li className="flex items-center text-slate-700">
                                <span className="w-2 h-2 bg-indigo-500 rounded-full mr-3"></span>
                                Tecnología de Compresor Silencioso
                            </li>
                            <li className="flex items-center text-slate-700">
                                <span className="w-2 h-2 bg-indigo-500 rounded-full mr-3"></span>
                                Capacidad Total 130L
                            </li>
                        </ul>
                    </div>
                </div>
            </div>

            {/* Feature 2: Audio & Charging */}
            <div className="bg-white py-24 mb-32">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-16 items-center md:flex-row-reverse">
                        <div className="order-2 md:order-1">
                            <span className="text-indigo-600 font-bold tracking-widest uppercase text-xs mb-4 block">Conectividad</span>
                            <h3 className="text-3xl md:text-4xl font-serif text-slate-900 mb-6">Sonido Inmersivo. Energía sin Esfuerzo.</h3>
                            <p className="text-slate-600 mb-8 font-light leading-relaxed">
                                Parlantes duales Bluetooth 5.0 ofrecen un sonido rico y envolvente.
                                Mientras tanto, la superficie de vidrio templado cuenta con carga inalámbrica dual
                                para mantener tus dispositivos con energía sin cables a la vista.
                            </p>
                            <ul className="space-y-4">
                                <li className="flex items-center text-slate-700">
                                    <span className="w-2 h-2 bg-indigo-500 rounded-full mr-3"></span>
                                    Parlantes Duales 20W
                                </li>
                                <li className="flex items-center text-slate-700">
                                    <span className="w-2 h-2 bg-indigo-500 rounded-full mr-3"></span>
                                    Carga Inalámbrica 15W (x2)
                                </li>
                                <li className="flex items-center text-slate-700">
                                    <span className="w-2 h-2 bg-indigo-500 rounded-full mr-3"></span>
                                    Puertos USB-C y USB-A
                                </li>
                            </ul>
                        </div>
                        <div className="order-1 md:order-2 relative h-[500px] w-full bg-slate-100 rounded-2xl overflow-hidden shadow-2xl">
                            <Image
                                src="/nora/smart_table_sound_v2.png"
                                alt="Funciones de Conectividad"
                                fill
                                className="object-cover"
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* Specs Grid */}
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <h2 className="text-3xl font-serif text-slate-900 mb-12 text-center">Especificaciones Técnicas</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
                    <div className="p-6 border border-slate-200 rounded-xl text-center hover:border-indigo-500 transition-colors cursor-default">
                        <div className="text-slate-400 text-xs uppercase tracking-widest mb-2">Dimensiones</div>
                        <div className="text-slate-900 font-medium">130 x 70 x 46 cm</div>
                    </div>
                    <div className="p-6 border border-slate-200 rounded-xl text-center hover:border-indigo-500 transition-colors cursor-default">
                        <div className="text-slate-400 text-xs uppercase tracking-widest mb-2">Refrigeración</div>
                        <div className="text-slate-900 font-medium">130 Litros</div>
                    </div>
                    <div className="p-6 border border-slate-200 rounded-xl text-center hover:border-indigo-500 transition-colors cursor-default">
                        <div className="text-slate-400 text-xs uppercase tracking-widest mb-2">Potencia Audio</div>
                        <div className="text-slate-900 font-medium">40W (20W x 2)</div>
                    </div>
                    <div className="p-6 border border-slate-200 rounded-xl text-center hover:border-indigo-500 transition-colors cursor-default">
                        <div className="text-slate-400 text-xs uppercase tracking-widest mb-2">Control</div>
                        <div className="text-slate-900 font-medium">Panel Táctil</div>
                    </div>
                </div>
            </div>
        </section>
    );
}
