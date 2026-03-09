import Link from 'next/link';

export default function Navbar() {
    return (
        <nav className="sticky top-0 z-50 w-full bg-white/80 backdrop-blur-md border-b border-gray-100">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between items-center h-20">
                    {/* Brand */}
                    <div className="flex-shrink-0">
                        <Link href="/nora" className="flex items-center gap-2">
                            <span className="text-3xl font-serif font-medium tracking-wide text-slate-900">
                                NORA
                            </span>
                        </Link>
                    </div>

                    {/* Navigation */}
                    <div className="hidden md:flex items-center space-x-12">
                        <Link href="/nora/shop" className="text-sm uppercase tracking-widest text-slate-500 hover:text-slate-900 transition-colors">
                            Tienda
                        </Link>
                        <Link href="/nora/collections" className="text-sm uppercase tracking-widest text-slate-500 hover:text-slate-900 transition-colors">
                            Colecciones
                        </Link>
                        <Link href="/nora/about" className="text-sm uppercase tracking-widest text-slate-500 hover:text-slate-900 transition-colors">
                            Nosotros
                        </Link>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center space-x-6 text-slate-400">

                        {/* UNPO Back Link */}
                        <div className="pl-6 border-l border-slate-200">
                            <Link href="/" className="text-xs font-bold tracking-widest text-slate-400 hover:text-slate-900 transition-colors">
                                UNPO
                            </Link>
                        </div>
                    </div>
                </div>
            </div>
        </nav>
    );
}
