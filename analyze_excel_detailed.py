
import pandas as pd
import sys

file_path = "docs/assets/samples/España/P-009245  Planta Bionergía de Campillos Málaga/Documentación proyecto/Presupuesto cero/20150128 RD/Presupuesto cero.xlsx"

try:
    # Read the Excel file
    # Trying to read all sheets to find the relevant one
    xl = pd.ExcelFile(file_path)
    print(f"Sheet names: {xl.sheet_names}")
    
    for sheet in xl.sheet_names:
        print(f"\n--- Sheet: {sheet} ---")
        df = pd.read_excel(file_path, sheet_name=sheet)
        print(df.head(20).to_string())
        # Calculate totals if possible
        # Look for columns that might contain values like 'Total', 'Precio', 'Importe'
        # This is a heuristic approach
        
except Exception as e:
    print(f"Error reading excel file: {e}")
