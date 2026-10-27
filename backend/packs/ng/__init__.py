"""Nigerian entity pack (PRD 6): regex entities and gazetteer names."""

from app.detectors.base import Detector

from .gazetteer import GazetteerDetector
from .patterns import PatternDetector


def detectors() -> list[Detector]:
    """Ordered layers: pattern rules first, then the PERSON gazetteer."""
    return [PatternDetector(), GazetteerDetector()]
