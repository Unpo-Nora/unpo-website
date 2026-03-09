import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';

export default function TerminosPage() {
    return (
        <main className="min-h-screen bg-white">
            <Navbar />
            <section className="pt-32 pb-24 max-w-4xl mx-auto px-6">
                <div className="mb-12">
                    <h1 className="text-4xl font-bold text-slate-900 mb-4">Términos y Condiciones</h1>
                    <p className="text-slate-500">Última actualización: Marzo 2026</p>
                </div>

                <div className="prose prose-slate max-w-none prose-headings:text-slate-900 prose-a:text-blue-600">
                    <h2>1. Condiciones Generales</h2>
                    <p>
                        Bienvenido al portal de compras mayoristas de UNPO S.A. ("nosotros", "nuestro").
                        El presente documento establece los términos y condiciones por los cuales se rige el uso de
                        nuestra plataforma y el vínculo comercial con nuestros clientes (distribuidores, revendedores,
                        comercios, "usted"). Al utilizar este sitio o realizar un pedido, usted acepta estos Términos.
                    </p>

                    <h2>2. Naturaleza del Servicio (B2B)</h2>
                    <p>
                        UNPO se dedica a la venta mayorista. El acceso a los precios, catálogo completo y compras a través
                        de la plataforma está orientado exclusivamente a clientes comerciales que adquieran
                        productos para revender o como insumo para sus operaciones comerciales, y no para consumidor final.
                    </p>

                    <h2>3. Apertura de Cuenta y Verificación</h2>
                    <p>
                        Para operar, se requiere la apertura de una cuenta cliente ("Cuenta Mayorista"). UNPO se reserva el
                        derecho de solicitar documentación fiscal (Inscripción en AFIP, Ingresos Brutos) para validar su
                        identidad comercial. Nos reservamos el derecho de rechazar cualquier solicitud de apertura de cuenta.
                    </p>

                    <h2>4. Precios y Condiciones de Pago</h2>
                    <ul>
                        <li>
                            Los precios en la plataforma pueden estar expresados en Pesos Argentinos (ARS) o Dólares Estadounidenses (USD),
                            lo cual estará debidamente aclarado. Los precios en USD se pesificarán al tipo de cambio acordado
                            al momento de la emisión de la factura/remito.
                        </li>
                        <li>Los precios mostrados <strong>NO incluyen IVA</strong>, salvo que se indique expresamente lo contrario.</li>
                        <li>Las formas y plazos de pago (transferencia, e-cheq, financiación) dependerán de la calificación crediticia de cada cliente.</li>
                    </ul>

                    <h2>5. Política de Envíos y Logística</h2>
                    <p>
                        Realizamos envíos a todo el territorio argentino. Los costos de envío y seguros asociados son a cargo
                        del cliente comprador, salvo que existan promociones o acuerdos específicos. La responsabilidad por pérdida, robo o
                        avería durante el transporte gestionado por terceros recae sobre la empresa transportista.
                    </p>

                    <h2>6. Modificaciones de los Términos</h2>
                    <p>
                        UNPO S.A. se reserva el derecho de modificar estos Términos y Condiciones en cualquier momento.
                        Las alteraciones sustanciales que afecten la relación comercial serán comunicadas oportunamente a los
                        clientes registrados a través de correo electrónico o alertas en la plataforma.
                    </p>
                </div>
            </section>
            <Footer />
        </main>
    );
}
