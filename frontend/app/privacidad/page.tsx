import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';

export default function PrivacidadPage() {
    return (
        <main className="min-h-screen bg-white">
            <Navbar />
            <section className="pt-32 pb-24 max-w-4xl mx-auto px-6">
                <div className="mb-12">
                    <h1 className="text-4xl font-bold text-slate-900 mb-4">Política de Privacidad</h1>
                    <p className="text-slate-500">Última actualización: Marzo 2026</p>
                </div>

                <div className="prose prose-slate max-w-none prose-headings:text-slate-900 prose-a:text-blue-600">
                    <h2>1. Información Recopilada</h2>
                    <p>
                        UNPO S.A. recopila la información proporcionada voluntariamente mediante nuestros formularios de alta
                        de cliente, contacto, compras y navegación por el sitio. Esto incluye, entre otros: Razón Social, CUIT/CUIL,
                        Domicilio Fiscal, Teléfonos, Correos Electrónicos, datos bancarios (para cobros/transferencias) y datos de navegación
                        (cookies).
                    </p>

                    <h2>2. Uso de la Información Comercial</h2>
                    <p>
                        La información se utiliza exclusivamente para:
                    </p>
                    <ul>
                        <li>Validar la identidad de los comercios y empresas solicitantes.</li>
                        <li>Gestión administrativa, facturación y cobro de pedidos.</li>
                        <li>Coordinación de logística y entregas.</li>
                        <li>Comunicaciones comerciales, envío de catálogos actualizados, promociones de productos y novedades (Newsletter B2B).</li>
                        <li>Mejorar la experiencia de usuario dentro de nuestro E-commerce.</li>
                    </ul>

                    <h2>3. Protección y Confidencialidad</h2>
                    <p>
                        UNPO S.A. se compromete a tratar sus datos de carácter comercial y personal con la máxima confidencialidad.
                        No comercializamos, alquilamos ni cedemos bases de datos a terceros, salvo a las empresas de logística estrictamente
                        necesarias para el cumplimiento de las entregas de mercadería adquirida, o por orden judicial competente.
                    </p>

                    <h2>4. Derechos de Acceso, Rectificación y Supresión</h2>
                    <p>
                        Cualquier empresa o persona física titular de los datos puede ejercer los derechos de Acceso, Rectificación, Actualización y Supresión
                        de su información registrados en nuestras bases, conforme a la Ley de Protección de Datos Personales N° 25.326 de la República Argentina.
                        Para ello, póngase en contacto a través de nuestros canales oficiales o respondiendo a nuestros correos electrónicos.
                    </p>
                </div>
            </section>
            <Footer />
        </main>
    );
}
