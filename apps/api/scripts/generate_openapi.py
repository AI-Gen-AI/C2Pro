"""
Generate OpenAPI YAML from the FastAPI app.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _ensure_env_defaults() -> None:
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault(
        "DATABASE_URL", "postgresql://nonsuperuser:test@localhost:5433/c2pro_test"
    )
    os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
    os.environ.setdefault("SUPABASE_ANON_KEY", "test")
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test")
    os.environ.setdefault(
        "JWT_SECRET_KEY", "test-secret-key-min-32-chars-required-for-testing-purposes-only"
    )
    os.environ.setdefault("JWT_ALGORITHM", "HS256")


def main() -> None:
    project_root = Path(__file__).resolve().parents[3]
    api_root = project_root / "apps" / "api"
    sys.path.insert(0, str(api_root))

    _ensure_env_defaults()

    try:
        import yaml
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("PyYAML is required to generate OpenAPI YAML.") from exc

    from src.main import create_application

    app = create_application()
    openapi = app.openapi()

    out_path = project_root / "docs" / "api" / "openapi.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_output = yaml.safe_dump(openapi, sort_keys=False, allow_unicode=False)
    print(yaml_output)
    try:
        out_path.write_text(yaml_output, encoding="utf-8")
    except PermissionError:
        print(f"skipped write {out_path} (permission denied)")
    else:
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
