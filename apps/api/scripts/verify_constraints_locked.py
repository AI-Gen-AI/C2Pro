#!/usr/bin/env python3
"""Verify that apps/api/constraints.txt matches a fresh uv pip compile."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "requirements.txt"
CONSTRAINTS = ROOT / "constraints.txt"

def run_uv_compile():
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    cmd = [
        "uv", "pip", "compile",
        str(REQ),
        "--python-version", "3.11",
        "--python-platform", "x86_64-unknown-linux-gnu",
        "--no-annotate",
        "--no-header",
        "--output-file", str(tmp_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("uv compile failed:", result.stderr, file=sys.stderr)
        sys.exit(1)
    # Verify uv version matches pinned
    ver = subprocess.run(["uv", "--version"], capture_output=True, text=True)
    print(f"UV_VERSION={ver.stdout.strip()}", file=sys.stderr)
    return tmp_path

def main():
    if not CONSTRAINTS.exists():
        print("constraints.txt missing", file=sys.stderr)
        sys.exit(1)
    fresh = run_uv_compile()
    # Byte-for-byte comparison – no normalization
    current_bytes = CONSTRAINTS.read_bytes()
    generated_bytes = fresh.read_bytes()
    if current_bytes == generated_bytes:
        print("constraints.txt is up-to-date")
        sys.exit(0)
    else:
        print("constraints.txt is stale – regenerate with:")
        print("uv pip compile apps/api/requirements.txt --python-version 3.11 --python-platform x86_64-unknown-linux-gnu --no-annotate --no-header --output-file apps/api/constraints.txt")
        sys.exit(1)

if __name__ == "__main__":
    main()
