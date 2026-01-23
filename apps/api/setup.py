"""
C2Pro API - Setup Script

Script de inicialización para configurar el backend.
"""

import os
import subprocess
import sys
from pathlib import Path


def print_header(message: str):
    """Print formatted header."""
    print("\n" + "=" * 60)
    print(f"  {message}")
    print("=" * 60 + "\n")


def check_python_version():
    """Verify Python version."""
    print_header("Verificando versión de Python")

    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print("[ERROR] Se requiere Python 3.11 o superior")
        sys.exit(1)

    print("[OK] Version de Python correcta")


def check_env_file():
    """Check if .env file exists."""
    print_header("Verificando archivo .env")

    env_file = Path(__file__).parent.parent.parent / ".env"

    if not env_file.exists():
        print("[ERROR] No se encontro el archivo .env")
        print("Por favor copia .env.example a .env y configura las variables")
        sys.exit(1)

    print("[OK] Archivo .env encontrado")

    # Check critical variables
    with open(env_file) as f:
        content = f.read()

        critical_vars = ["DATABASE_URL", "SUPABASE_URL", "SUPABASE_ANON_KEY", "JWT_SECRET_KEY"]

        missing = []
        for var in critical_vars:
            if f"{var}=" not in content or f"{var}=your" in content or f"{var}=YOUR" in content:
                missing.append(var)

        if missing:
            print("[ADVERTENCIA] Las siguientes variables necesitan ser configuradas:")
            for var in missing:
                print(f"   - {var}")

            response = input("\n¿Continuar de todas formas? (s/n): ")
            if response.lower() != "s":
                sys.exit(1)


def install_dependencies():
    """Install Python dependencies."""
    print_header("Instalando dependencias")

    # Use Sprint 1 requirements (minimal dependencies)
    requirements_file = Path(__file__).parent / "requirements-sprint1.txt"

    if not requirements_file.exists():
        print("[ERROR] No se encontro requirements-sprint1.txt")
        print("Intentando con requirements.txt...")
        requirements_file = Path(__file__).parent / "requirements.txt"
        if not requirements_file.exists():
            print("[ERROR] No se encontro requirements.txt")
            sys.exit(1)

    print(f"Instalando paquetes de Python desde {requirements_file.name}...")

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("[ERROR] Error al instalar dependencias:")
        print(result.stderr)
        sys.exit(1)

    print("[OK] Dependencias instaladas correctamente")


def run_migrations():
    """Run database migrations."""
    print_header("Ejecutando migraciones de base de datos")

    print("Aplicando migraciones con Alembic...")

    # Change to api directory
    api_dir = Path(__file__).parent
    os.chdir(api_dir)

    result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)

    if result.returncode != 0:
        print("[ERROR] Error al ejecutar migraciones:")
        print(result.stderr)
        print("\nPosibles causas:")
        print("1. DATABASE_URL no está configurada correctamente")
        print("2. No hay conexión a la base de datos")
        print("3. Las credenciales de Supabase son incorrectas")
        sys.exit(1)

    print("[OK] Migraciones aplicadas correctamente")
    print(result.stdout)


def create_storage_directory():
    """Create local storage directory."""
    print_header("Creando directorio de almacenamiento local")

    storage_dir = Path(__file__).parent / "storage"
    storage_dir.mkdir(exist_ok=True)

    print(f"[OK] Directorio creado: {storage_dir}")


def print_success():
    """Print success message."""
    print_header("¡Setup completado!")

    print("[OK] El backend esta listo para ejecutarse")
    print("\nPara iniciar el servidor de desarrollo:")
    print("  cd apps/api")
    print("  python dev.py")
    print("\nO usando uvicorn directamente:")
    print("  uvicorn src.main:app --reload")
    print("\nAccede a la documentación en:")
    print("  http://localhost:8000/docs")
    print()


def main():
    """Main setup function."""
    try:
        check_python_version()
        check_env_file()
        install_dependencies()
        create_storage_directory()
        run_migrations()
        print_success()

    except KeyboardInterrupt:
        print("\n\n[CANCELADO] Setup cancelado por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
