import pandas as pd
import os

file_path = r"c:\Users\user\.gemini\antigravity\scratch\UNPO_NORA_System\backend\data\Clientes.xlsm"

def analyze_excel():
    if not os.path.exists(file_path):
        print(f"Error: No se encuentra el archivo en {file_path}")
        return

    try:
        xl = pd.ExcelFile(file_path, engine='openpyxl')
        print(f"Hojas encontradas: {xl.sheet_names}")
        
        for sheet in xl.sheet_names:
            print(f"\n--- Analizando hoja: {sheet} ---")
            df = pd.read_excel(file_path, sheet_name=sheet, nrows=5, engine='openpyxl')
            print("Columnas:", df.columns.tolist())
            print("Muestra de datos:")
            print(df.head())
    except Exception as e:
        print(f"Error al leer Excel: {e}")

if __name__ == "__main__":
    analyze_excel()
