"""Á mannamáli — plain-language rewriting with a local model.

See ``service.py``. The author's text is never replaced automatically.
"""

from ritarinn.services.simplification.service import SimplificationService, SimplifyOptions

__all__ = ["SimplificationService", "SimplifyOptions"]
