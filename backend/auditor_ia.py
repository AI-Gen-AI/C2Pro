import os
import openai
from dotenv import load_dotenv
from parser_contrato import leer_contrato

# Cargar clave desde .env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Prompt estructurado
PROMPT_BASE = """
Actúa como un auditor inteligente especializado en contratos de obra, suministro o servicios.

A continuación, recibirás un fragmento de un contrato técnico o pliego de condiciones. Tu tarea es extraer de forma estructurada la siguiente información, si aparece:

1. Fechas clave (de entrega, firma, ejecución, penalizaciones).
2. Hitos críticos o etapas importantes del proyecto.
3. Condiciones de entrega (materiales, documentación, ubicaciones, restricciones).
4. Penalizaciones explícitas (por retrasos, incumplimientos, falta de calidad, etc.).
5. Garantías (tiempos, condiciones, penalizaciones asociadas).

Devuelve la información en formato JSON con esta estructura:

{
  "fechas_clave": [ {"evento": "...", "fecha": "..."} ],
  "hitos": [ {"descripcion": "...", "fecha_limite": "..."} ],
  "condiciones_entrega": [ "..." ],
  "penalizaciones": [ {"motivo": "...", "importe": "...", "condicion": "..."} ],
  "garantias": [ {"descripcion": "...", "duracion": "...", "condicion": "..."} ]
}

No incluyas ningún comentario ni explicación adicional fuera del JSON. Solo responde con el JSON.

Texto del contrato:
===
{texto_contrato}
===
"""

def analizar_contrato_con_ia(ruta_contrato):
    texto = leer_contrato(ruta_contrato)

    prompt = PROMPT_BASE.replace("{texto_contrato}", texto[:4000])  # Recorta si es muy largo

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Eres un experto legal y auditor de contratos técnicos."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    resultado = response['choices'][0]['message']['content']
    return resultado

# Test rápido
if __name__ == "__main__":
    ruta = "../data_samples/contracts/ejemplo_contrato.pdf"  # Cambia según tu archivo
    salida = analizar_contrato_con_ia(ruta)
    print("\nJSON devuelto por la IA:\n")
    print(salida)
