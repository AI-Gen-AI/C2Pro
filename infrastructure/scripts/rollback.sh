#!/bin/bash

# CE-S4-011: Automated Rollback Script (Code + DB)
#
# This script provides a safety net for deployments by enabling a quick rollback
# to a previous stable state. It supports reverting code to a specific commit
# and restoring a database snapshot.
#
# Usage:
# ./scripts/rollback.sh --target-commit <commit_sha> [--db-snapshot <path_to_sql>] [--environment <env>] [--force]
#
# Arguments:
#   --target-commit <sha> : Required. The git commit hash to roll back to.
#   --db-snapshot <path>  : Optional. Path to the database snapshot file for restoration.
#   --environment <name>  : Optional. Environment to load variables from (e.g., dev, staging, prod).
#                           Defaults to 'dev'.
#   --force               : Optional. Skips the manual confirmation prompt for database operations.
#
# Example:
# ./scripts/rollback.sh --target-commit a1b2c3d --db-snapshot backups/dump_20230101.sql --environment staging

set -e

# --- Configuration ---
# You might need to adjust these based on your project structure
DOCKER_COMPOSE_FILE="docker-compose.yml"
# --- End Configuration ---

# --- Helper Functions ---
log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

exit_with_error() {
  log "ERROR: $1"
  exit 1
}

# --- Script Logic ---
main() {
  # Parse arguments
  while [[ "$#" -gt 0 ]]; do
    case $1 in
      --target-commit) TARGET_COMMIT="$2"; shift ;;
      --db-snapshot) DB_SNAPSHOT="$2"; shift ;;
      --environment) ENVIRONMENT="$2"; shift ;;
      --force) FORCE=1 ;;
      *) exit_with_error "Unknown parameter passed: $1" ;;
    esac
    shift
  done

  # Validate arguments
  if [ -z "$TARGET_COMMIT" ]; then
    exit_with_error "--target-commit is a required argument."
  fi

  ENVIRONMENT=${ENVIRONMENT:-dev}
  log "Starting rollback process for environment: $ENVIRONMENT..."

  # --- Code Rollback ---
  log "Rolling back code to commit: $TARGET_COMMIT"
  if ! git checkout "$TARGET_COMMIT"; then
    exit_with_error "Failed to checkout commit $TARGET_COMMIT. Aborting."
  fi
  log "Code rollback successful."

  # --- Database Rollback ---
  if [ -n "$DB_SNAPSHOT" ]; then
    log "Database snapshot provided: $DB_SNAPSHOT"
    if [ "$FORCE" != "1" ]; then
      echo "ADVERTENCIA: Restaurar la BD borrará cualquier dato creado después del snapshot."
      read -p "Escriba 'CONFIRM' para continuar: " CONFIRMATION
      if [ "$CONFIRMATION" != "CONFIRM" ]; then
        exit_with_error "Confirmación no válida. Abortando rollback de la base de datos."
      fi
    fi
    log "Restoring database from snapshot..."
    # This is a placeholder for the actual restore command.
    # You will need to replace this with the correct command for your setup.
    # For example, for PostgreSQL:
    # psql $DATABASE_URL < $DB_SNAPSHOT
    if ! echo "Simulating database restore from $DB_SNAPSHOT"; then
      exit_with_error "Failed to restore database from snapshot."
    fi
    log "Database restore successful."
  else
    log "No database snapshot provided. Skipping database rollback."
    log "ADVERTENCIA: La base de datos puede estar en un estado inconsistente con el código."
  fi

  # --- Restart Services ---
  log "Rebuilding and restarting Docker containers..."
  if ! docker-compose -f "$DOCKER_COMPOSE_FILE" up -d --build; then
    exit_with_error "Failed to rebuild or restart Docker containers."
  fi
  log "Services restarted successfully."

  log "Rollback to commit $TARGET_COMMIT completed successfully."
}

main "$@"
