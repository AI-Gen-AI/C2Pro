"""
Coherence Services

Additional services for coherence scoring and alert generation.
Note: This directory contains alternative implementations that may need consolidation.
"""

from src.coherence.services.alerts.generator import AlertGeneratorService
from src.coherence.services.scoring.calculator import ScoreCalculator, ScoreResult

__all__ = ["ScoreCalculator", "ScoreResult", "AlertGeneratorService"]
