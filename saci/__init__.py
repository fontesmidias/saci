"""Saci — roteador de LLMs gratuitas com fallback. Sempre dá um jeito."""

from .router import LLMRouter, Result, RouterError

__all__ = ["LLMRouter", "RouterError", "Result"]
__version__ = "0.1.0"
