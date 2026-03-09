import pandas as pd
from sqlalchemy.orm import Session
from .. import models, schemas, crud
import io
from typing import List, Dict, Any

def process_excel_leads(file_content: bytes, filename: str, db: Session) -> Dict[str, Any]:
    """
    Procesa un archivo Excel y carga los leads en la base de datos.
    Detecta automáticamente si es el formato de Marketing o el de Vendedores.
    """
    try:
        # Cargamos el Excel en memoria
        # Base de datos UNPO.xlsx no suele tener offsets locos
        # Clientes.xlsm tiene el header en la fila 3 (index 2)
        
        header_idx = 0
        if "Clientes" in filename:
            header_idx = 2
            
        df = pd.read_excel(io.BytesIO(file_content), header=header_idx)
        
        # Limpieza básica de nombres de columnas (quitar espacios, etc)
        df.columns = [str(c).strip() for c in df.columns]
        
        imported_count = 0
        skipped_count = 0
        
        for _, row in df.iterrows():
            lead_data = {}
            
            # --- Mapeo dinámico según columnas encontradas ---
            
            # Identificación Base
            if 'Nombre' in df.columns:
                lead_data['full_name'] = str(row['Nombre'])
            
            # Teléfono: Intentamos varios nombres posibles
            phone_col = None
            for c in ['Telefono', 'Telefono ok', 'Teléfono']:
                if c in df.columns:
                    phone_col = c
                    break
            if phone_col:
                lead_data['phone'] = str(row[phone_col])
                
            # Fecha: Extraer fecha original si existe
            if 'Fecha' in df.columns:
                try:
                    dt = pd.to_datetime(row['Fecha'])
                    # Forzamos mediodía para evitar que desfases de zona horaria (UTC-3) 
                    # muevan la fecha al día anterior al guardar en la DB.
                    lead_data['lead_date'] = dt.replace(hour=12, minute=0, second=0).to_pydatetime()
                except:
                    pass
                
            # Email
            mail_col = None
            for c in ['Mail', 'Email', 'correo']:
                if c in df.columns:
                    mail_col = c
                    break
            if mail_col:
                lead_data['email'] = str(row[mail_col])
            else:
                # Si no hay email, generamos uno ficticio o dejamos nulo si el esquema lo permite
                # Para evitar conflictos de unicidad si los hay
                lead_data['email'] = f"import_{imported_count}_{skipped_count}@unpoboton.com"

            # Datos de Negocio (Base de datos UNPO)
            if '¿Qué tipo de negocio tenés?' in df.columns:
                lead_data['business_type'] = str(row['¿Qué tipo de negocio tenés?'])
            if 'Selecciona tu volumen de compra' in df.columns:
                lead_data['purchase_volume'] = str(row['Selecciona tu volumen de compra'])
            if '¿Por cuál categoría estár más interesado?' in df.columns:
                lead_data['category_interest'] = str(row['¿Por cuál categoría estár más interesado?'])
            if '¿En qué producto estabas interesado?' in df.columns:
                lead_data['product_interest'] = str(row['¿En qué producto estabas interesado?'])
            if 'Campaña' in df.columns:
                lead_data['campaign'] = str(row['Campaña'])
            if 'Plataforma' in df.columns:
                lead_data['platform'] = str(row['Plataforma'])
                
            # Datos de Vendedor (Clientes.xlsm)
            if 'Vendedor' in df.columns:
                lead_data['seller'] = str(row['Vendedor'])
                lead_data['source'] = "EXCEL_VENDEDORES"
            else:
                lead_data['source'] = "EXCEL_MARKETING"

            # Validación mínima: Si no tiene nombre ni teléfono, lo saltamos
            if pd.isna(row.get('Nombre')) and not phone_col:
                skipped_count += 1
                continue

            try:
                # --- Prevención de Duplicados ---
                existing = crud.get_lead_by_contact(db, email=lead_data.get('email'), phone=lead_data.get('phone'))
                
                if existing:
                    # Por ahora saltamos, pero podríamos actualizar datos
                    skipped_count += 1
                    continue
                    
                # Creamos el lead
                lead_schema = schemas.LeadCreate(**lead_data)
                crud.create_lead(db, lead_schema)
                imported_count += 1
            except Exception as e:
                print(f"Error al importar fila: {e}")
                skipped_count += 1
                
        return {
            "status": "success",
            "imported": imported_count,
            "skipped": skipped_count,
            "total_rows": len(df)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
