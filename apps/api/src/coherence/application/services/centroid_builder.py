"""
Service to build and cache deterministic prototype centroids from the Category Registry.

Location: apps/api/src/coherence/application/services/centroid_builder.py
"""

import hashlib

import structlog

from src.coherence.category_registry import CanonicalCategory, CategoryRegistry
from src.coherence.ports.centroid_repository import CategoryCentroidRecord, ICentroidRepository
from src.documents.adapters.rag.rag_service import _embed_texts

logger = structlog.get_logger(__name__)


# pgvector columns (document_chunks, clause_embeddings, category_centroids) are
# all declared vector(1536). The centroid cache MUST match or pgvector rejects
# the INSERT with an opaque dimension error. This is the explicit compatibility
# check mandated by TASK-BCK-088 / SPEC §9.2: fail predictably at the
# application layer, never silently at the DB boundary.
#
# NOTE: The live model for this phase is OpenAI ``text-embedding-3-small``
# (1536 dims) — chosen for pragmatic pgvector compatibility. This guard does
# NOT change that; it only rejects an accidental swap to an incompatible-dim
# model. text-embedding-3-small maps to 1536 and passes.
EXPECTED_PGVECTOR_DIMS = 1536

# Known output dimensions for candidate embedding models (SPEC §9.2 shortlist).
# Used for a cheap pre-flight reject before spending embedding API calls.
# Unknown models are NOT rejected here — the post-embedding length backstop
# catches every model regardless of whether it is listed.
_KNOWN_MODEL_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,   # OpenAI — live model for this phase
    "text-embedding-3-large": 3072,
    "bge-m3": 1024,
    "multilingual-e5-large": 1024,
    "cohere-multilingual-v3": 1024,
}


class EmbeddingDimensionMismatchError(ValueError):
    """Raised when the configured embedding model is incompatible with the
    pgvector column dimension, before any vector reaches the database.

    Subclasses ``ValueError`` for backward compatibility with callers that
    catch ``ValueError`` around centroid building.
    """


def compute_seed_hash(prototypes: list[str]) -> str:
    """
    Computes a deterministic SHA256 hash from a list of strings.
    The strings are sorted before hashing so the order does not change the hash.
    """
    sorted_texts = sorted(prototypes)
    combined = "|".join(sorted_texts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def l2_normalize(vector: list[float]) -> list[float]:
    """
    Applies L2 normalization to a vector.
    """
    import math

    magnitude = math.sqrt(sum(val**2 for val in vector))
    if magnitude == 0:
        return vector
    return [val / magnitude for val in vector]


async def calculate_centroid_vector(texts: list[str]) -> list[float]:
    """
    Embeds the provided texts and calculates their centroid (mean) vector,
    normalized using L2 normalization.
    """
    if not texts:
        raise ValueError("Cannot calculate centroid of empty text list.")

    embeddings: list[list[float]] = await _embed_texts(texts)
    if not embeddings:
        raise ValueError("Embedding service returned empty results.")

    dimension = len(embeddings[0])
    sum_vector = [0.0] * dimension

    for emb in embeddings:
        for i, val in enumerate(emb):
            sum_vector[i] += val

    mean_vector = [val / len(embeddings) for val in sum_vector]
    return l2_normalize(mean_vector)


class CentroidBuilderService:
    """
    Service to ensure all categories in the registry have corresponding
    cached centroid vectors in the repository.
    """

    def __init__(self, repository: ICentroidRepository):
        self.repository = repository

    async def ensure_centroids_built(
        self, registry: CategoryRegistry
    ) -> dict[CanonicalCategory, CategoryCentroidRecord]:
        """
        Validates the repository against the provided registry.
        If a category's prototypes have changed (detected via seed_hash) or
        are missing, it computes and saves a new centroid vector.

        Returns the mapping of category to the active centroid record.
        """
        score_version = registry.version.score_version
        embedding_model = registry.version.embedding_model

        # Pre-flight compatibility guard (cheap, before any embedding calls).
        # Reject KNOWN models whose dimension does not match the pgvector column.
        # Unknown models fall through to the post-embedding length backstop.
        declared_dims = _KNOWN_MODEL_DIMS.get(embedding_model)
        if declared_dims is not None and declared_dims != EXPECTED_PGVECTOR_DIMS:
            raise EmbeddingDimensionMismatchError(
                f"embedding_model '{embedding_model}' produces {declared_dims}-dim "
                f"vectors, incompatible with the {EXPECTED_PGVECTOR_DIMS}-dim pgvector "
                "columns. Migrate the vector columns or choose a 1536-dim model "
                "(e.g. text-embedding-3-small)."
            )

        logger.info(
            "Checking category centroids",
            score_version=score_version,
            embedding_model=embedding_model
        )

        active_centroids: dict[CanonicalCategory, CategoryCentroidRecord] = {}

        for cat_enum, definition in registry.categories.items():
            # Flatten all language prototypes into a single list
            all_prototypes: list[str] = []
            for lang_protos in definition.prototypes.values():
                all_prototypes.extend(lang_protos)

            seed_hash = compute_seed_hash(all_prototypes)

            existing_record = await self.repository.get_centroid(
                category=cat_enum.value,
                embedding_model=embedding_model,
                score_version=score_version,
            )

            if existing_record and existing_record.seed_hash == seed_hash:
                logger.debug(f"Centroid for {cat_enum.value} is up-to-date", seed_hash=seed_hash)
                active_centroids[cat_enum] = existing_record
                continue

            logger.info(
                f"Building new centroid for {cat_enum.value}",
                reason="missing" if not existing_record else "hash_mismatch",
                new_hash=seed_hash,
            )

            centroid_vector = await calculate_centroid_vector(all_prototypes)

            # Post-embedding length backstop: name-independent, zero-maintenance.
            # Catches ANY model (incl. ones absent from _KNOWN_MODEL_DIMS) before
            # the opaque pgvector dimension error at INSERT time.
            if len(centroid_vector) != EXPECTED_PGVECTOR_DIMS:
                raise EmbeddingDimensionMismatchError(
                    f"Centroid for {cat_enum.value} is {len(centroid_vector)}-dim; "
                    f"expected {EXPECTED_PGVECTOR_DIMS}. Aborting before pgvector "
                    f"insert (embedding_model='{embedding_model}')."
                )

            new_record = CategoryCentroidRecord(
                category=cat_enum.value,
                embedding_model=embedding_model,
                score_version=score_version,
                embedding=centroid_vector,
                seed_hash=seed_hash,
            )

            saved_record = await self.repository.save_centroid(new_record)
            active_centroids[cat_enum] = saved_record

        logger.info("All centroids verified and built successfully.")
        return active_centroids
