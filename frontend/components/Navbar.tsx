import Link from 'next/link';
import Image from 'next/image';
import { Users } from 'lucide-react';

export default function Navbar() {
    return (
        <nav className="sticky top-0 z-50 w-full bg-white border-b border-gray-100 shadow-sm">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between items-center h-20">
                    {/* Logo */}
                    <div className="flex-shrink-0 flex items-center">
                        <Link href="/" className="flex items-center gap-2">
                            <div className="relative flex items-center justify-center px-2">
                                {/* CSS-based Logo Construction */}
                                <div className="relative flex items-end">
                                    <span className="text-5xl font-black tracking-tighter text-slate-900 leading-none block -mb-1">
                                        U
                                    </span>
                                    <div className="relative">
                                        <div className="absolute -top-2 left-0 w-full h-[6px] bg-red-600"></div>
                                        <span className="text-4xl font-black tracking-tighter text-slate-900 leading-none block">
                                            NPO
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </Link>
                    </div>

                    {/* Desktop Navigation */}
                    <div className="hidden md:flex items-center space-x-8">
                        <Link href="/catalogo" className="text-slate-600 hover:text-blue-600 font-medium transition-colors">
                            Catálogo
                        </Link>
                        <Link href="/#about" className="text-slate-600 hover:text-blue-600 font-medium transition-colors">
                            Nosotros
                        </Link>
                        <Link href="/#benefits" className="text-slate-600 hover:text-blue-600 font-medium transition-colors">
                            Beneficios
                        </Link>
                    </div>

                    {/* CTA Buttons */}
                    <div className="flex items-center gap-3">
                        <Link href="/admin/login">
                            <button className="flex items-center gap-2 bg-white hover:bg-blue-50 text-blue-600 px-4 py-2 text-sm font-black rounded-xl transition-all border-2 border-blue-600 shadow-lg shadow-blue-100 active:scale-95">
                                <Users size={16} strokeWidth={3} />
                                Acceso Staff
                            </button>
                        </Link>
                        {/* 
                        <button className="bg-slate-900 hover:bg-slate-800 text-white px-5 py-2.5 rounded-lg font-medium transition-all shadow-lg shadow-slate-900/20">
                            Acceso Clientes
                        </button>
                        */}
                    </div>
                </div>
            </div>
        </nav>
    );
}
