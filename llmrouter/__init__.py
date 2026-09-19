"""LLM Router — cascata de fallback entre provedores gratuitos."""

from .router import LLMRouter, RouterError, Result

__all__ = ["LLMRouter", "RouterError", "Result"]
__version__ = "0.1.0"
