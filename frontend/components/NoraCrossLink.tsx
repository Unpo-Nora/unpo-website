import Link from 'next/link';
import Image from 'next/image';

export default function NoraCrossLink() {
    return (
        <section className="bg-slate-800 text-white py-24 overflow-hidden relative">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 flex flex-col md:flex-row items-center gap-16">

                {/* Text Content */}
                <div className="flex-1 text-center md:text-left">
                    <span className="inline-block py-1 px-3 rounded-full bg-indigo-500/20 text-indigo-300 text-xs font-semibold tracking-widest uppercase mb-4">
                        New Division
                    </span>
                    <h2 className="text-4xl md:text-5xl font-serif font-medium mb-4 tracking-wide">
                        NORA <span className="text-slate-500 font-light">—</span> Smart Living
                    </h2>
                    <p className="text-xl text-slate-300 mb-2 font-light">
                        Nuestra división de Smart Furniture para consumidor final.
                    </p>
                    <p className="text-base text-slate-400 mb-10 max-w-lg mx-auto md:mx-0 leading-relaxed">
                        Una línea exclusiva donde diseño, lujo y tecnología se fusionan para redefinir los espacios modernos.
                    </p>

                    <Link href="/nora" className="inline-flex items-center justify-center px-8 py-4 text-sm font-bold tracking-widest uppercase text-slate-900 bg-white hover:bg-slate-200 transition-colors">
                        Descubrí NORA
                    </Link>
                </div>

                {/* Visual Content - Smart Table Placeholder */}
                <div className="flex-1 w-full relative h-[400px] md:h-[500px]">
                    <div className="absolute inset-0 bg-gradient-to-tr from-slate-900/50 to-transparent z-10"></div>
                    {/* Using user-provided Smart Table image */}
                    <Image
                        src="/nora/smart_table_white.jpg"
                        alt="Nora Smart Furniture"
                        fill
                        className="object-cover rounded-sm hover:scale-105 transition-all duration-700 ease-in-out"
                    />
                </div>
            </div>

            {/* Background elements for minimalist feel */}
            <div className="absolute top-0 right-0 -mt-20 -mr-20 w-96 h-96 bg-indigo-900/10 rounded-full blur-3xl"></div>
            <div className="absolute bottom-0 left-0 -mb-20 -ml-20 w-96 h-96 bg-slate-800/20 rounded-full blur-3xl"></div>
        </section>
    );
}
