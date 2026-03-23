import openpyxl
import sys

def read_excel(file_path):
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet = wb.active
        print(f"--- File: {file_path} ---")
        print(f"Sheet: {sheet.title}")
        for row in sheet.iter_rows(min_row=1, max_row=30, values_only=True):
            print(row)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")

file1 = "docs/assets/samples/España/P-009192 Señaliz. y comunicaciones LAV La Roda-Pobla de Lena/Documentación Proyecto/Desglose del Pliego.xlsx"
file2 = "docs/assets/samples/España/P-009192 Señaliz. y comunicaciones LAV La Roda-Pobla de Lena/Compras/0. Listado Proveedores Homologados/La Robla - Proveedores ofertados.xlsx"

read_excel(file1)
read_excel(file2)
