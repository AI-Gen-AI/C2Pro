#!/usr/bin/env python
"""Convenience script to run golden dataset regression tests.

This script can be run from the repository root or the apps/api directory.

Usage:
    python apps/api/scripts/run_golden_regression.py
    python apps/api/scripts/run_golden_regression.py --difficulty easy
    python apps/api/scripts/run_golden_regression.py --output json --output-file report.json
"""

import sys
from pathlib import Path

# Add src to path so we can import golden module
script_dir = Path(__file__).parent.absolute()
src_dir = script_dir.parent / "src"
sys.path.insert(0, str(src_dir))

# Now import and run the main function
from golden.runner import main

if __name__ == "__main__":
    sys.exit(main())
