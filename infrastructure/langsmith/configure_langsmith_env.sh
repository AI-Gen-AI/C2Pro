#!/usr/bin/env bash
set -euo pipefail

TARGET_ENV="${1:-${ENVIRONMENT:-development}}"
TARGET_ENV="$(echo "$TARGET_ENV" | tr '[:upper:]' '[:lower:]')"

case "$TARGET_ENV" in
  development|dev)
    export LANGCHAIN_API_KEY="${LANGCHAIN_API_KEY_DEV:?Missing LANGCHAIN_API_KEY_DEV}"
    export LANGCHAIN_PROJECT="${LANGCHAIN_PROJECT_DEV:-c2pro-dev}"
    export LANGCHAIN_ENDPOINT="${LANGCHAIN_ENDPOINT_DEV:-https://api.smith.langchain.com}"
    ;;
  staging)
    export LANGCHAIN_API_KEY="${LANGCHAIN_API_KEY_STAGING:?Missing LANGCHAIN_API_KEY_STAGING}"
    export LANGCHAIN_PROJECT="${LANGCHAIN_PROJECT_STAGING:-c2pro-staging}"
    export LANGCHAIN_ENDPOINT="${LANGCHAIN_ENDPOINT_STAGING:-https://api.smith.langchain.com}"
    ;;
  production|prod)
    export LANGCHAIN_API_KEY="${LANGCHAIN_API_KEY_PROD:?Missing LANGCHAIN_API_KEY_PROD}"
    export LANGCHAIN_PROJECT="${LANGCHAIN_PROJECT_PROD:-c2pro-prod}"
    export LANGCHAIN_ENDPOINT="${LANGCHAIN_ENDPOINT_PROD:-https://api.smith.langchain.com}"
    ;;
  *)
    echo "Unsupported environment: $TARGET_ENV" >&2
    exit 1
    ;;
esac

echo "LANGCHAIN_PROJECT=$LANGCHAIN_PROJECT"
echo "LANGCHAIN_ENDPOINT=$LANGCHAIN_ENDPOINT"
