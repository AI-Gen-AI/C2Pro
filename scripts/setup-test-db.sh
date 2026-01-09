#!/bin/bash
# Script para inicializar la base de datos de test

set -e

echo "🚀 Iniciando setup de base de datos de test..."

# Verificar si Docker está corriendo
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker no está corriendo"
    exit 1
fi

# Detener contenedor anterior si existe
echo "🧹 Limpiando contenedores anteriores..."
docker-compose -f docker-compose.test.yml down -v 2>/dev/null || true

# Iniciar PostgreSQL
echo "🐘 Iniciando PostgreSQL..."
docker-compose -f docker-compose.test.yml up -d

# Esperar a que PostgreSQL esté listo
echo "⏳ Esperando a que PostgreSQL esté listo..."
until docker-compose -f docker-compose.test.yml exec -T postgres-test pg_isready -U test -d c2pro_test > /dev/null 2>&1; do
    sleep 1
done

echo "✅ PostgreSQL está listo"

# Ejecutar migraciones
echo "📦 Ejecutando migraciones..."
export DATABASE_URL="postgresql://test:test@localhost:5432/c2pro_test"

cd apps/api
python -m pytest --version > /dev/null 2>&1 || pip install -r requirements.txt

cd ../..

# Aplicar migraciones usando SQL directo
echo "🔧 Aplicando migraciones..."
for migration in infrastructure/supabase/migrations/*.sql; do
    if [ -f "$migration" ]; then
        echo "  ➡️  Aplicando $(basename $migration)..."
        docker-compose -f docker-compose.test.yml exec -T postgres-test psql -U test -d c2pro_test < "$migration" || true
    fi
done

echo "✅ Base de datos de test configurada!"
echo ""
echo "📊 Información de conexión:"
echo "  Host:     localhost"
echo "  Port:     5432"
echo "  Database: c2pro_test"
echo "  User:     test"
echo "  Password: test"
echo ""
echo "🧪 Para ejecutar los tests:"
echo "  cd apps/api"
echo "  pytest tests/security/ -v"
echo ""
echo "🛑 Para detener la base de datos:"
echo "  docker-compose -f docker-compose.test.yml down"
