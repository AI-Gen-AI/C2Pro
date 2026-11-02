"""Loaded by the interpreter when this directory is on PYTHONPATH. Inert unless C2PRO_AI_GOVERNOR_LEDGER is set.

Once the ledger variable IS set the governor is mandatory: a failure to install it must stop the process, never leave an
uncapped interpreter running next to a paid credential.
"""

import os

if os.environ.get("C2PRO_AI_GOVERNOR_LEDGER"):
    from real_ai_governor import install

    if not install():
        raise RuntimeError("C2PRO_AI_GOVERNOR_NOT_INSTALLED: the Anthropic SDK is not importable in this interpreter")
