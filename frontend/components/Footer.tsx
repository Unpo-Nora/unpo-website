export default function Footer() {
    return (
        <footer className="bg-slate-900 text-slate-400 py-12">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="grid md:grid-cols-4 gap-8 mb-8">
                    <div className="col-span-1 md:col-span-2">
                        <span className="text-2xl font-bold text-white tracking-tight">UNPO</span>
                        <p className="mt-4 max-w-xs text-sm">
                            Partner tecnológico líder en distribución mayorista. Conectamos innovación con retail.
                        </p>
                    </div>

                    <div>
                        <h4 className="text-white font-semibold mb-4">Empresa</h4>
                        <ul className="space-y-2 text-sm">
                            <li><a href="#" className="hover:text-blue-400">Sobre Nosotros</a></li>
                            <li><a href="/prensa" className="hover:text-blue-400">Prensa</a></li>
                        </ul>
                    </div>

                    <div>
                        <h4 className="text-white font-semibold mb-4">Legal</h4>
                        <ul className="space-y-2 text-sm">
                            <li><a href="/terminos" className="hover:text-blue-400">Términos y Condiciones</a></li>
                            <li><a href="/privacidad" className="hover:text-blue-400">Política de Privacidad</a></li>
                            <li><a href="/garantias" className="hover:text-blue-400">Garantías</a></li>
                        </ul>
                    </div>
                </div>

                <div className="border-t border-slate-800 pt-8 flex flex-col md:flex-row justify-between items-center text-sm">
                    <p>&copy; {new Date().getFullYear()} UNPO S.A. Todos los derechos reservados.</p>
                    <div className="flex gap-4 mt-4 md:mt-0">
                        {/* Social Icons Placeholder */}
                        <div className="w-5 h-5 bg-slate-800 rounded-full"></div>
                        <div className="w-5 h-5 bg-slate-800 rounded-full"></div>
                        <div className="w-5 h-5 bg-slate-800 rounded-full"></div>
                    </div>
                </div>
            </div>
        </footer>
    );
}
