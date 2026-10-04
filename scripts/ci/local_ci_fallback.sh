#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODE="${1:-all}"
CACHE_ROOT="${C2PRO_LOCAL_CI_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/c2pro-local-ci}"
PYTHON_VERSION="${C2PRO_LOCAL_CI_PYTHON:-3.11}"
VENV="$CACHE_ROOT/venv-py$PYTHON_VERSION"
PNPM_BIN="$CACHE_ROOT/bin"
SUMMARY="${GITHUB_STEP_SUMMARY:-$CACHE_ROOT/summary.md}"

usage() {
  cat <<'USAGE'
Usage: scripts/ci/local_ci_fallback.sh [all|backend|frontend|control]

Temporary local fallback for GitHub CI lanes that do not need protected
GitHub environments/secrets. It deliberately does NOT replace P0b,
production synthetic acceptance, CodeQL, or hosted production/security gates.
USAGE
}

case "$MODE" in
  all|backend|frontend|control) ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

mkdir -p "$CACHE_ROOT"
: > "$SUMMARY"

log() { printf '\n==> %s\n' "$*"; }
die() { printf '\nLOCAL_CI_FAIL: %s\n' "$*" >&2; exit 1; }
trap 'printf "\nLOCAL_CI_FAIL: command failed at line %s\n" "$LINENO" >&2' ERR

prepare_backend() {
  command -v uv >/dev/null 2>&1 || die "uv is required on the VPS"
  if [[ ! -x "$VENV/bin/python" ]]; then
    log "Create Python $PYTHON_VERSION CI venv"
    uv venv --python "$PYTHON_VERSION" "$VENV"
  fi

  log "Sync backend dependencies"
  uv pip install --python "$VENV/bin/python" --only-binary=:all:     -r "$ROOT/apps/api/requirements.txt"     -c "$ROOT/apps/api/constraints.txt"
  uv pip install --python "$VENV/bin/python" pip python-magic

  if ! "$VENV/bin/python" -c 'import es_core_news_md' >/dev/null 2>&1; then
    log "Install pinned Presidio spaCy model"
    uv pip install --python "$VENV/bin/python"       "https://github.com/explosion/spacy-models/releases/download/es_core_news_md-3.7.0/es_core_news_md-3.7.0-py3-none-any.whl"
  fi

  export PATH="$VENV/bin:$PATH"
  export GITHUB_STEP_SUMMARY="$SUMMARY"
}

prepare_frontend() {
  command -v corepack >/dev/null 2>&1 || die "corepack is required on the VPS"
  mkdir -p "$PNPM_BIN"
  corepack enable --install-directory "$PNPM_BIN" pnpm >/dev/null
  export PATH="$PNPM_BIN:$PATH"

  log "Sync frontend dependencies"
  cd "$ROOT"
  pnpm install --frozen-lockfile
}

run_control() {
  prepare_backend
  cd "$ROOT"

  log "Development control"
  python -m pytest -q --confcutdir=tests/development     tests/development/test_c2pro_control_plane.py

  log "Product control guard"
  python validation/product/check_control_parity.py
  python validation/product/test_control_parity.py
  python validation/product/test_qualification_evidence.py
  python -m pytest -q     validation/product/test_build_p0b_prod_qualification_bundle_paths.py     validation/product/test_prod_synthetic_workflow_contract.py     validation/product/test_verify_prod_deployment_identity.py
  python validation/product/validate_qualification_evidence.py
}

run_backend() {
  prepare_backend
  cd "$ROOT"

  log "Backend Ruff"
  (cd apps/api && python -m ruff check .)

  log "Backend mypy ratchet"
  (
    cd apps/api
    python -m mypy src --no-error-summary --no-color-output > "$CACHE_ROOT/mypy-report.txt" || true
    python scripts/mypy_ratchet.py --check mypy-baseline.txt < "$CACHE_ROOT/mypy-report.txt"       | tee -a "$SUMMARY"
  )

  log "ADR-009 coherence cache-key guard"
  local matches
  matches="$(grep -rEn 'f"coherence:|f'"'"'coherence:' "$ROOT/apps/api/src/"     --include='*.py'     | grep -v 'src/coherence/cache_keys.py'     | grep -v 'src/coherence/cache_invalidation.py' || true)"
  [[ -z "$matches" ]] || {
    printf '%s\n' "$matches" >&2
    die "ADR-009 cache-key guard failed"
  }

  log "ADR-013 graph contract"
  (cd apps/api && python -m pytest tests/contract/test_graph_node_contracts.py -q --tb=short)

  log "S5 core AI gates"
  (
    cd apps/api
    python -m pytest       tests/modules/stakeholders/domain/test_i10_stakeholder_resolution.py       tests/modules/stakeholders/application/test_i10_ports_contract.py       tests/modules/hitl/domain/test_i11_confidence_gate_routing.py       tests/modules/hitl/application/test_i11_review_queue_service.py       tests/modules/observability/domain/test_i12_trace_envelope_completeness.py       tests/modules/observability/application/test_i12_langsmith_adapter.py       tests/modules/observability/application/test_i12_eval_drift_detection.py       tests/security/test_i10_stakeholder_raci_security_red.py       -q --tb=short
  )

  log "Backend unit suite"
  (
    cd apps/api
    python -m pytest tests/unit/ -m "not integration" -q --tb=short       --cov=src --cov-report=term-missing:skip-covered
  )

  log "Repository root core unit suite"
  python -m pytest tests/unit/core/ --noconftest -q --tb=short
}

run_frontend() {
  prepare_frontend
  cd "$ROOT"
  export NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="pk_test_Y2xlcmsubW9jay5sb2NhbCQ"
  export NEXT_PUBLIC_API_URL="http://localhost:8000"
  export NEXT_PUBLIC_BACKEND_URL="http://localhost:8000"

  log "Frontend typecheck"
  (cd apps/web && pnpm typecheck)

  log "Frontend lint"
  (cd apps/web && pnpm lint)

  log "ADR-009 coherence null->0 guard"
  local matches
  matches="$(grep -rEn '\?\? *0([^.0-9]|$)|\|\| *0([^.0-9]|$)'     apps/web/components/coherence/     apps/web/lib/api/contracts.ts     --include='*.tsx' --include='*.ts'     | grep -v 'weights_used'     | grep -v '\.test\.'     | grep -v 'test-utils' || true)"
  [[ -z "$matches" ]] || {
    printf '%s\n' "$matches" >&2
    die "ADR-009 null->0 guard failed"
  }

  log "Frontend tests"
  (cd apps/web && pnpm test:all)

  log "Frontend coverage"
  (cd apps/web && pnpm test:coverage)

  log "Generated API drift"
  (cd apps/web && pnpm generate:api:check)

  log "Frontend production build"
  (cd apps/web && pnpm build)
}

log "C2Pro temporary local CI fallback"
printf 'HEAD=%s\n' "$(git -C "$ROOT" rev-parse HEAD)"
printf 'MODE=%s\n' "$MODE"

case "$MODE" in
  all)
    run_control
    run_backend
    run_frontend
    ;;
  control) run_control ;;
  backend) run_backend ;;
  frontend) run_frontend ;;
esac

cat <<'EOF'

LOCAL_CI_PASS=YES
NOT_RUN=P0b acceptance, DB-backed integration/migrations, production synthetic acceptance, CodeQL/hosted security gates.
EOF
