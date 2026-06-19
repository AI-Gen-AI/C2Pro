import math
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.coherence.application.services.centroid_builder import (
    EXPECTED_PGVECTOR_DIMS,
    CentroidBuilderService,
    EmbeddingDimensionMismatchError,
    calculate_centroid_vector,
    compute_seed_hash,
    l2_normalize,
)
from src.coherence.category_registry import CanonicalCategory, load_category_registry
from src.coherence.ports.centroid_repository import CategoryCentroidRecord, ICentroidRepository


@pytest.fixture
def mock_registry():
    return load_category_registry()


@pytest.fixture
def mock_repository():
    repo = MagicMock(spec=ICentroidRepository)
    repo.get_centroid = AsyncMock(return_value=None)

    async def mock_save(record):
        return CategoryCentroidRecord(
            id=uuid4(),
            category=record.category,
            embedding_model=record.embedding_model,
            score_version=record.score_version,
            embedding=record.embedding,
            seed_hash=record.seed_hash,
            created_at=datetime.utcnow(),
        )

    repo.save_centroid = AsyncMock(side_effect=mock_save)
    return repo


def test_compute_seed_hash():
    """Verify hash is deterministic and order-independent."""
    protos1 = ["apple", "banana", "cherry"]
    protos2 = ["cherry", "apple", "banana"]

    hash1 = compute_seed_hash(protos1)
    hash2 = compute_seed_hash(protos2)

    assert hash1 == hash2
    assert isinstance(hash1, str)
    assert len(hash1) == 64  # SHA256 length


def test_l2_normalize():
    """Verify L2 normalization math."""
    vector = [3.0, 4.0]
    # Magnitude = sqrt(3^2 + 4^2) = 5
    # Normalized = [3/5, 4/5] = [0.6, 0.8]
    normalized = l2_normalize(vector)

    assert math.isclose(normalized[0], 0.6)
    assert math.isclose(normalized[1], 0.8)

    # Verify magnitude of normalized vector is 1.0
    assert math.isclose(math.sqrt(sum(v**2 for v in normalized)), 1.0)


@pytest.mark.asyncio
@patch("src.coherence.application.services.centroid_builder._embed_texts")
async def test_calculate_centroid_vector(mock_embed_texts):
    """Verify centroid math across multiple embeddings."""
    mock_embed_texts.return_value = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    texts = ["proto1", "proto2", "proto3"]
    centroid = await calculate_centroid_vector(texts)

    mock_embed_texts.assert_called_once_with(texts)

    # Mean vector should be [1/3, 1/3, 1/3]
    # Magnitude = sqrt(1/9 + 1/9 + 1/9) = sqrt(3/9) = sqrt(1/3) = ~0.577
    # Normalized = [1/3 / sqrt(1/3), ...] = [sqrt(1/3), sqrt(1/3), sqrt(1/3)] = [0.577, 0.577, 0.577]
    expected_val = math.sqrt(1 / 3)

    assert len(centroid) == 3
    for val in centroid:
        assert math.isclose(val, expected_val)


@pytest.mark.asyncio
@patch("src.coherence.application.services.centroid_builder.calculate_centroid_vector")
async def test_centroid_builder_builds_missing(mock_calc, mock_registry, mock_repository):
    """Verify builder computes and saves new centroids if they are missing."""
    mock_calc.return_value = [0.5] * 1536

    builder = CentroidBuilderService(mock_repository)
    result = await builder.ensure_centroids_built(mock_registry)

    assert len(result) == 6
    assert CanonicalCategory.LEGAL in result

    # get_centroid called 6 times (once per category)
    assert mock_repository.get_centroid.call_count == 6

    # save_centroid called 6 times
    assert mock_repository.save_centroid.call_count == 6


@pytest.mark.asyncio
@patch("src.coherence.application.services.centroid_builder.calculate_centroid_vector")
async def test_centroid_builder_skips_existing(mock_calc, mock_registry, mock_repository):
    """Verify builder skips saving if centroid exists and hash matches."""

    # Setup mock repo to return matching records
    async def mock_get(category, embedding_model, score_version):
        definition = mock_registry.categories[CanonicalCategory(category)]
        all_protos = []
        for protos in definition.prototypes.values():
            all_protos.extend(protos)
        seed_hash = compute_seed_hash(all_protos)

        return CategoryCentroidRecord(
            category=category,
            embedding_model=embedding_model,
            score_version=score_version,
            embedding=[0.1] * 1536,
            seed_hash=seed_hash,
        )

    mock_repository.get_centroid.side_effect = mock_get

    builder = CentroidBuilderService(mock_repository)
    result = await builder.ensure_centroids_built(mock_registry)

    assert len(result) == 6

    # calculate_centroid_vector should never be called because all matched
    mock_calc.assert_not_called()

    # save_centroid should never be called
    mock_repository.save_centroid.assert_not_called()


@pytest.mark.asyncio
async def test_centroid_builder_dimension_compatibility_guard(mock_registry, mock_repository):
    """Pre-flight guard: a KNOWN incompatible-dim model is rejected by name
    BEFORE any embedding call (no get_centroid / save_centroid)."""
    # Force a known 1024-dim model.
    mock_registry.version.embedding_model = "bge-m3"

    builder = CentroidBuilderService(mock_repository)
    with pytest.raises(EmbeddingDimensionMismatchError, match="produces 1024-dim"):
        await builder.ensure_centroids_built(mock_registry)

    # The reject must happen before touching the repository.
    mock_repository.get_centroid.assert_not_called()
    mock_repository.save_centroid.assert_not_called()


@pytest.mark.asyncio
async def test_centroid_builder_unknown_model_passes_preflight(
    mock_registry, mock_repository
):
    """An UNKNOWN model is not pre-flight rejected (not in the dim map) — it must
    fall through to the build path, where the length backstop is the safety net."""
    mock_registry.version.embedding_model = "some-future-model-v9"

    with patch(
        "src.coherence.application.services.centroid_builder.calculate_centroid_vector"
    ) as mock_calc:
        mock_calc.return_value = [0.5] * EXPECTED_PGVECTOR_DIMS  # correct dim
        builder = CentroidBuilderService(mock_repository)
        result = await builder.ensure_centroids_built(mock_registry)

    assert len(result) == 6  # built normally; pre-flight did not block


@pytest.mark.asyncio
@patch("src.coherence.application.services.centroid_builder.calculate_centroid_vector")
async def test_centroid_builder_length_backstop_rejects_wrong_dim(
    mock_calc, mock_registry, mock_repository
):
    """Backstop guard: even with the live (compatible) model, if the embedding
    service returns a wrong-dimension vector, the builder aborts BEFORE the
    pgvector insert — name-independent safety net."""
    # Registry keeps the live compatible model (text-embedding-3-small).
    # But the embedding service returns a 1024-dim vector (e.g. provider drift).
    mock_calc.return_value = [0.1] * 1024

    builder = CentroidBuilderService(mock_repository)
    with pytest.raises(EmbeddingDimensionMismatchError, match="expected 1536"):
        await builder.ensure_centroids_built(mock_registry)

    # Never persisted the bad vector.
    mock_repository.save_centroid.assert_not_called()
