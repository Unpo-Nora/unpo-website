import pandas as pd
import json
import os

excel_path = '/app/data/Panel_control_UNPO.xlsm'
xl = pd.ExcelFile(excel_path, engine='openpyxl')
info = {}

for sheet in xl.sheet_names:
    try:
        # Intentamos con header=3 (fila 4)
        df = pd.read_excel(xl, sheet, header=3, nrows=2)
        info[sheet] = [str(c).strip() for c in df.columns]
    except:
        info[sheet] = "ERROR"

print(json.dumps(info, indent=2))
