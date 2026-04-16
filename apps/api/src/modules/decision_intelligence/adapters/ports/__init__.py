"""Runtime-wired port adapters for Decision Intelligence.

These adapters bridge the lightweight Protocol contracts defined in
``src/modules/decision_intelligence/application/ports.py`` to the real
production services (document parsing, clause extraction, RAG retrieval,
coherence scoring, HITL). They are composed in
``src/modules/decision_intelligence/runtime.py`` and attached to the
FastAPI app.state during ``main.py`` lifespan startup.

Refers to Suite ID: TS-I13-E2E-REAL-001.
"""
