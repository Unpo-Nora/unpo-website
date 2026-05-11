import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

export const optimizeImageForPdf = async (url: string, maxSize = 600): Promise<string | null> => {
    return new Promise((resolve) => {
        const img = new Image();
        img.crossOrigin = "Anonymous"; // Fundamental para evitar tainted canvas con imágenes externas
        
        img.onload = () => {
            const canvas = document.createElement("canvas");
            let width = img.width;
            let height = img.height;

            if (width > maxSize || height > maxSize) {
                const ratio = Math.min(maxSize / width, maxSize / height);
                width = Math.floor(width * ratio);
                height = Math.floor(height * ratio);
            }

            canvas.width = width;
            canvas.height = height;

            const ctx = canvas.getContext("2d");
            if (!ctx) {
                resolve(null);
                return;
            }
            
            // Fondo blanco para imágenes PNG transparentes
            ctx.fillStyle = "#FFFFFF";
            ctx.fillRect(0, 0, width, height);
            
            ctx.drawImage(img, 0, 0, width, height);
            
            // Comprimir fuertemente (0.7 calidad JPEG)
            resolve(canvas.toDataURL("image/jpeg", 0.7));
        };
        
        img.onerror = () => {
            console.warn("No se pudo cargar la imagen para PDF:", url);
            resolve(null);
        };
        
        img.src = url;
    });
};

export async function generateCatalogPdf(products: any[], exchangeRate: number, onProgress?: (msg: string) => void) {
    const doc = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: "a4",
    });

    const pageWidth = doc.internal.pageSize.getWidth();
    const marginX = 14;

    // Header del Documento
    doc.setFont("helvetica", "bold");
    doc.setFontSize(18);
    doc.setTextColor(0, 143, 104); // Green UNPO
    doc.text("UNPO - CATÁLOGO MAYORISTA", marginX, 20);

    doc.setFontSize(10);
    doc.setTextColor(100, 100, 100);
    doc.text(`Fecha de emisión: ${new Date().toLocaleDateString('es-AR')}`, marginX, 26);
    doc.text("Importadores Directos Bazar - unpo.com.ar", marginX, 31);
    
    doc.setFontSize(12);
    doc.setTextColor(220, 38, 38);
    doc.text("Los precios indicados son SIN IVA", pageWidth - marginX, 26, { align: "right" });

    doc.setDrawColor(200, 200, 200);
    doc.line(marginX, 35, pageWidth - marginX, 35);

    // Order products by Category
    const sortedProducts = [...products].sort((a, b) => {
        const catA = a.category?.name || "";
        const catB = b.category?.name || "";
        return catA.localeCompare(catB);
    });

    const rows: any[][] = [];
    const imgMap: Record<number, string | null> = {};
    
    // BATCH PROCESSING para evitar desborde de memoria (Memory Error)
    const BATCH_SIZE = 15;
    let currentRowIndex = 0;

    for (let i = 0; i < sortedProducts.length; i += BATCH_SIZE) {
        if (onProgress) {
            onProgress(`Procesando lote de imágenes: ${Math.min(i + BATCH_SIZE, sortedProducts.length)} de ${sortedProducts.length}...`);
        }
        
        const batch = sortedProducts.slice(i, i + BATCH_SIZE);
        
        // Optimizar todas las imágenes del lote en paralelo
        await Promise.all(batch.map(async (p) => {
            let imgData: string | null = null;
            if (p.images && p.images.length > 0) {
                let url = p.images[0];
                if (!url.startsWith('http')) {
                    url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${url.startsWith('/') ? '' : '/'}${url}`;
                }
                imgData = await optimizeImageForPdf(url);
            }
            p._pdfImgData = imgData; // Almacenamiento temporal
        }));
        
        // Agregar a las filas de la tabla
        for (const p of batch) {
            let finalPrice = 0;
            if (p.price_usd && p.price_usd > 0) {
                finalPrice = p.price_usd * exchangeRate;
            } else if (p.price_wholesale && p.price_wholesale > 0) {
                finalPrice = p.price_wholesale;
            } else {
                continue; // Saltar productos sin precio definido
            }
            
            imgMap[currentRowIndex] = p._pdfImgData;
            
            rows.push([
                "", // Celda vacía para la imagen
                p.sku || "-",
                p.name || "-",
                p.category?.name || "-",
                `$${finalPrice.toLocaleString('es-AR', { maximumFractionDigits: 0 })}`
            ]);
            
            currentRowIndex++;
        }
    }

    if (onProgress) {
        onProgress("Generando archivo PDF y ensamblando páginas...");
    }

    // Dibujar la Tabla usando autoTable
    autoTable(doc, {
        startY: 40,
        head: [["Imagen", "SKU", "Producto", "Categoría", "Precio (Sin IVA)"]],
        body: rows,
        didDrawCell: (data) => {
            // Dibujar la imagen optimizada dentro de la primera celda
            if (data.section === 'body' && data.column.index === 0) {
                const imgData = imgMap[data.row.index];
                if (imgData) {
                    const margin = 2;
                    const x = data.cell.x + margin;
                    const y = data.cell.y + margin;
                    // El tamaño máximo será el alto de la celda o el ancho de la columna
                    const dim = Math.min(data.cell.height - margin * 2, data.cell.width - margin * 2);
                    
                    // Centrar la imagen en la celda
                    const offsetX = (data.cell.width - dim) / 2;
                    
                    try {
                        doc.addImage(imgData, 'JPEG', data.cell.x + offsetX, y, dim, dim);
                    } catch (e) {
                        console.warn("No se pudo dibujar una imagen en el PDF:", e);
                    }
                }
            }
        },
        styles: {
            fontSize: 8,
            cellPadding: 3,
            valign: 'middle',
            textColor: [40, 40, 40]
        },
        headStyles: {
            fillColor: [15, 23, 42], // Slate-900
            textColor: [255, 255, 255],
            fontStyle: "bold"
        },
        columnStyles: {
            0: { cellWidth: 28, minCellHeight: 28 }, // Espacio para la imagen 
            1: { cellWidth: 20 },
            2: { cellWidth: 70 },
            3: { cellWidth: 35 },
            4: { cellWidth: 35, halign: 'right', fontStyle: 'bold' }
        }
    });

    if (onProgress) {
        onProgress("¡PDF Listo! Iniciando descarga...");
    }

    // Guardar Documento
    doc.save(`Catalogo_UNPO_${new Date().toLocaleDateString('es-AR').replace(/\//g, '-')}.pdf`);
}
