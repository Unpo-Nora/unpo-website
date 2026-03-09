import pandas as pd
import os

def debug_sync():
    data_dir = "backend/data"
    csv_mayorista = os.path.join(data_dir, 'MAYORISTA.csv')
    csv_catalogo = os.path.join(data_dir, 'CATALOGO.csv')

    def normalize_sku(val):
        if pd.isna(val) or str(val).strip() == '': return None
        val = str(val).strip()
        if '.' in val: val = val.split('.')[0]
        try:
            if val.isdigit():
                return str(int(val))
        except:
            pass
        return val

    df_may = pd.read_csv(csv_mayorista, header=3, dtype=str)
    df_cat = pd.read_csv(csv_catalogo, dtype=str)

    df_may['sku_norm'] = df_may.iloc[:, 0].apply(normalize_sku)
    df_cat['sku_norm'] = df_cat.iloc[:, 0].apply(normalize_sku)

    print(f"MAYORISTA samples: {df_may['sku_norm'].head(5).tolist()}")
    print(f"CATALOGO samples: {df_cat['sku_norm'].head(5).tolist()}")

    matches = 0
    missing = []
    for sku in df_may['sku_norm'].unique():
        if sku and sku != 'nan':
            if sku in df_cat['sku_norm'].values:
                matches += 1
            else:
                missing.append(sku)

    print(f"Total Unique SKUs in MAYORISTA: {len(df_may['sku_norm'].unique())}")
    print(f"Matches found in CATALOGO: {matches}")
    print(f"Missing SKUs sample: {missing[:10]}")

    # Check a specific one
    test_sku = "10300028"
    if test_sku in df_cat['sku_norm'].values:
        info = df_cat[df_cat['sku_norm'] == test_sku].iloc[0]
        print(f"SKU {test_sku} full info ({len(info)} cols):")
        for i, val in enumerate(info):
            print(f"  Col {i}: [{val}]")
    else:
        print(f"SKU {test_sku} NOT found in CATALOGO")

if __name__ == "__main__":
    debug_sync()
