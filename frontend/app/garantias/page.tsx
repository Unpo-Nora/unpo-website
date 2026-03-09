import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';

export default function GarantiasPage() {
    return (
        <main className="min-h-screen bg-white">
            <Navbar />
            <section className="pt-32 pb-24 max-w-4xl mx-auto px-6">
                <div className="mb-12">
                    <h1 className="text-4xl font-bold text-slate-900 mb-4">Políticas de Garantía</h1>
                    <p className="text-slate-500">Última actualización: Marzo 2026</p>
                </div>

                <div className="prose prose-slate max-w-none prose-headings:text-slate-900 prose-a:text-blue-600">
                    <h2>1. Período de Garantía B2B</h2>
                    <p>
                        UNPO S.A. otorga una garantía estándar de <strong>3 (tres) a 6 (seis) meses</strong> a partir de la
                        fecha de facturación sobre defectos de fabricación en productos de electrónica y hogar, salvo que la ficha
                        técnica o empaque del producto específico establezca un plazo distinto. Esta garantía está orientada a la protección
                        del cliente mayorista.
                    </p>

                    <h2>2. Condiciones para Validar la Garantía</h2>
                    <p>
                        Para procesar un reclamo por producto defectuoso (RMA), el distribuidor deberá presentar:
                    </p>
                    <ul>
                        <li>Número de Remito o Factura original de compra.</li>
                        <li>El producto en su empaque original, con todos sus accesorios, manuales, plásticos y etiquetas.</li>
                        <li>Una descripción clara del fallo reportado o, en su defecto, el reporte que le entregó el consumidor final.</li>
                    </ul>

                    <h2>3. Exclusiones de la Garantía</h2>
                    <p>La garantía quedará automáticamente anulada si el producto presenta, entre otros:</p>
                    <ul>
                        <li>Daños físicos (roturas, abolladuras, rayas profundas), signos de contacto con líquidos no aptos o quemaduras.</li>
                        <li>Uso inadecuado, desgaste natural por uso (baterías agotadas, desgaste estético) o instalación eléctrica deficiente.</li>
                        <li>Modificaciones, desarmado, o intentos de reparación por personal no autorizado por UNPO.</li>
                        <li>Etiquetas de seguridad violadas, números de serie alterados o ilegibles.</li>
                    </ul>

                    <h2>4. Proceso de Cambio y/o NC</h2>
                    <p>
                        Una vez recibido el producto en <strong>nuestros depósitos centrales</strong> (con flete a cargo del cliente remitente), el
                        departamento técnico de UNPO evaluará la falla informada en un plazo no mayor a 10 (diez) días hábiles.
                    </p>
                    <p>
                        De confirmarse el defecto de fabricación, el producto se reparará, se cambiará por unidad nueva idéntica, o se emitirá una
                        <strong>Nota de Crédito (NC)</strong> a favor del distribuidor por el valor de compra original, la cual podrá ser imputada
                        a futuras compras. En caso de no confirmarse la falla técnica informada o estar fuera de los términos de garantía, el
                        producto se retornará al cliente (con flete a abonar en destino).
                    </p>

                    <h2>Refurbished o Segundas Opciones (NORA)</h2>
                    <p>
                        Los productos etiquetados o liquidados bajo categorías de segunda selección, open box o outlet
                        no cuentan con la misma garantía extendida general y podrían estar sujetos a términos de garantía reducidos
                        (típicamente 30 días) que se comunicarán explícitamente en la lista de precios y la factura.
                    </p>
                </div>
            </section>
            <Footer />
        </main>
    );
}
