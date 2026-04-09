"""Ejecuta los casos de prueba (Golden Tasks) contra los agentes.

Eval-Driven Development: antes de cambiar un prompt de agente,
ejecuta estos tests para detectar Agent Drift.
"""
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML requerido. pip install pyyaml")
    sys.exit(1)

from core.guardrails import validar_blackboard, validar_plan

EVALS_DIR = Path("evals")
BLACKBOARD_PATH = Path("blackboard.json")
RESULTS_PATH = Path("evals/results.json")


def cargar_test_cases() -> list[dict]:
    """Carga los casos de prueba desde test_cases.yaml."""
    yaml_path = EVALS_DIR / "test_cases.yaml"
    if not yaml_path.exists():
        print(f"ERROR: {yaml_path} no encontrado")
        return []
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("test_cases", [])


def ejecutar_eval(test_case: dict, modo_simulacion: bool = True) -> dict:
    """Ejecuta un caso de prueba y devuelve resultado."""
    print(f"\n{'='*60}")
    print(f"EVAL: {test_case['id']} - {test_case['nombre']}")
    print(f"Agente: {test_case['agente_objetivo']}")
    print(f"Prompt: {test_case['prompt'][:100]}...")
    print(f"{'='*60}")

    inicio = time.time()

    if modo_simulacion:
        # En modo simulacion, mostrar el test y pedir evaluacion humana
        print(f"\n[INSTRUCCION PARA EL HUMANO]")
        print(f"1. Abre el CLI de {test_case['agente_objetivo']}")
        print(f"2. Ejecuta: {test_case['prompt']}")
        print(f"3. Verifica los criterios de exito:")
        for i, criterio in enumerate(test_case["criterios_exito"], 1):
            print(f"   {i}. {criterio}")
        print(f"\n4. Ingresa el resultado (pass/fail): ", end="")
        resultado_input = input().strip().lower()
        passed = resultado_input == "pass"
    else:
        # Modo automatico: requiere integracion real con CLIs
        passed = False

    duracion = time.time() - inicio

    return {
        "eval_id": test_case["id"],
        "nombre": test_case["nombre"],
        "agente_objetivo": test_case["agente_objetivo"],
        "passed": passed,
        "duracion_seg": round(duracion, 2),
        "criterios_verificados": len(test_case["criterios_exito"]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def ejecutar_todas_evals(modo_simulacion: bool = True) -> list[dict]:
    """Ejecuta todos los casos de prueba."""
    test_cases = cargar_test_cases()
    if not test_cases:
        print("No hay casos de prueba configurados.")
        return []

    resultados = []
    for tc in test_cases:
        resultado = ejecutar_eval(tc, modo_simulacion)
        resultados.append(resultado)

    # Guardar resultados
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    reporte = {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "total": len(resultados),
        "pasados": sum(1 for r in resultados if r["passed"]),
        "fallidos": sum(1 for r in resultados if not r["passed"]),
        "resultados": resultados,
    }
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)

    # Resumen
    print(f"\n{'='*60}")
    print(f"RESUMEN DE EVALUACION")
    print(f"Total: {reporte['total']} | Pasados: {reporte['pasados']} | Fallidos: {reporte['fallidos']}")
    tasa = (reporte["pasados"] / reporte["total"] * 100) if reporte["total"] > 0 else 0
    print(f"Tasa de exito: {tasa:.1f}%")
    print(f"Resultados guardados en: {RESULTS_PATH}")
    print(f"{'='*60}")

    return resultados


if __name__ == "__main__":
    modo = "simulacion" if "--auto" not in sys.argv else "automatico"
    print(f"Ejecutando evaluaciones en modo: {modo}")
    ejecutar_todas_evals(modo_simulacion=(modo == "simulacion"))
