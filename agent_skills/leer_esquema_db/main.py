"""Skill: leer_esquema_db — Lee esquemas desde modelos SQLAlchemy y migraciones."""
import json
import sys
from pathlib import Path
import re


def leer_esquema(modulo: str) -> dict:
    """Extrae informacion de tablas desde archivos de modelo y migraciones."""
    base = Path("apps/api/src")
    resultados = {"tablas": []}

    # Buscar modelos del modulo
    modulo_path = base / "modules" / modulo
    if modulo_path.exists():
        for py_file in modulo_path.rglob("*.py"):
            if "model" in py_file.name.lower() or py_file.name == "models.py":
                tablas = _extraer_de_modelo(py_file)
                resultados["tablas"].extend(tablas)

    # Buscar migraciones del modulo
    migrations = Path("supabase/migrations")
    if migrations.exists():
        for sql_file in sorted(migrations.glob("*.sql")):
            if modulo.lower() in sql_file.read_text(encoding="utf-8", errors="ignore").lower():
                tablas = _extraer_de_migracion(sql_file)
                resultados["tablas"].extend(tablas)

    return resultados


def _extraer_de_modelo(filepath: Path) -> list[dict]:
    """Extrae nombres de tablas y columnas de modelos SQLAlchemy."""
    tablas = []
    try:
        content = filepath.read_text(encoding="utf-8")
        # Buscar clases que hereden de Base
        class_pattern = re.compile(r"class\s+(\w+)\(.*Base.*\):")
        col_pattern = re.compile(r"Column\(['\"](\w+)['\"]")

        for match in class_pattern.finditer(content):
            clase = match.group(1)
            start = match.end()
            # Buscar siguiente clase o fin del archivo
            next_match = class_pattern.search(content, start)
            end = next_match.start() if next_match else len(content)
            bloque = content[start:end]

            columnas = [m.group(1) for m in col_pattern.finditer(bloque)]
            tablas.append({"nombre": clase, "columnas": columnas})
    except Exception:
        pass
    return tablas


def _extraer_de_migracion(filepath: Path) -> list[dict]:
    """Extrae nombres de tablas desde archivos SQL de migracion."""
    tablas = []
    try:
        content = filepath.read_text(encoding="utf-8")
        create_pattern = re.compile(r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)\s*\((.*?)\);", re.DOTALL)

        for match in create_pattern.finditer(content):
            nombre = match.group(1)
            columnas_raw = match.group(2)
            columnas = []
            for linea in columnas.split("\n"):
                linea = linea.strip().rstrip(",")
                if linea and not linea.startswith(("--", "PRIMARY", "FOREIGN", "CONSTRAINT", "UNIQUE")):
                    col_name = linea.split()[0].strip('"')
                    if col_name:
                        columnas.append(col_name)
            tablas.append({"nombre": nombre, "columnas": columnas})
    except Exception:
        pass
    return tablas


if __name__ == "__main__":
    modulo = sys.argv[1] if len(sys.argv) > 1 else "documents"
    resultado = leer_esquema(modulo)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
