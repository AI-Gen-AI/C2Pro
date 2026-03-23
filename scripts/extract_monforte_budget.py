import pandas as pd
import sys

# Target file
file_path = "docs/assets/samples/España/P-009604 LAV Monforte-Murcia/Estudio económico Monforte_Murcia V10.xls"

try:
    print(f"Analyzing: {file_path}")
    # Read the Excel file - using xlrd for .xls if needed, pandas usually auto-detects
    xl = pd.ExcelFile(file_path)
    print(f"Sheet names: {xl.sheet_names}")
    
    # Iterate through specific sheets
    for sheet in ['Formulario']:
        if sheet in xl.sheet_names:
            print(f"\n--- Reading Sheet: {sheet} ---")
            df = pd.read_excel(file_path, sheet_name=sheet)
            # Clean up NaN
            df_clean = df.dropna(how='all')
            # Print rows 40 to 100
            print(df_clean.iloc[40:100].to_string())
            
except Exception as e:
    print(f"Error: {e}")
