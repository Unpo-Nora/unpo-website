import pandas as pd
import os

file_path = r"c:\Users\user\.gemini\antigravity\scratch\UNPO_NORA_System\backend\data\Panel_control_UNPO.xlsm"

def analyze_specific():
    xl = pd.ExcelFile(file_path, engine='openpyxl')
    
    sheets = ['MAESTRO PROD', 'LISTA MAYORISTA', 'COSTOS SINIVA']
    for s in sheets:
        if s in xl.sheet_names:
            print(f"\n--- Hoja: {s} ---")
            df = pd.read_excel(file_path, sheet_name=s, nrows=1, engine='openpyxl')
            print("Columnas:", df.columns.tolist())
            # Verificamos si hay una fila de cabecera desplazada
            df2 = pd.read_excel(file_path, sheet_name=s, nrows=5, header=1, engine='openpyxl')
            print("Columnas (con header=1):", df2.columns.tolist())
        else:
            print(f"\nHoja {s} no encontrada")

if __name__ == "__main__":
    analyze_specific()
