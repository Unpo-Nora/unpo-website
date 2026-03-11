import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from PIL import Image as PILImage
from reportlab.lib.utils import ImageReader
from .. import models

def generate_remito_pdf(order: models.SaleOrder) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    elements = []
    
    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]
    bold_style = ParagraphStyle(name='Bold', parent=styles['Normal'], fontName='Helvetica-Bold')
    
    # 1. Top Green Header
    # Adjust date for Argentina timezone since `order.created_at` might be in UTC from DB
    from datetime import timedelta
    date_ar = order.created_at - timedelta(hours=3) if getattr(order.created_at, "tzinfo", None) is None or order.created_at.tzinfo.utcoffset(order.created_at).total_seconds() == 0 else order.created_at
    
    header_date = Paragraph(f"<font color='white'><b>Fecha: {date_ar.strftime('%d/%m/%Y')}</b></font>", bold_style)
    t_header = Table([[header_date]], colWidths=[18*cm])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#008f68")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 0.5*cm))
    
    # 2. Company Info & Logo
    logo_path = "/app/data/images/UNPO1.jpg" # Using the valid logo
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=4*cm, height=2*cm)
    else:
        logo = Paragraph("<b>UNPO</b>", ParagraphStyle(name="Title", fontSize=24, parent=styles["Normal"]))
        
    company_info = Paragraph("Razón Social<br/>CUIT<br/>WEB", normal_style)
    remito_number = Paragraph(f"<b>REMITO N° {order.id}</b>", normal_style)
    
    t_company = Table([[logo, company_info, remito_number]], colWidths=[5*cm, 8*cm, 5*cm])
    t_company.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (2,0), (2,0), 'CENTER'),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 1, colors.black),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_company)
    elements.append(Spacer(1, 0.5*cm))
    
    # 3. Client Info
    lead = order.lead
    client_data = f"""
    <b>Nombre:</b> {lead.full_name}<br/>
    <b>DNI/CUIT:</b> {lead.dni_cuit or ''}<br/>
    <b>Domicilio:</b> {lead.address or ''}<br/>
    <b>Localidad:</b> {lead.locality or ''}<br/>
    <b>Provincia:</b> {lead.province or ''}<br/>
    <b>Teléfono:</b> {lead.phone or ''}<br/>
    <b>C.P:</b> {lead.zip_code or ''}
    """
    t_client = Table([[Paragraph(client_data, normal_style)]], colWidths=[18*cm])
    t_client.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_client)
    elements.append(Spacer(1, 0.5*cm))
    
    # 4. Products Table
    table_data = [["BULTO", "UNIDAD", "DESCRIPCIÓN", "PRECIO", "PRECIO TOTAL"]]
    
    for item in order.items:
        table_data.append([
            "1",  # BULTO (simplificado)
            str(int(item.quantity)), # UNIDAD
            str(item.product.name if item.product else item.product_sku),
            f"${item.unit_price:,.2f}",
            f"${item.total_price:,.2f}"
        ])
        
    # Table Total
    table_data.append(["", "", "", "", f"${order.total_amount:,.2f}"])
        
    t_products = Table(table_data, colWidths=[2*cm, 2*cm, 8*cm, 3*cm, 3*cm])
    t_products.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f172a")), # Slate-900 header
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (2,1), (2,-1), 'LEFT'),
        ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")), # Light slate grid
        ('BOX', (0,0), (-1, -2), 1, colors.HexColor("#94a3b8")),
        ('BOX', (-1, -1), (-1, -1), 1, colors.HexColor("#94a3b8")), # Total box
        ('BACKGROUND', (-1,-1), (-1,-1), colors.HexColor("#f8fafc")), # Total background
        ('FONTNAME', (-1,-1), (-1,-1), 'Helvetica-Bold'),
    ]))
    elements.append(t_products)
    elements.append(Spacer(1, 1*cm))
    
    # 5. Received Box
    t_received = Table([[Paragraph("RECIBÍ CONFORME:", normal_style)]], colWidths=[18*cm], rowHeights=[2*cm])
    t_received.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_received)
    elements.append(Spacer(1, 0.5*cm))
    
    # 6. Transport Details
    delivery_d = order.delivery_date.strftime('%d/%m/%Y') if order.delivery_date else ''
    transport_data = f"""
    DATOS DEL TRANSPORTISTA<br/>
    Nombre: {order.transport_name or ''}<br/>
    DNI: {order.transport_dni or ''}<br/>
    Patente: {order.license_plate or ''}<br/>
    Lugar de Entrega: {order.delivery_address or ''}<br/>
    Fecha de Entrega: {delivery_d}
    """
    t_transport = Table([[Paragraph(transport_data, normal_style)]], colWidths=[18*cm])
    t_transport.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_transport)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.read()

def generate_catalog_pdf(products) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    elements = []
    
    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]
    bold_style = ParagraphStyle(name='Bold', parent=styles['Normal'], fontName='Helvetica-Bold')
    title_style = ParagraphStyle(name='CatTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor("#0f172a"), spaceAfter=12)
    
    # 1. Top Header
    header_date = Paragraph(f"<font color='white'><b>Catálogo Mayorista UNPO - Fecha: {datetime.now().strftime('%d/%m/%Y')}</b></font>", bold_style)
    t_header = Table([[header_date]], colWidths=[18*cm])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#008f68")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 0.5*cm))
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # This reaches backend/app, need to go one level up to backend
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    IMAGES_DIR = os.path.join(PROJECT_ROOT, "data", "images")
    
    logo_path = os.path.join(IMAGES_DIR, "UNPO1.jpg")
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=5*cm, height=2.5*cm)
    else:
        logo = Paragraph("<b>UNPO</b>", ParagraphStyle(name="Title", fontSize=24, parent=styles["Normal"]))
        
    company_info = Paragraph("<b>Importadores Directos Bazar</b><br/>Precios Mayoristas (Sin IVA)<br/>unpo.com.ar", normal_style)
    
    t_company = Table([[logo, company_info]], colWidths=[8*cm, 10*cm])
    t_company.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    elements.append(t_company)
    elements.append(Spacer(1, 0.5*cm))
    
    # 3. Products Table
    table_data = [["IMAGEN", "SKU", "PRODUCTO", "CATEGORÍA", "PRECIO\n(Sin IVA)"]]
    
    # Sort products by category name for better presentation
    products_sorted = sorted(products, key=lambda x: (str(x.category.name) if x.category and x.category.name else "", str(x.name) if x.name else ""))
    
    for p in products_sorted:
        # Load Image
        img_element = ""
        if p.images and len(p.images) > 0:
            filename = p.images[0].replace("/static/images/", "").strip("/")
            img_path = os.path.join(IMAGES_DIR, filename)
            if os.path.exists(img_path):
                try:
                    pil_img = PILImage.open(img_path)
                    if pil_img.mode in ("RGBA", "CMYK", "LA", "P"):
                        # Remove transparency and convert
                        background = PILImage.new('RGB', pil_img.size, (255, 255, 255))
                        if pil_img.mode in ('RGBA', 'LA'):
                            background.paste(pil_img, mask=pil_img.split()[-1])
                        else:
                            background.paste(pil_img)
                        pil_img = background
                    else:
                        pil_img = pil_img.convert("RGB")
                    
                    pil_img.thumbnail((250, 250))
                    img_io = io.BytesIO()
                    pil_img.save(img_io, format='JPEG', quality=75, optimize=True)
                    img_io.seek(0)
                    img_element = Image(img_io, width=4.0*cm, height=4.0*cm)
                except Exception as e:
                    print(f"Error loading image {img_path}: {e}")
                    img_element = ""
                
        # Format Text Elements
        cat_name = p.category.name if p.category else "-"
        import html
        safe_name = html.escape(str(p.name or ""))
        safe_desc = html.escape(str(p.description or ""))
        name_desc = f"<b>{safe_name}</b><br/><font size=8 color='#475569'>{safe_desc}</font>"
        prod_para = Paragraph(name_desc, normal_style)
        price_val = p.price_wholesale if getattr(p, "price_wholesale", None) is not None else 0.0
        price_str = f"${price_val:,.2f}"
        
        table_data.append([
            img_element,
            p.sku,
            prod_para,
            cat_name,
            price_str
        ])
        
    t_products = Table(table_data, colWidths=[4.2*cm, 2.3*cm, 6.5*cm, 2.5*cm, 2.5*cm])
    t_products.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (2,1), (2,-1), 'LEFT'), # Left align product info
        ('ALIGN', (4,1), (4,-1), 'RIGHT'), # Right align prices
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('BOX', (0,0), (-1, -1), 1, colors.HexColor("#94a3b8")),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
    ]))
    
    elements.append(t_products)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.read()
