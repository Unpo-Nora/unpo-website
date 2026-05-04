import io
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from PIL import Image as PILImage
from reportlab.lib.utils import ImageReader
from .. import models
import requests
from io import BytesIO

def format_price(amount):
    return f"${round(amount):,}".replace(",", ".")

def _process_and_resize_image(img_url, images_dir):
    """
    Helper to fetch, convert to RGB, and resize an image.
    Returns (BytesIO_buffer, None) or (None, Error)
    """
    try:
        if img_url.startswith("http"):
            response = requests.get(img_url, timeout=10)
            if response.status_code != 200:
                return None, f"HTTP {response.status_code}"
            img_data = response.content
        else:
            filename = img_url.replace("/static/images/", "").strip("/")
            img_path = os.path.join(images_dir, filename)
            if not os.path.exists(img_path):
                return None, "File not found"
            with open(img_path, "rb") as f:
                img_data = f.read()

        with PILImage.open(io.BytesIO(img_data)) as pil_img:
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")
            
            # Resize for catalog (keeping aspect ratio)
            pil_img.thumbnail((300, 300), PILImage.Resampling.LANCZOS)
            
            out_io = io.BytesIO()
            # Lower quality for significant weight reduction
            pil_img.save(out_io, format='JPEG', quality=60, optimize=True)
            out_io.seek(0)
            return out_io, None
    except Exception as e:
        return None, str(e)

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
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    IMAGES_DIR = os.path.join(PROJECT_ROOT, "data", "images")
    logo_path = os.path.join(IMAGES_DIR, "UNPO1.jpg")
    
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=4.5*cm, height=2.2*cm)
    else:
        logo = Paragraph("<b>UNPO</b>", ParagraphStyle(name="Title", fontSize=24, parent=styles["Normal"]))
        
    company_info_text = """<b>UNPO Oficial</b><br/>
    Venta Mayorista<br/>
    Sitio Web: unpo.com.ar<br/>
    Atención al Cliente: +5491131488378"""
    company_info = Paragraph(company_info_text, normal_style)
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
    table_data = [[
        Paragraph("<b>BULTO</b>", normal_style), 
        Paragraph("<b>UNIDAD</b>", normal_style), 
        Paragraph("<b>SKU</b>", normal_style), 
        Paragraph("<b>DESCRIPCIÓN</b>", normal_style), 
        Paragraph("<b>PRECIO<br/>(sin IVA)</b>", normal_style), 
        Paragraph("<b>PRECIO TOTAL<br/>(sin IVA)</b>", normal_style)
    ]]
    
    for item in order.items:
        desc_text = str(item.product.name if item.product else item.product_sku)
        table_data.append([
            "1",  # BULTO (simplificado)
            str(int(item.quantity)), # UNIDAD
            str(item.product_sku), # SKU
            Paragraph(desc_text, normal_style),
            format_price(item.unit_price),
            format_price(item.total_price)
        ])
        
    # Calculate implicit discount and IVA based on discrepancy
    sum_items_raw = sum(float(item.total_price) for item in order.items)
    target = float(order.total_amount)
    
    best_d = 0.0
    best_iva = False
    
    for iva_opt in [False, True]:
        for d_opt in [0.0, 0.05, 0.10, 0.15]:
            calc = sum_items_raw * (1 - d_opt)
            if iva_opt:
                calc *= 1.21
            # 10 ARS tolerance for rounding
            if abs(calc - target) < 10.0:
                best_d = d_opt
                best_iva = iva_opt
                break
                
    table_data.append(["", "", "", "", "SUBTOTAL:", format_price(sum_items_raw)])
    
    subtotal_desc = sum_items_raw * (1 - best_d)
    
    if best_d > 0.0:
        desc_amount = sum_items_raw - subtotal_desc
        table_data.append(["", "", "", "", f"DESCUENTO ({int(best_d*100)}%):", "-" + format_price(desc_amount)])
        if not best_iva:
            table_data.append(["", "", "", "", "TOTAL FINAL:", format_price(target)])
            
    if best_iva:
        iva_amount = subtotal_desc * 0.21
        table_data.append(["", "", "", "", "IVA (21%):", "+" + format_price(iva_amount)])
        table_data.append(["", "", "", "", "TOTAL FINAL:", format_price(target)])
        
    if best_d == 0.0 and not best_iva:
        # Just simple replacement of TOTAL FINAL since SUBTOTAL is already there
        pass
        
    t_products = Table(table_data, colWidths=[1.8*cm, 1.8*cm, 2.0*cm, 6.4*cm, 3*cm, 3*cm])
    t_products.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#475569")), # Slate-600 header
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (3,1), (3,-1), 'LEFT'),
        ('ALIGN', (4,1), (-1,-1), 'RIGHT'),
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

def generate_catalog_pdf(products, exchange_rate: float = 1450.0) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    elements = []
    
    # Store image buffers to prevent them from being closed before doc.build()
    image_buffers = []
    
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
    header_row = ["IMAGEN", "SKU", "PRODUCTO", "CATEGORÍA", "PRECIO\n(Sin IVA)"]
    all_rows = []
    
    # Sort products by category name for better presentation
    products_sorted = sorted(products, key=lambda x: (str(x.category.name) if x.category and x.category.name else "", str(x.name) if x.name else ""))
    
    # Step 1: Pre-calculate prices and filter
    valid_products = []
    for p in products_sorted:
        usd_price = float(p.price_usd) if p.price_usd is not None else 0.0
        calculated_price = usd_price * exchange_rate
        
        if calculated_price <= 0:
            wholesale = float(p.price_wholesale) if p.price_wholesale is not None else 0.0
            if wholesale > 0:
                calculated_price = wholesale
            else:
                continue
        
        price_str = f"{format_price(calculated_price)} + IVA"
        valid_products.append((p, price_str))

    # Step 2: Parallel Image Processing
    print(f"Starting parallel image processing for {len(valid_products)} products...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Prepare list of (product, img_url)
        tasks = []
        for p, price_str in valid_products:
            img_url = p.images[0] if (p.images and len(p.images) > 0) else None
            tasks.append((p, price_str, img_url))
        
        # Map URLs to processing function
        image_futures = []
        for p, price_str, img_url in tasks:
            if img_url:
                image_futures.append(executor.submit(_process_and_resize_image, img_url, IMAGES_DIR))
            else:
                image_futures.append(None)

    # Step 3: Assemble Rows
    for i, (p, price_str, img_url) in enumerate(tasks):
        img_element = ""
        future = image_futures[i]
        if future:
            img_io, error = future.result()
            if img_io:
                image_buffers.append(img_io)
                img_element = Image(img_io, width=4.0*cm, height=4.0*cm)
            elif error:
                print(f"Error processing image for {p.sku}: {error}")

        cat_name_val = p.category.name if p.category else "-"
        cat_para = Paragraph(cat_name_val, normal_style)
        
        import html
        safe_name = html.escape(str(p.name or ""))
        safe_desc = html.escape(str(p.description or ""))
        name_desc = f"<b>{safe_name}</b><br/><font size=8 color='#475569'>{safe_desc}</font>"
        prod_para = Paragraph(name_desc, normal_style)
        
        all_rows.append([
            img_element,
            p.sku,
            prod_para,
            cat_para,
            price_str
        ])
        
    table_style = TableStyle([
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
    ])

    CHUNK_SIZE = 50
    for i in range(0, len(all_rows), CHUNK_SIZE):
        chunk = all_rows[i:i + CHUNK_SIZE]
        t_products = Table([header_row] + chunk, colWidths=[4.2*cm, 2.0*cm, 6.2*cm, 2.4*cm, 3.2*cm], repeatRows=1)
        t_products.setStyle(table_style)
        elements.append(t_products)
        if i + CHUNK_SIZE < len(all_rows):
             elements.append(Spacer(1, 0.5*cm))
             
    doc.build(elements)
    buffer.seek(0)
    return buffer.read()
