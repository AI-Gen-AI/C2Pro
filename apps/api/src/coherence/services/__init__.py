"""
Coherence Services

Additional services for coherence scoring and alert generation.
Note: This directory contains alternative implementations that may need consolidation.
"""

from src.coherence.services.scoring.calculator import ScoreCalculator, ScoreResult
from src.coherence.services.alerts.generator import AlertGeneratorService

__all__ = ["ScoreCalculator", "ScoreResult", "AlertGeneratorService"]
