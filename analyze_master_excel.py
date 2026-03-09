import pandas as pd
import os

file_path = r"c:\Users\user\.gemini\antigravity\scratch\UNPO_NORA_System\backend\data\Panel_control_UNPO.xlsm"

def analyze_excel():
    if not os.path.exists(file_path):
        print(f"Error: No se encuentra el archivo en {file_path}")
        return

    try:
        xl = pd.ExcelFile(file_path, engine='openpyxl')
        print(f"Hojas encontradas: {xl.sheet_names}")
        
        # Analizar todas las hojas para encontrar productos
        for sheet in xl.sheet_names:
            print(f"\n--- Analizando hoja: {sheet} ---")
            try:
                # Leemos un poco más para captar cabeceras si hay filas vacías al inicio
                df = pd.read_excel(file_path, sheet_name=sheet, nrows=15, engine='openpyxl')
                print("Columnas detectadas:", df.columns.tolist())
                print("Muestra de datos (primeras 5 filas):")
                print(df.head(10))
            except Exception as e:
                print(f"No se pudo leer la hoja {sheet}: {e}")
                
    except Exception as e:
        print(f"Error al abrir el archivo Excel: {e}")

if __name__ == "__main__":
    analyze_excel()
