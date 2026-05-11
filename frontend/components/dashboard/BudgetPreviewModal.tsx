import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom';
import { X, Printer, Download } from 'lucide-react';
import { generateBudgetPdf } from '../../utils/generateBudgetPdf';

interface OrderItem {
    product_sku: string;
    quantity: number;
    unit_price: number;
    total_price: number;
    product_name: string;
    product_image?: string;
}

interface BudgetPreviewModalProps {
    cart: OrderItem[];
    lead: any;
    discountPercent: number;
    hasIva: boolean;
    rawTotalAmount: number;
    discountedAmount: number;
    ivaAmount: number;
    finalTotalAmount: number;
    onClose: () => void;
}

const PresupuestoPrintDocument = ({
    cart, lead, discountPercent, hasIva, rawTotalAmount, discountedAmount, ivaAmount, finalTotalAmount, today
}: any) => {
    return (
        <div className="presupuesto-print-document bg-white text-black">
            {/* Header Document */}
            <div className="flex justify-between items-start border-b-2 border-black pb-6 mb-8">
                <div>
                    <h1 className="text-4xl font-black tracking-tighter text-black mb-1">UNPO</h1>
                    <p className="text-sm font-bold text-gray-600 uppercase tracking-widest">Venta Mayorista</p>
                </div>
                <div className="text-right">
                    <h2 className="text-2xl font-black text-black uppercase tracking-wider mb-2">Presupuesto</h2>
                    <p className="text-sm text-gray-800 font-medium">Fecha: <strong>{today}</strong></p>
                    <p className="text-sm text-gray-800 font-medium mt-1">Validez: <strong>15 días</strong></p>
                </div>
            </div>

            {/* Client Info */}
            <div className="presupuesto-client-data bg-gray-50 rounded-xl p-4 mb-8 border border-gray-200">
                <h3 className="text-xs font-black text-gray-500 uppercase tracking-widest mb-3">Datos del Cliente</h3>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <p className="text-sm text-gray-600 mb-1">Nombre / Razón Social:</p>
                        <p className="font-bold text-black">{lead?.full_name || "Consumidor Final"}</p>
                    </div>
                    <div>
                        <p className="text-sm text-gray-600 mb-1">Teléfono / Contacto:</p>
                        <p className="font-bold text-black">{lead?.phone || "-"}</p>
                    </div>
                </div>
            </div>

            {/* Items Table */}
            <div className="mb-8">
                <table className="presupuesto-table text-left text-sm w-full">
                    <thead>
                        <tr className="border-b-2 border-gray-300">
                            <th className="py-3 px-2 font-black text-black uppercase tracking-wider">SKU</th>
                            <th className="py-3 px-2 font-black text-black uppercase tracking-wider">Producto</th>
                            <th className="py-3 px-2 font-black text-black uppercase tracking-wider text-center">Cant.</th>
                            <th className="py-3 px-2 font-black text-black uppercase tracking-wider text-right">Precio Unit.</th>
                            <th className="py-3 px-2 font-black text-black uppercase tracking-wider text-right">Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {cart.map((item: any, index: number) => (
                            <tr key={`${item.product_sku}-${index}`} className="border-b border-gray-200">
                                <td className="py-3 px-2 text-gray-600 font-medium">{item.product_sku || "-"}</td>
                                <td className="py-3 px-2 font-bold text-black">{item.product_name}</td>
                                <td className="py-3 px-2 text-center font-bold text-black">{item.quantity}</td>
                                <td className="py-3 px-2 text-right font-medium text-gray-800">
                                    ${item.unit_price.toLocaleString('es-AR', { maximumFractionDigits: 0 })}
                                </td>
                                <td className="py-3 px-2 text-right font-black text-black">
                                    ${item.total_price.toLocaleString('es-AR', { maximumFractionDigits: 0 })}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Totals Section */}
            <div className="presupuesto-totals flex justify-end mt-8">
                <div className="w-full max-w-sm space-y-3">
                    <div className="flex justify-between text-sm">
                        <span className="font-bold text-gray-600">Subtotal:</span>
                        <span className="font-bold text-black">
                            ${rawTotalAmount.toLocaleString('es-AR', { maximumFractionDigits: 0 })}
                        </span>
                    </div>

                    {discountPercent > 0 && (
                        <div className="flex justify-between text-sm">
                            <span className="font-bold text-black">Descuento ({discountPercent}%):</span>
                            <span className="font-bold text-black">
                                - ${(rawTotalAmount - discountedAmount).toLocaleString('es-AR', { maximumFractionDigits: 0 })}
                            </span>
                        </div>
                    )}

                    <div className="flex justify-between text-sm">
                        <span className="font-bold text-gray-600">IVA ({hasIva ? '21%' : 'No incluido'}):</span>
                        <span className="font-bold text-black">
                            {hasIva 
                                ? `+ $${ivaAmount.toLocaleString('es-AR', { maximumFractionDigits: 0 })}` 
                                : "$0"
                            }
                        </span>
                    </div>

                    <div className="border-t-2 border-black pt-3 mt-3 flex justify-between items-center">
                        <span className="text-lg font-black uppercase tracking-widest text-black">Total Final</span>
                        <span className="text-2xl font-black text-black">
                            ${finalTotalAmount.toLocaleString('es-AR', { maximumFractionDigits: 0 })}
                        </span>
                    </div>
                </div>
            </div>

            {/* Footer Notes */}
            <div className="presupuesto-footer mt-12 pt-6 border-t border-gray-200 text-center text-xs text-gray-500 font-medium">
                <p>Este documento es un presupuesto no válido como factura y está sujeto a disponibilidad de stock.</p>
                <p className="mt-1">Los precios pueden variar sin previo aviso una vez superado el tiempo de validez.</p>
            </div>
        </div>
    );
};

export default function BudgetPreviewModal({
    cart,
    lead,
    discountPercent,
    hasIva,
    rawTotalAmount,
    discountedAmount,
    ivaAmount,
    finalTotalAmount,
    onClose
}: BudgetPreviewModalProps) {
    const [mounted, setMounted] = useState(false);
    
    useEffect(() => {
        setMounted(true);
    }, []);

    const today = new Date().toLocaleDateString('es-AR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });

    const handlePrint = () => {
        window.print();
    };

    const handleDownloadPdf = () => {
        // Utilizamos la utilidad de generación programática en vez del motor de impresión del navegador
        generateBudgetPdf({
            client: lead,
            items: cart,
            discountPercent,
            hasIva,
            dateStr: today,
            totals: {
                subtotal: rawTotalAmount,
                discountAmount: rawTotalAmount - discountedAmount,
                ivaAmount,
                total: finalTotalAmount
            }
        });
    };

    const printRootContent = (
        <div className="presupuesto-print-root">
            <PresupuestoPrintDocument
                cart={cart}
                lead={lead}
                discountPercent={discountPercent}
                hasIva={hasIva}
                rawTotalAmount={rawTotalAmount}
                discountedAmount={discountedAmount}
                ivaAmount={ivaAmount}
                finalTotalAmount={finalTotalAmount}
                today={today}
            />
        </div>
    );

    return (
        <>
            <style>{`
                @media screen {
                    .presupuesto-print-root {
                        display: none !important;
                    }
                }

                @media print {
                    @page {
                        size: A4 portrait;
                        margin: 10mm;
                    }

                    html, body {
                        width: 100% !important;
                        height: 100% !important;
                        margin: 0 !important;
                        padding: 0 !important;
                        overflow: visible !important;
                        background: white !important;
                    }

                    /* Apagar por completo toda la app y su flujo para evitar hojas fantasma */
                    #__next,
                    .presupuesto-preview-modal,
                    .modal-backdrop,
                    #root,
                    .admin-layout {
                        display: none !important;
                        height: 0 !important;
                        width: 0 !important;
                        overflow: hidden !important;
                        margin: 0 !important;
                        padding: 0 !important;
                        border: none !important;
                        position: absolute !important;
                    }

                    body * {
                        visibility: hidden;
                    }

                    .presupuesto-print-root,
                    .presupuesto-print-root * {
                        visibility: visible !important;
                    }

                    .presupuesto-print-root {
                        display: block !important;
                        position: relative !important;
                        width: 100% !important;
                        height: auto !important;
                        overflow: visible !important;
                        background: white !important;
                        margin: 0 !important;
                        padding: 0 !important;
                    }

                    .presupuesto-print-document {
                        width: 100% !important;
                        max-width: 100% !important;
                        min-height: 0 !important;
                        height: auto !important;
                        margin: 0 !important;
                        padding: 0 !important;
                        box-shadow: none !important;
                        border: none !important;
                        overflow: visible !important;
                        transform: none !important;
                        page-break-after: auto;
                    }

                    .presupuesto-table {
                        width: 100%;
                        border-collapse: collapse;
                        page-break-inside: auto;
                    }

                    .presupuesto-table thead {
                        display: table-header-group;
                    }

                    .presupuesto-table tbody {
                        display: table-row-group;
                    }

                    .presupuesto-table tr {
                        page-break-inside: avoid;
                        break-inside: avoid;
                    }

                    .presupuesto-totals,
                    .presupuesto-client-data,
                    .presupuesto-footer {
                        page-break-inside: avoid;
                        break-inside: avoid;
                    }
                }
            `}</style>

            {/* Modal de Previsualización en Pantalla */}
            <div className="presupuesto-preview-modal fixed inset-0 z-[200] flex items-center justify-center p-4 sm:p-8 bg-slate-900/80 backdrop-blur-sm">
                <div className="relative bg-white w-full max-w-4xl max-h-[90vh] sm:rounded-2xl shadow-2xl flex flex-col overflow-hidden">
                    
                    {/* Header Actions */}
                    <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50 shrink-0">
                        <div>
                            <h3 className="text-xl font-black text-slate-900">Previsualización de Presupuesto</h3>
                            <p className="text-sm text-slate-500">Puedes imprimirlo o guardarlo como PDF.</p>
                        </div>
                        <div className="flex items-center gap-3">
                            <button 
                                onClick={handleDownloadPdf}
                                className="flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-700 hover:bg-blue-100 font-bold rounded-xl transition-colors"
                            >
                                <Download size={18} /> PDF
                            </button>
                            <button 
                                onClick={handlePrint}
                                className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white hover:bg-slate-800 font-bold rounded-xl transition-colors"
                            >
                                <Printer size={18} /> Imprimir
                            </button>
                            <div className="w-px h-6 bg-slate-200 mx-2"></div>
                            <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full transition-colors text-slate-400">
                                <X size={24} />
                            </button>
                        </div>
                    </div>

                    {/* Preview Scrollable Area */}
                    <div className="flex-1 overflow-y-auto p-4 sm:p-8 bg-slate-100 custom-scrollbar">
                        <div className="bg-white w-full max-w-3xl mx-auto p-8 shadow-sm rounded-xl border border-slate-200">
                            {/* Reutilizamos el mismo componente visual para la pantalla */}
                            <PresupuestoPrintDocument
                                cart={cart}
                                lead={lead}
                                discountPercent={discountPercent}
                                hasIva={hasIva}
                                rawTotalAmount={rawTotalAmount}
                                discountedAmount={discountedAmount}
                                ivaAmount={ivaAmount}
                                finalTotalAmount={finalTotalAmount}
                                today={today}
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* Documento Exclusivo para Impresión adjunto directamente al body para evadir jerarquía DOM */}
            {mounted && ReactDOM.createPortal(printRootContent, document.body)}
        </>
    );
}
