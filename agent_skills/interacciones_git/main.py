"""Skill: interacciones_git — Ejecuta comandos git de forma segura."""
import subprocess
import json
import sys


COMANDOS_PERMITIDOS = {
    "status": ["git", "status", "--short"],
    "diff": ["git", "diff", "--stat"],
}

COMANDOS_PROHIBIDOS = {"push --force", "reset --hard", "push -f"}


def ejecutar_git(accion: str, mensaje: str | None = None, archivos: list[str] | None = None) -> dict:
    """Ejecuta un comando git permitido y devuelve resultado."""
    if accion == "commit":
        if not mensaje:
            return {"success": False, "output": "Error: mensaje de commit requerido"}
        files = archivos or ["."]
        try:
            subprocess.run(["git", "add"] + files, check=True, capture_output=True, text=True)
            result = subprocess.run(
                ["git", "commit", "-m", mensaje],
                check=True, capture_output=True, text=True
            )
            return {"success": True, "output": result.stdout}
        except subprocess.CalledProcessError as e:
            return {"success": False, "output": e.stderr}

    if accion == "push":
        try:
            result = subprocess.run(
                ["git", "push"],
                check=True, capture_output=True, text=True
            )
            return {"success": True, "output": result.stdout}
        except subprocess.CalledProcessError as e:
            return {"success": False, "output": e.stderr}

    if accion in COMANDOS_PERMITIDOS:
        try:
            result = subprocess.run(
                COMANDOS_PERMITIDOS[accion],
                check=True, capture_output=True, text=True
            )
            return {"success": True, "output": result.stdout}
        except subprocess.CalledProcessError as e:
            return {"success": False, "output": e.stderr}

    return {"success": False, "output": f"Accion no soportada: {accion}"}


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else "status"
    mensaje = sys.argv[2] if len(sys.argv) > 2 else None
    resultado = ejecutar_git(accion, mensaje)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
