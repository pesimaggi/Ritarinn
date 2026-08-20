"""Samantekt — summarization (Milestone 2).

Deliberately empty in v0.1. Summarization requires a local LLM, and Ritarinn
will not fall back to a hosted service, so the feature stays switched off and
``/api/summarize`` reports it as unavailable rather than degrading silently.

The planned design is hierarchical: chunk on paragraph/section boundaries,
summarise each chunk, then combine — so that a small local model is never handed
a document larger than its context window. See ``docs/roadmap.md``.
"""
