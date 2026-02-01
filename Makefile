# ===========================================
# C2PRO - Makefile
# ===========================================
# 
# Uso:
#   make help        # Ver comandos disponibles
#   make setup       # Setup inicial completo
#   make dev         # Iniciar desarrollo
#   make test        # Ejecutar todos los tests

.PHONY: help setup dev test clean

# Default
.DEFAULT_GOAL := help

# Colors
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

# ===========================================
# HELP
# ===========================================
help: ## Mostrar esta ayuda
	@echo ""
	openapi: ## Generar OpenAPI YAML desde runtime
	@echo "$(CYAN)📜 Generando OpenAPI...$(RESET)"
	@python apps/api/scripts/generate_openapi.py
	@echo "$(CYAN)C2PRO - Comandos disponibles$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ===========================================
# SETUP
# ===========================================
setup: ## Setup inicial completo (Supabase)
	@echo "$(CYAN)🚀 Configurando C2PRO...$(RESET)"
	@make setup-env
	@make setup-backend-supabase
	@echo "$(GREEN)✅ Setup completado!$(RESET)"
	@echo ""
	@echo "$(YELLOW)Próximos pasos:$(RESET)"
	@echo "  1. Configura DATABASE_URL en .env con tu password de Supabase"
	@echo "  2. Ejecuta: make backend-init"
	@echo "  3. Ejecuta: make backend-dev"

setup-local: ## Setup con Docker local
	@echo "$(CYAN)🚀 Configurando C2PRO (Docker)...$(RESET)"
	@make setup-env
	@make setup-backend
	@make setup-frontend
	@make setup-infra
	@echo "$(GREEN)✅ Setup completado!$(RESET)"

setup-env: ## Crear archivo .env desde ejemplo
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(YELLOW)⚠️  Archivo .env creado. Edita con tus credenciales.$(RESET)"; \
	else \
		echo "$(GREEN)✓ Archivo .env ya existe$(RESET)"; \
	fi

setup-backend: ## Instalar dependencias del backend (Docker)
	@echo "$(CYAN)📦 Instalando dependencias del backend...$(RESET)"
	cd apps/api && python -m venv .venv
	cd apps/api && . .venv/bin/activate && pip install -r requirements.txt

setup-backend-supabase: ## Instalar dependencias (Supabase cloud)
	@echo "$(CYAN)📦 Instalando dependencias del backend...$(RESET)"
	cd apps/api && pip install -r requirements.txt
	@echo "$(GREEN)✅ Dependencias instaladas$(RESET)"

setup-frontend: ## Instalar dependencias del frontend
	@echo "$(CYAN)📦 Instalando dependencias del frontend...$(RESET)"
	cd apps/web && npm install

setup-infra: ## Iniciar servicios de infraestructura
	@echo "$(CYAN)🐳 Iniciando servicios Docker...$(RESET)"
	docker-compose up -d postgres redis minio minio-setup
	@echo "$(CYAN)⏳ Esperando a que los servicios estén listos...$(RESET)"
	@sleep 5
	@echo "$(GREEN)✓ Servicios iniciados$(RESET)"

# ===========================================
# DEVELOPMENT
# ===========================================
dev: ## Iniciar entorno de desarrollo (Docker local)
	@echo "$(CYAN)🚀 Iniciando desarrollo...$(RESET)"
	@make dev-infra
	@echo ""
	@echo "$(GREEN)Servicios listos:$(RESET)"
	@echo "  - PostgreSQL: localhost:5432"
	@echo "  - Redis: localhost:6379"
	@echo "  - MinIO: localhost:9000 (console: localhost:9001)"
	@echo ""
	@echo "$(YELLOW)Inicia backend y frontend en terminales separadas:$(RESET)"
	@echo "  Terminal 1: make dev-api"
	@echo "  Terminal 2: make dev-web"

backend-init: ## Inicializar backend (setup + migraciones)
	@echo "$(CYAN)🔧 Inicializando backend...$(RESET)"
	cd apps/api && python setup.py

backend-dev: ## Iniciar backend en desarrollo (Supabase)
	@echo "$(CYAN)🚀 Iniciando backend...$(RESET)"
	cd apps/api && python dev.py

dev-infra: ## Iniciar solo infraestructura
	docker-compose up -d postgres redis minio

dev-api: ## Iniciar backend en modo desarrollo
	cd apps/api && . venv/bin/activate && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-web: ## Iniciar frontend en modo desarrollo
	cd apps/web && npm run dev

# ===========================================
# DATABASE (Supabase Cloud)
# ===========================================
db-migrate: ## Aplicar migraciones
	cd apps/api && python migrate.py upgrade

db-migrate-create: ## Crear nueva migración (uso: make db-migrate-create MSG="descripcion")
	cd apps/api && python migrate.py create "$(MSG)"

db-migrate-status: ## Ver estado de migraciones
	cd apps/api && python migrate.py current

db-migrate-history: ## Ver historial de migraciones
	cd apps/api && python migrate.py history

db-reset: ## Resetear base de datos (⚠️ destruye datos)
	docker-compose down -v postgres
	docker-compose up -d postgres
	@sleep 3
	@make db-migrate

db-shell: ## Abrir shell de PostgreSQL
	docker-compose exec postgres psql -U postgres -d c2pro

# ===========================================
# TESTING
# ===========================================
test: ## Ejecutar todos los tests
	@make test-api
	@make test-web

test-api: ## Tests del backend
	cd apps/api && . venv/bin/activate && pytest -v

test-api-cov: ## Tests del backend con coverage
	cd apps/api && . venv/bin/activate && pytest --cov=src --cov-report=html --cov-report=term

test-web: ## Tests del frontend
	cd apps/web && npm test

test-e2e: ## Tests end-to-end
	cd apps/web && npm run test:e2e

# ===========================================
# LINTING & FORMATTING
# ===========================================
lint: ## Ejecutar linters
	@make lint-api
	@make lint-web

lint-api: ## Lint del backend
	cd apps/api && . venv/bin/activate && ruff check src tests

lint-web: ## Lint del frontend
	cd apps/web && npm run lint

format: ## Formatear código
	@make format-api
	@make format-web

format-api: ## Formatear backend
	cd apps/api && . venv/bin/activate && ruff format src tests

format-web: ## Formatear frontend
	cd apps/web && npm run format

typecheck: ## Verificar tipos
	cd apps/api && . venv/bin/activate && mypy src
	cd apps/web && npm run typecheck

# ===========================================
# BUILD
# ===========================================
build: ## Construir para producción
	@make build-api
	@make build-web

build-api: ## Build del backend
	cd apps/api && docker build -t c2pro-api .

build-web: ## Build del frontend
	cd apps/web && npm run build

# ===========================================
# CLEANUP
# ===========================================
clean: ## Limpiar archivos temporales
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

clean-docker: ## Limpiar contenedores y volúmenes Docker
	docker-compose down -v --remove-orphans
	docker system prune -f

# ===========================================
# UTILITIES
# ===========================================
logs: ## Ver logs de todos los servicios
	docker-compose logs -f

logs-api: ## Ver logs del backend
	docker-compose logs -f api

shell-api: ## Shell en contenedor del backend
	docker-compose exec api /bin/sh

redis-cli: ## Cliente de Redis
	docker-compose exec redis redis-cli

check-health: ## Verificar salud de servicios
	@echo "$(CYAN)Verificando servicios...$(RESET)"
	@curl -s http://localhost:8000/health | jq . || echo "❌ API no disponible"
	@curl -s http://localhost:3000 > /dev/null && echo "✅ Frontend OK" || echo "❌ Frontend no disponible"
	@docker-compose exec postgres pg_isready -U postgres > /dev/null && echo "✅ PostgreSQL OK" || echo "❌ PostgreSQL no disponible"
	@docker-compose exec redis redis-cli ping > /dev/null && echo "✅ Redis OK" || echo "❌ Redis no disponible"
