import pandas as pd
import os
from sqlalchemy.orm import Session
from .. import models
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def sync_products_from_excel(db: Session, excel_path: str):
    """
    Sincroniza el catálogo de productos priorizando archivos CSV para evitar bloqueos del Excel.
    Usa:
    - backend/data/MAYORISTA.csv (Stock Real, Categorías, SKUs)
    - backend/data/CATALOGO.csv (Nombres, Precios, posibles Imágenes)
    """
    data_dir = os.path.dirname(excel_path)
    csv_mayorista = os.path.join(data_dir, 'MAYORISTA.csv')
    csv_catalogo = os.path.join(data_dir, 'CATALOGO.csv')

    if not os.path.exists(csv_mayorista):
        return {"status": "error", "message": f"Archivo crucial {csv_mayorista} no encontrado."}

    try:
        # 1. Leer MAYORISTA.csv (Fuente principal de Stock y SKUs)
        # Saltamos las primeras 3 filas de metadatos (el header real está en la fila 3, index 3 de pd.read_csv)
        df_may = pd.read_csv(csv_mayorista, header=3, dtype=str)
        
        # 2. Leer CATALOGO.csv (Fuente de nombres refinados y descripciones)
        # Este CSV tiene el header en la primera fila.
        df_cat = pd.read_csv(csv_catalogo, dtype=str) if os.path.exists(csv_catalogo) else None

        def normalize_sku(val):
            if pd.isna(val) or str(val).strip() == '': return None
            val = str(val).strip()
            # Eliminar punto decimal si lo tiene (ej: "123.0")
            if '.' in val: val = val.split('.')[0]
            # Quitar ceros a la izquierda
            try:
                if val.isdigit():
                    return str(int(val))
            except:
                pass
            return val

        # Identificar columnas por nombre o índice fallback
        col_sku_may = 'COD. UNPO' if 'COD. UNPO' in df_may.columns else df_may.columns[0]
        col_name_may = 'DESCRIPCION' if 'DESCRIPCION' in df_may.columns else df_may.columns[1]
        col_cat_may = 'CATEGORIA' if 'CATEGORIA' in df_may.columns else df_may.columns[2]
        col_stock_may = 'UNIDADES' if 'UNIDADES' in df_may.columns else df_may.columns[17]
        col_weight_may = 'KG' if 'KG' in df_may.columns else df_may.columns[3]

        df_may['sku_norm'] = df_may[col_sku_may].apply(normalize_sku)
        
        if df_cat is not None:
            # En CATALOGO.csv los nombres de columnas son: COD. UNPO, NOMBRE, DESCRIPCION, ...
            # Limpiamos nombres de columnas por si tienen espacios
            df_cat.columns = [c.strip() for c in df_cat.columns]
            col_sku_cat = 'COD. UNPO' if 'COD. UNPO' in df_cat.columns else df_cat.columns[0]
            df_cat['sku_norm'] = df_cat[col_sku_cat].apply(normalize_sku)

        counts = {"created": 0, "updated": 0, "errors": 0}
        processed_skus = set()

        # --- Helper for Media ---
        def _get_media(sku_val, fallback_cat_info=None):
            images = []
            videos = []
            img_dir = os.path.join(data_dir, 'images')
            vid_dir = os.path.join(data_dir, 'videos')

            try:
                from PIL import Image
                from pillow_heif import register_heif_opener
                register_heif_opener()
                has_heif = True
            except ImportError:
                has_heif = False

            if os.path.exists(img_dir):
                for f in sorted(os.listdir(img_dir)):
                    fname_lower = f.lower()
                    if fname_lower.startswith(sku_val.lower()) and (len(fname_lower) == len(sku_val) or fname_lower[len(sku_val)] in ['.', '_', '-']):
                        ext = os.path.splitext(f)[1].lower()
                        if ext in ['.jpg', '.jpeg', '.png', '.webp', '.heic']:
                            if ext == '.heic' and has_heif:
                                try:
                                    jpg_name = f"{os.path.splitext(f)[0]}.jpg"
                                    if not os.path.exists(os.path.join(img_dir, jpg_name)):
                                        heif_img = Image.open(os.path.join(img_dir, f))
                                        heif_img.save(os.path.join(img_dir, jpg_name), "JPEG")
                                    images.append(f"/static/images/{jpg_name}")
                                except Exception: pass
                            elif ext != '.heic':
                                images.append(f"/static/images/{f}")

            if os.path.exists(vid_dir):
                for v in sorted(os.listdir(vid_dir)):
                    vname_lower = v.lower()
                    if vname_lower.startswith(sku_val.lower()) and (len(vname_lower) == len(sku_val) or vname_lower[len(sku_val)] in ['.', '_', '-']):
                        if os.path.splitext(v)[1].lower() in ['.mp4', '.webm', '.mov', '.m4v']:
                            videos.append(f"/static/videos/{v}")
            
            images = list(dict.fromkeys(images))
            if not images and fallback_cat_info is not None:
                for cell in fallback_cat_info:
                    if isinstance(cell, str) and ('http' in cell or 'Image' in cell):
                        if 'http' in cell:
                            images.append(cell)
                            break
            return images, videos

        # Iterar sobre MAYORISTA (que tiene el stock real)
        total_rows = len(df_may)
        print(f"Starting sync for {total_rows} rows...")
        
        for idx, row in df_may.iterrows():
            sku = row.get('sku_norm')
            if not sku or sku == 'nan': continue
            processed_skus.add(sku)

            # Extraer Stock
            stock_val = 0
            try:
                raw_stock = row[col_stock_may]
                if pd.isna(raw_stock) or str(raw_stock).strip() == '':
                    stock_val = 0
                else:
                    # Limpiar comas de miles y puntos decimales
                    val = str(raw_stock).replace('.', '').replace(',', '.')
                    stock_val = int(float(val))
            except Exception as e:
                logger.warning(f"Error parseando stock para SKU {sku}: {e}")
                stock_val = 0

            # Buscar info extra en CATALOGO
            cat_info = df_cat[df_cat['sku_norm'] == sku].iloc[0] if df_cat is not None and sku in df_cat['sku_norm'].values else None
            
            # Nombre: Priorizar CATALOGO['NOMBRE'], luego MAYORISTA['DESCRIPCION']
            name = row[col_name_may] if col_name_may in row else f"Producto {sku}"
            description = ""
            
            if cat_info is not None:
                try:
                    # Intentar obtener NOMBRE de CATALOGO
                    if 'NOMBRE' in cat_info and not pd.isna(cat_info['NOMBRE']) and str(cat_info['NOMBRE']).strip():
                        name = str(cat_info['NOMBRE']).strip()
                    
                    # Intentar obtener DESCRIPCION de CATALOGO
                    if 'DESCRIPCION' in cat_info and not pd.isna(cat_info['DESCRIPCION']) and str(cat_info['DESCRIPCION']).strip():
                        description = str(cat_info['DESCRIPCION']).strip()
                except Exception as e:
                    logger.warning(f"Error extrayendo nombre/desc de CATALOGO para SKU {sku}: {e}")

            if not name or name == 'nan': name = f"Producto {sku}"
            
            # Corrección manual de nombre para el Koala
            if str(sku) == "20800064":
                name = "PELUCHE KOALA NARIZ NEGRA"


            # Categoría
            cat_name = str(row[col_cat_may] if col_cat_may in row else 'General').strip()
            if cat_name == 'nan' or not cat_name: cat_name = 'General'
            
            db_category = db.query(models.Category).filter(models.Category.name == cat_name).first()
            if not db_category:
                db_category = models.Category(name=cat_name)
                db.add(db_category)
                db.flush()

            # Precio (Priorizamos CATALOGO.csv: CONTADO / TRANSFERENCIA)
            price = Decimal(0)
            try:
                raw_price = None
                # Priorizar CATALOGO 'CONTADO / TRANSFERENCIA'
                if cat_info is not None:
                    if 'CONTADO / TRANSFERENCIA' in cat_info and not pd.isna(cat_info['CONTADO / TRANSFERENCIA']) and str(cat_info['CONTADO / TRANSFERENCIA']).strip():
                        raw_price = cat_info['CONTADO / TRANSFERENCIA']
                    elif len(cat_info) > 7 and not pd.isna(cat_info.iloc[7]) and str(cat_info.iloc[7]).strip():
                        raw_price = cat_info.iloc[7]
                
                # Fallback a MAYORISTA 'PRECIO SIN IVA' (columna 9 aprox) si no hay precio en CATALOGO
                if pd.isna(raw_price) or not str(raw_price).strip() or str(raw_price) == '0':
                    col_price_may = 'PRECIO SIN IVA' if 'PRECIO SIN IVA' in df_may.columns else (df_may.columns[9] if len(df_may.columns) > 9 else None)
                    if col_price_may and col_price_may in row and not pd.isna(row[col_price_may]) and str(row[col_price_may]).strip():
                        raw_price = row[col_price_may]
                    else:
                        raw_price = row.iloc[8] if len(row) > 8 else '0'
                
                if not pd.isna(raw_price) and str(raw_price).strip():
                    # Formato del CSV suele ser "29,122.70" o "4.125,00" o "4,125.00"
                    # Si tiene coma y punto, asumimos US: "1,234.56" -> quitar coma, mantener punto
                    # Si tiene solo comas: "4.125,00" -> quitar punto, cambiar coma a punto
                    price_str = str(raw_price).replace('$', '').strip()
                    if '.' in price_str and ',' in price_str:
                        # Formato 1,234.56 or 1.234,56
                        if price_str.find(',') < price_str.find('.'): # 1,234.56
                            price_str = price_str.replace(',', '')
                        else: # 1.234,56
                            price_str = price_str.replace('.', '').replace(',', '.')
                    elif ',' in price_str: # Solo comas: 1234,56
                        price_str = price_str.replace(',', '.')
                    elif '.' in price_str and len(price_str.split('.')[-1]) == 3: # 1.234 (separador miles)
                        price_str = price_str.replace('.', '')
                    
                    if price_str:
                        price = Decimal(price_str)
            except Exception as e:
                logger.warning(f"Error parseando precio para SKU {sku}: {e}")
                price = Decimal(0)

            # Corrección manual de precio para el Koala
            if str(sku) == "20800064":
                price = Decimal('17138.43')

            # --- Galería Multimedia ---
            images, videos = _get_media(sku, cat_info)

            product_data = {
                "sku": sku,
                "name": name,
                "description": description,
                "category_id": db_category.id if db_category else None,
                "is_active": True,
                "price_wholesale": price,
                "stock_quantity": stock_val,
                "images": images,
                "videos": videos,
                "weight": Decimal(str(row.iloc[3] if len(row) > 3 and not pd.isna(row.iloc[3]) else 0)),
                "is_featured": False
            }

            # Upsert
            existing = db.query(models.Product).filter(models.Product.sku == sku).first()
            if existing:
                for key, value in product_data.items():
                    setattr(existing, key, value)
                counts["updated"] += 1
            else:
                db_product = models.Product(**product_data)
                db.add(db_product)
                counts["created"] += 1

        # 3. Procesar CATALOGO.csv para los SKU que no estaban en MAYORISTA
        if df_cat is not None:
            for idx, cnt_row in df_cat.iterrows():
                sku = cnt_row.get('sku_norm')
                if not sku or sku == 'nan' or sku in processed_skus: continue
                processed_skus.add(sku)

                # Extraer Stock
                stock_val = 0
                raw_stock = cnt_row['Stock'] if 'Stock' in cnt_row else (cnt_row.iloc[6] if len(cnt_row) > 6 else 0)
                if not pd.isna(raw_stock):
                    try:
                        val = str(raw_stock).replace('.', '').replace(',', '.')
                        stock_val = int(float(val))
                    except: pass

                name = str(cnt_row['NOMBRE']).strip() if 'NOMBRE' in cnt_row and not pd.isna(cnt_row['NOMBRE']) else (str(cnt_row.iloc[1]).strip() if len(cnt_row) > 1 and not pd.isna(cnt_row.iloc[1]) else f"Producto {sku}")
                description = str(cnt_row['DESCRIPCION']).strip() if 'DESCRIPCION' in cnt_row and not pd.isna(cnt_row['DESCRIPCION']) else (str(cnt_row.iloc[2]).strip() if len(cnt_row) > 2 and not pd.isna(cnt_row.iloc[2]) else "")
                cat_name = str(cnt_row['CATEGORIA']).strip() if 'CATEGORIA' in cnt_row and not pd.isna(cnt_row['CATEGORIA']) else (str(cnt_row.iloc[3]).strip() if len(cnt_row) > 3 and not pd.isna(cnt_row.iloc[3]) else 'General')

                db_category = db.query(models.Category).filter(models.Category.name == cat_name).first()
                if not db_category:
                    db_category = models.Category(name=cat_name)
                    db.add(db_category)
                    db.flush()

                price = Decimal(0)
                try:
                    # En CATALOGO.csv sin headers, index 5 es Efectivo/Transferencia, index 7 es Precio lista
                    raw_price = cnt_row['CONTADO / TRANSFERENCIA'] if 'CONTADO / TRANSFERENCIA' in cnt_row else (cnt_row.iloc[5] if len(cnt_row) > 5 else '0')
                    if pd.isna(raw_price) or not str(raw_price).strip() or str(raw_price) == '0':
                        raw_price = cnt_row.iloc[7] if len(cnt_row) > 7 else '0'

                    if not pd.isna(raw_price) and str(raw_price).strip():
                        price_str = str(raw_price).replace('$', '').strip()
                        if '.' in price_str and ',' in price_str:
                            if price_str.find(',') < price_str.find('.'): price_str = price_str.replace(',', '')
                            else: price_str = price_str.replace('.', '').replace(',', '.')
                        elif ',' in price_str: price_str = price_str.replace(',', '.')
                        elif '.' in price_str and len(price_str.split('.')[-1]) == 3: price_str = price_str.replace('.', '')
                        if price_str: price = Decimal(price_str)
                except: pass

                images, videos = _get_media(sku, cnt_row)

                product_data = {
                    "sku": sku,
                    "name": name,
                    "description": description,
                    "category_id": db_category.id if db_category else None,
                    "is_active": True,
                    "price_wholesale": price,
                    "stock_quantity": stock_val,
                    "images": images,
                    "videos": videos,
                    "weight": Decimal("0"),
                    "is_featured": False
                }

                existing = db.query(models.Product).filter(models.Product.sku == sku).first()
                if existing:
                    for key, value in product_data.items(): setattr(existing, key, value)
                    counts["updated"] += 1
                else:
                    db_product = models.Product(**product_data)
                    db.add(db_product)
                    counts["created"] += 1

        # 4. Desactivar productos que ya no están en el Excel (fantasmas)
        inactive_count = 0
        all_db_products = db.query(models.Product).all()
        for db_prod in all_db_products:
            if db_prod.sku not in processed_skus:
                if db_prod.is_active:
                    db_prod.is_active = False
                    # También ponemos el stock en 0 por seguridad
                    db_prod.stock_quantity = 0
                    inactive_count += 1
        
        counts["deactivated"] = inactive_count

        db.commit()
        return {"status": "success", "counts": counts}

    except Exception as e:
        db.rollback()
        logger.error(f"Error en sincronización CSV: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

