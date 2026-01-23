from __future__ import annotations

from pathlib import Path
import os
import sys


repo_root = Path(__file__).resolve().parents[2]
api_root = repo_root / "apps" / "api"
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
