import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

interface OrderItem {
    product_sku: string;
    quantity: number;
    unit_price: number;
    total_price: number;
    product_name: string;
    product_image?: string;
}

interface Totals {
    subtotal: number;
    discountAmount: number;
    ivaAmount: number;
    total: number;
}

interface GenerateBudgetPdfParams {
    client: any;
    items: OrderItem[];
    totals: Totals;
    discountPercent: number;
    hasIva: boolean;
    dateStr: string;
}

const formatCurrency = (value: number) => {
    return `$${value.toLocaleString('es-AR', { maximumFractionDigits: 0 })}`;
};

export function generateBudgetPdf({ client, items, totals, discountPercent, hasIva, dateStr }: GenerateBudgetPdfParams) {
    // Debug for validation (required by user)
    console.log("Productos presupuesto:", items.length, items.map(p => p.product_sku));

    const doc = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: "a4",
    });

    const pageWidth = doc.internal.pageSize.getWidth();
    const marginX = 14;

    // Header
    doc.setFont("helvetica", "bold");
    doc.setFontSize(18);
    doc.text("UNPO", marginX, 18);

    doc.setFontSize(8);
    doc.text("VENTA MAYORISTA", marginX, 23);

    doc.setFontSize(16);
    doc.setTextColor(37, 99, 235); // Blue
    doc.text("PRESUPUESTO", pageWidth - marginX, 18, { align: "right" });

    doc.setTextColor(0, 0, 0);
    doc.setFontSize(8);
    doc.text(`Fecha: ${dateStr}`, pageWidth - marginX, 25, { align: "right" });
    doc.text("Validez: 15 días", pageWidth - marginX, 30, { align: "right" });

    doc.line(marginX, 36, pageWidth - marginX, 36);

    // Client Info
    doc.setFont("helvetica", "bold");
    doc.setFontSize(9);
    doc.text("DATOS DEL CLIENTE", marginX, 45);

    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.text(`Nombre / Razón Social: ${client?.full_name || "Consumidor Final"}`, marginX, 52);
    doc.text(`Teléfono / Contacto: ${client?.phone || "-"}`, 110, 52);

    // Items Table
    const tableBody = items.map(item => [
        item.product_sku || "-",
        item.product_name || "-",
        String(item.quantity || 0),
        formatCurrency(item.unit_price || 0),
        formatCurrency(item.total_price || 0),
    ]);

    autoTable(doc, {
        startY: 65,
        head: [["SKU", "Producto", "Cant.", "Precio Unit.", "Subtotal"]],
        body: tableBody,
        margin: { left: marginX, right: marginX },
        styles: {
            fontSize: 7,
            cellPadding: 2,
            overflow: "linebreak",
        },
        headStyles: {
            fillColor: [255, 255, 255],
            textColor: [15, 23, 42],
            lineColor: [200, 200, 200],
            lineWidth: 0.1,
            fontStyle: "bold",
        },
        columnStyles: {
            0: { cellWidth: 25 },
            1: { cellWidth: 75 },
            2: { cellWidth: 15, halign: "center" },
            3: { cellWidth: 30, halign: "right" },
            4: { cellWidth: 30, halign: "right" },
        },
    });

    const finalY = (doc as any).lastAutoTable.finalY + 10;

    // Validate if totals fit on the current page, otherwise add a new page
    const pageHeight = doc.internal.pageSize.getHeight();
    let y = finalY;
    if (y > pageHeight - 55) {
        doc.addPage();
        y = 20;
    }

    // Totals Section
    doc.setFontSize(9);
    doc.setFont("helvetica", "bold");
    doc.text("Subtotal:", 130, y);
    doc.text(formatCurrency(totals.subtotal), pageWidth - marginX, y, { align: "right" });

    y += 7;

    if (discountPercent > 0) {
        doc.setTextColor(220, 38, 38); // Red
        doc.text(`Descuento (${discountPercent}%):`, 130, y);
        doc.text(`- ${formatCurrency(totals.discountAmount)}`, pageWidth - marginX, y, { align: "right" });
        y += 7;
        doc.setTextColor(0, 0, 0);
    }

    doc.text(hasIva ? "IVA incluido:" : "IVA (No incluido):", 130, y);
    doc.text(formatCurrency(totals.ivaAmount || 0), pageWidth - marginX, y, { align: "right" });

    y += 6;
    doc.line(130, y, pageWidth - marginX, y);
    y += 8;

    doc.setFontSize(13);
    doc.text("TOTAL FINAL", 130, y);
    doc.setTextColor(37, 99, 235); // Blue
    doc.text(formatCurrency(totals.total), pageWidth - marginX, y, { align: "right" });

    y += 18;
    doc.setTextColor(0, 0, 0);
    doc.setFontSize(7);
    doc.setFont("helvetica", "normal");

    // Check if footer fits
    if (y > pageHeight - 25) {
        doc.addPage();
        y = 20;
    }

    // Footer
    doc.text(
        "Este documento es un presupuesto no válido como factura y está sujeto a disponibilidad de stock.",
        pageWidth / 2,
        y,
        { align: "center" }
    );

    doc.text(
        "Los precios pueden variar sin previo aviso una vez superado el tiempo de validez.",
        pageWidth / 2,
        y + 5,
        { align: "center" }
    );

    // Save File
    const clientNameStr = client?.full_name ? client.full_name.replace(/[^a-z0-9]/gi, '_').toLowerCase() : 'cliente';
    const dateFileStr = dateStr.replace(/\//g, '-');
    const fileName = `presupuesto_UNPO_${clientNameStr}_${dateFileStr}.pdf`;
    
    doc.save(fileName);
}
