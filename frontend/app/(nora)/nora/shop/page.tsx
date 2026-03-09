import Navbar from '../../../../components/nora/Navbar';
import Link from 'next/link';
import Image from 'next/image';

const NORA_PRODUCTS = [
    {
        id: "tb135-pro",
        name: "TB135 Pro",
        subtitle: "135L - Dual Zone",
        features: ["Enfriamiento Computarizado", "Bluetooth 5.0", "Carga Inalámbrica 15W", "Iluminación LED RGB"],
        desc: "Mesa ratona inteligente de doble zona (70L + 65L) con panel táctil.",
        colors: ["Negro"],
        isPro: true,
        image: "/nora/images/TB135.PNG"
    },
    {
        id: "ctf-135",
        name: "Coffee Table Fridge 135",
        subtitle: "135L - Dual Zone Clásica",
        features: ["Control Mecánico", "Doble Enchufe (2x Socket)", "Orificio para toma de agua"],
        desc: "Capacidad de 135L distribuidos en dos zonas. Enfoque clásico y puramente funcional.",
        colors: ["Negro"],
        isPro: false,
        image: "/nora/images/coffee_table_fridge_135.PNG"
    },
    {
        id: "tb90-max",
        name: "TB90 Max",
        subtitle: "Heladera + Freezer Profundo",
        features: ["Freezer (-12°C a -24°C)", "Bluetooth 5.0", "Carga Inalámbrica 15W", "Iluminación LED"],
        desc: "La solución total de 93L. Combina refrigerador de bebidas y freezer profundo en un diseño sofisticado.",
        colors: ["Negro"],
        isPro: true,
        image: "/nora/images/TB90.PNG"
    },
    {
        id: "tb65-max",
        name: "TB65 Max",
        subtitle: "65L - Compact & Smart",
        features: ["Enfriamiento Computarizado", "Bluetooth 5.0", "Carga Inalámbrica 15W", "Night Light & LED RGB"],
        desc: "Formato compacto ideal para espacios minimalistas, sin sacrificar inteligencia tecnológica.",
        colors: ["Blanco"],
        isPro: true,
        image: "/nora/images/TB65.PNG"
    }
];

export default function ShopNora() {
    return (
        <main className="min-h-screen bg-slate-50">
            <Navbar />

            <section className="pt-24 pb-12 max-w-7xl mx-auto px-6">
                <div className="flex justify-between items-end mb-12">
                    <div>
                        <h1 className="text-4xl font-serif text-slate-900 mb-2">Catálogo NORA</h1>
                        <p className="text-slate-500">Exclusividad en Smart Furniture</p>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                    {NORA_PRODUCTS.map((prod) => (
                        <div key={prod.id} className="bg-white rounded-3xl p-6 shadow-sm hover:shadow-xl transition-all border border-slate-100 group flex flex-col">
                            {/* Product Image */}
                            <div className="relative w-full aspect-square bg-white rounded-2xl mb-6 flex items-center justify-center overflow-hidden">
                                <Image
                                    src={prod.image}
                                    alt={prod.name}
                                    fill
                                    className="object-contain p-4 group-hover:scale-105 transition-transform duration-500"
                                    sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                                />
                                {prod.isPro && (
                                    <div className="absolute top-4 right-4 bg-slate-900 text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider z-10">
                                        Pro Series
                                    </div>
                                )}
                            </div>

                            <div className="flex-1">
                                <h3 className="text-2xl font-serif text-slate-900 mb-1">{prod.name}</h3>
                                <p className="text-sm font-medium text-slate-500 uppercase tracking-wider mb-4">{prod.subtitle}</p>

                                <ul className="space-y-2 mb-6 text-sm text-slate-600">
                                    {prod.features.slice(0, 3).map((f, i) => (
                                        <li key={i} className="flex items-center gap-2">
                                            <span className="w-1.5 h-1.5 bg-slate-900 rounded-full shrink-0"></span>
                                            <span className="truncate">{f}</span>
                                        </li>
                                    ))}
                                </ul>

                                <p className="text-sm text-slate-400 font-light mb-6 line-clamp-2">
                                    {prod.desc}
                                </p>
                            </div>

                            <div className="pt-6 border-t border-slate-100 mt-auto">
                                <Link href="/nora#waitlist" className="flex items-center justify-center w-full px-6 py-3 bg-slate-900 text-white rounded-xl text-sm font-bold tracking-widest uppercase hover:bg-slate-800 transition-colors shadow-md">
                                    Consultar por Modelo
                                </Link>
                            </div>
                        </div>
                    ))}
                </div>
            </section>
        </main>
    );
}
