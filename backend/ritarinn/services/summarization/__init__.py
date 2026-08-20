"""Samantekt — summarization with a local model.

See ``service.py``. Long documents are summarised hierarchically so that a
model with a bounded context is never handed more than it can read.
"""

from ritarinn.services.summarization.service import SummarizationService, SummaryOptions

__all__ = ["SummarizationService", "SummaryOptions"]
