"""
C2Pro API - Database Migration Helper

Script para gestionar migraciones de base de datos.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str):
    """Run a command and handle errors."""
    print(f"\n🔄 {description}...")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("❌ ERROR:")
        print(result.stderr)
        return False

    print(result.stdout)
    print(f"✅ {description} completado")
    return True


def show_help():
    """Show help message."""
    print("""
C2Pro - Database Migration Helper

Uso:
  python migrate.py <comando>

Comandos:
  upgrade       Aplica todas las migraciones pendientes
  downgrade     Revierte la última migración
  current       Muestra la migración actual
  history       Muestra el historial de migraciones
  create        Crea una nueva migración automáticamente
  help          Muestra esta ayuda

Ejemplos:
  python migrate.py upgrade
  python migrate.py create "add users table"
  python migrate.py history
""")


def main():
    """Main function."""
    # Change to API directory
    api_dir = Path(__file__).parent
    os.chdir(api_dir)

    # Check arguments
    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1].lower()

    if command == "help":
        show_help()
        return

    elif command == "upgrade":
        run_command(["alembic", "upgrade", "head"], "Aplicando migraciones")

    elif command == "downgrade":
        confirm = input("⚠️  ¿Estás seguro de revertir la última migración? (s/n): ")
        if confirm.lower() == "s":
            run_command(["alembic", "downgrade", "-1"], "Revirtiendo migración")

    elif command == "current":
        run_command(["alembic", "current"], "Verificando migración actual")

    elif command == "history":
        run_command(["alembic", "history", "--verbose"], "Obteniendo historial de migraciones")

    elif command == "create":
        if len(sys.argv) < 3:
            print("❌ ERROR: Se requiere un mensaje para la migración")
            print('Ejemplo: python migrate.py create "add users table"')
            return

        message = " ".join(sys.argv[2:])
        run_command(
            ["alembic", "revision", "--autogenerate", "-m", message],
            f"Creando migración: {message}",
        )

    else:
        print(f"❌ Comando desconocido: {command}")
        show_help()


if __name__ == "__main__":
    main()
