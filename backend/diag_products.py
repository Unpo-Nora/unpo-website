import pandas as pd
import os

def audit_products():
    data_dir = 'data'
    csv_mayorista = os.path.join(data_dir, 'MAYORISTA.csv')
    csv_catalogo = os.path.join(data_dir, 'CATALOGO.csv')
    img_dir = os.path.join(data_dir, 'images')

    print("--- INICIANDO AUDITORIA DE PRODUCTOS ---")
    
    try:
        df_may = pd.read_csv(csv_mayorista, header=3, dtype=str)
        df_cat = pd.read_csv(csv_catalogo, dtype=str)
    except Exception as e:
        print(f"Error cargando CSVs: {e}")
        return

    def normalize_sku(val):
        if pd.isna(val) or str(val).strip() == '': return None
        val = str(val).strip()
        if '.' in val: val = val.split('.')[0]
        try:
            if val.isdigit(): return str(int(val))
        except: pass
        return val

    # Identificar columnas
    col_sku_may = 'COD. UNPO' if 'COD. UNPO' in df_may.columns else df_may.columns[0]
    col_name_may = 'DESCRIPCION' if 'DESCRIPCION' in df_may.columns else df_may.columns[1]
    col_stock_may = 'UNIDADES' if 'UNIDADES' in df_may.columns else df_may.columns[17]

    df_may['sku_norm'] = df_may[col_sku_may].apply(normalize_sku)
    
    df_cat.columns = [c.strip() for c in df_cat.columns]
    col_sku_cat = 'COD. UNPO' if 'COD. UNPO' in df_cat.columns else df_cat.columns[0]
    df_cat['sku_norm'] = df_cat[col_sku_cat].apply(normalize_sku)

    all_images = os.listdir(img_dir) if os.path.exists(img_dir) else []
    
    issues = []
    
    for idx, row in df_may.iterrows():
        sku_raw = row.get('sku_norm')
        if pd.isna(sku_raw): continue
        sku = str(sku_raw).strip()
        if not sku or sku == 'nan': continue
        
        name = str(row[col_name_may])
        
        # Check stock
        stock = 0
        raw_stock = row[col_stock_may]
        if not pd.isna(raw_stock) and str(raw_stock).strip() != '':
            try:
                val = str(raw_stock).replace('.', '').replace(',', '.')
                stock = int(float(val))
            except: pass
            
        # Check Catálogo match
        cat_match = df_cat[df_cat['sku_norm'] == sku]
        desc_cat = name
        price = "No price found"
        if not cat_match.empty:
            cat_info = cat_match.iloc[0]
            if 'NOMBRE' in cat_info and not pd.isna(cat_info['NOMBRE']):
                desc_cat = str(cat_info['NOMBRE'])
            
            raw_price = cat_info.get('CONTADO / TRANSFERENCIA', None)
            if pd.isna(raw_price) and len(cat_info) > 7:
                 raw_price = cat_info.iloc[7]
            price = str(raw_price) if not pd.isna(raw_price) else "Missing"
        else:
            issues.append(f"[SKU {sku}] No existe en CATALOGO.csv - Nombre: {name}")
            
        # Check Images
        has_img = False
        for f in all_images:
            fname_lower = f.lower()
            if fname_lower.startswith(sku.lower()) and (len(fname_lower) == len(sku) or fname_lower[len(sku)] in ['.', '_', '-']):
                has_img = True
                break
                
        if not has_img:
            issues.append(f"[SKU {sku}] Faltan imágenes - Nombre: {desc_cat} - Stock: {stock}")

    with open('reporte.txt', 'w', encoding='utf-8') as f:
        f.write("--- PROBLEMAS ENCONTRADOS ---\n")
        if not issues:
            f.write("Todo parece correcto.\n")
        else:
            for i in issues:
                f.write(i + "\n")

if __name__ == "__main__":
    audit_products()
