"""Modulo Procesador NLP (RF-04, RF-05, RF-06, RF-13)."""

from .explainer import generate_explanation, regenerate_explanation
from .validator import validate_coherence

__all__ = ["generate_explanation", "regenerate_explanation", "validate_coherence"]
