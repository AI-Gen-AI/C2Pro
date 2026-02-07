"""
C2Pro API - Development Server

Script para ejecutar el servidor de desarrollo con hot-reload.
"""

import sys
from pathlib import Path


def main():
    """Run development server."""
    # Add src to Python path
    src_path = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_path))

    # Check if .env exists
    env_file = Path(__file__).parent.parent.parent / ".env"
    if not env_file.exists():
        print("[ERROR] No se encontro el archivo .env")
        print("Por favor ejecuta 'python setup.py' primero")
        sys.exit(1)

    # Run uvicorn
    import uvicorn

    print(">> Iniciando servidor de desarrollo...")
    print(">> Docs disponibles en: http://localhost:8000/docs")
    print(">> Hot-reload activado")
    print("\nPresiona Ctrl+C para detener\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
