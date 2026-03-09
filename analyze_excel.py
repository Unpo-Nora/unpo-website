import pandas as pd
import os

data_dir = "backend/data"
files_in_dir = os.listdir(data_dir)
print(f"Archivos en {data_dir}: {files_in_dir}")

for filename in files_in_dir:
    file_path = os.path.join(data_dir, filename)
    print(f"\n--- Analizando: {file_path} ---")
    try:
        header_idx = 2 if "Clientes" in filename else 0
        df = pd.read_excel(file_path, header=header_idx, nrows=10)
        print("Columnas encontradas:")
        print(df.columns.tolist())
        print("\nMuestra de datos:")
        print(df.head())
    except Exception as e:
        print(f"Error al leer {file_path}: {e}")
