#!/usr/bin/env python3
"""Verify that apps/api/constraints.txt matches a fresh uv pip compile."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "requirements.txt"
CONSTRAINTS = ROOT / "constraints.txt"

def run_uv_compile():
    # uv pip compile writes to stdout when -o is not used? Use output file.
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    cmd = [
        "uv", "pip", "compile",
        str(REQ),
        "--python-version", "3.11",
        "--python-platform", "linux",
        "--output-file", str(tmp_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("uv compile failed:", result.stderr, file=sys.stderr)
        sys.exit(1)
    return tmp_path

def normalize(content: str) -> str:
    lines = []
    for line in content.splitlines():
        if line.startswith("#"):
            continue
        # keep blank lines for readability but they don't matter
        lines.append(line.strip())
    # remove empty
    lines = [l for l in lines if l]
    return "\n".join(lines)

def main():
    if not CONSTRAINTS.exists():
        print("constraints.txt missing", file=sys.stderr)
        sys.exit(1)
    fresh = run_uv_compile()
    current_norm = normalize(CONSTRAINTS.read_text())
    generated_norm = normalize(fresh.read_text())
    if current_norm == generated_norm:
        print("constraints.txt is up-to-date")
        sys.exit(0)
    else:
        print("constraints.txt is stale – regenerate with:")
        print("uv pip compile apps/api/requirements.txt --python-version 3.11 --python-platform linux --output-file apps/api/constraints.txt")
        sys.exit(1)

if __name__ == "__main__":
    main()
