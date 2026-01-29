#!/bin/bash
# C2Pro - Backend Initialization Script (Linux/Mac)
# Este script configura e inicia el backend automáticamente

set -e  # Exit on error

echo "================================"
echo "C2Pro - Backend Setup"
echo "================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "[ERROR] No se encontró el archivo .env"
    echo ""
    echo "Por favor copia .env.example a .env y configura las variables:"
    echo "  1. DATABASE_URL"
    echo "  2. SUPABASE_URL"
    echo "  3. SUPABASE_ANON_KEY"
    echo "  4. SUPABASE_SERVICE_ROLE_KEY"
    echo ""
    exit 1
fi

echo "[1/4] Verificando Python..."
python3 --version || {
    echo "[ERROR] Python 3 no está instalado"
    exit 1
}

echo ""
echo "[2/4] Navegando al directorio de la API..."
cd apps/api

echo ""
echo "[3/4] Ejecutando setup..."
python3 setup.py || {
    echo ""
    echo "[ERROR] Setup fallido. Revisa los errores anteriores."
    exit 1
}

echo ""
echo "[4/4] Iniciando servidor de desarrollo..."
echo ""
echo "================================"
echo "Backend listo!"
echo "================================"
echo ""
echo "Accede a la API en:"
echo "  - API: http://localhost:8000"
echo "  - Docs: http://localhost:8000/docs"
echo ""
echo "Presiona Ctrl+C para detener el servidor"
echo ""

python3 dev.py
