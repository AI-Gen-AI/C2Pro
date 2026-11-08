"""Contract of the G4 PILOT-only, model-free Celery Beat image."""

from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[4]


def test_scheduler_image_avoids_external_spacy_model_download():
    api = (API_ROOT / "Dockerfile").read_text()
    beat = (API_ROOT / "Dockerfile.scheduler").read_text()

    # API and Worker must retain the Spanish Presidio NER model.
    assert "es_core_news_md-3.7.0-py3-none-any.whl" in api
    # Beat only emits Celery messages; model loading is lazy in anonymizer.py.
    assert "es_core_news_md" not in beat
    assert "github.com/explosion/spacy-models" not in beat
    assert "RUN pip install --no-cache-dir --only-binary=:all:" in beat


def test_scheduler_image_preserves_build_runtime_and_nonroot_identity():
    beat = (API_ROOT / "Dockerfile.scheduler").read_text()
    for required in (
        "FROM python:3.11-slim AS builder",
        "FROM python:3.11-slim AS runtime",
        "COPY --from=builder /opt/venv /opt/venv",
        "COPY src/ ./src/",
        "COPY alembic/ ./alembic/",
        "COPY scripts/ ./scripts/",
        "USER appuser",
        "HEALTHCHECK NONE",
        'CMD ["bash", "scripts/run_scheduler.sh"]',
    ):
        assert required in beat
    assert "http://localhost:" not in beat
