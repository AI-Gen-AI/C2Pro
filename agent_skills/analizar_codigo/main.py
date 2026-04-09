"""Skill: analizar_codigo — Lee y analiza archivos de un directorio."""
import os
import json
import sys
from pathlib import Path


def analizar_directorio(directorio: str, profundidad: int = 2) -> dict:
    """Analiza un directorio y devuelve estructura de archivos con imports."""
    base = Path(directorio)
    if not base.exists():
        return {"error": f"Directorio no encontrado: {directorio}"}

    resultados = []
    _recursivo(base, profundidad, resultados)
    return {"archivos": resultados}


def _recursivo(path: Path, profundidad: int, resultados: list, nivel: int = 0):
    if nivel > profundidad:
        return
    for item in sorted(path.iterdir()):
        if item.name.startswith((".", "__")) or item.name == "node_modules":
            continue
        if item.is_file():
            info = {
                "path": str(item),
                "size_bytes": item.stat().st_size,
                "imports": _extraer_imports(item) if item.suffix in (".py", ".ts", ".tsx", ".js") else [],
            }
            resultados.append(info)
        elif item.is_dir():
            _recursivo(item, profundidad, resultados, nivel + 1)


def _extraer_imports(filepath: Path) -> list[str]:
    imports = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                imports.append(stripped)
            if len(imports) > 50:
                break
    except Exception:
        pass
    return imports


if __name__ == "__main__":
    directorio = sys.argv[1] if len(sys.argv) > 1 else "."
    profundidad = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    resultado = analizar_directorio(directorio, profundidad)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
