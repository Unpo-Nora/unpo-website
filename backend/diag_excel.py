import pandas as pd
import json
import os

excel_path = '/app/data/Panel_control_UNPO.xlsm'

if not os.path.exists(excel_path):
    print(f"Error: {excel_path} not found")
    exit(1)

xl = pd.ExcelFile(excel_path, engine='openpyxl')
info = {}

for sheet in xl.sheet_names:
    df = pd.read_excel(xl, sheet, nrows=5)
    info[sheet] = {
        "columns": [str(c).strip() for c in df.columns],
        "first_row": df.iloc[0].to_dict() if not df.empty else {}
    }

with open('/app/excel_diag.json', 'w') as f:
    json.dump(info, f, indent=2, default=str)

print("Diagnostics written to /app/excel_diag.json")
