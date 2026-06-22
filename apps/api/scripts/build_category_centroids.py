#!/usr/bin/env python
"""
Script to execute the Category Centroid build process.
Initializes the database session, loads the registry, and calls the CentroidBuilderService.

Location: apps/api/scripts/build_category_centroids.py
"""

import asyncio
import logging
import sys

from src.coherence.adapters.persistence.pgvector_centroid_repository import (
    PgvectorCentroidRepository,
)
from src.coherence.application.services.centroid_builder import CentroidBuilderService
from src.coherence.category_registry import load_category_registry
from src.core.database import SessionLocal

# Set up logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting Category Centroid build process...")

    try:
        # Load registry
        registry = load_category_registry()
        logger.info(
            f"Loaded registry: version {registry.version.registry_version}, "
            f"score_version {registry.version.score_version}"
        )

        # Open DB session and run builder
        async with SessionLocal() as session:
            repository = PgvectorCentroidRepository(session)
            builder = CentroidBuilderService(repository)

            # The builder will automatically query OpenAI if centroids are missing or hash differs.
            # CAUTION: Running this without mock/stub in CI will charge the OpenAI account.
            result = await builder.ensure_centroids_built(registry)

            # Commit the upserts
            await session.commit()

        logger.info(f"Successfully verified/built {len(result)} category centroids.")

    except Exception as e:
        logger.exception(f"Fatal error during centroid build: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
