import fitz  # PyMuPDF
import docx
import os

def leer_pdf(ruta_pdf):
    texto = ""
    try:
        with fitz.open(ruta_pdf) as doc:
            for pagina in doc:
                texto += pagina.get_text()
    except Exception as e:
        print(f"Error leyendo PDF: {e}")
    return texto.strip()

def leer_docx(ruta_docx):
    texto = ""
    try:
        doc = docx.Document(ruta_docx)
        for parrafo in doc.paragraphs:
            texto += parrafo.text + "\n"
    except Exception as e:
        print(f"Error leyendo DOCX: {e}")
    return texto.strip()

def leer_contrato(ruta_archivo):
    if ruta_archivo.endswith(".pdf"):
        return leer_pdf(ruta_archivo)
    elif ruta_archivo.endswith(".docx"):
        return leer_docx(ruta_archivo)
    else:
        raise ValueError("Formato de archivo no soportado. Usa .pdf o .docx")

# Test rápido
if __name__ == "__main__":
    archivo = "../data_samples/contracts/ejemplo_contrato.pdf"  # Ajusta si es necesario
    texto = leer_contrato(archivo)
    print("Primeras 500 palabras del contrato:\n")
    print(texto[:1000])

