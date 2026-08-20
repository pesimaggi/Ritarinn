"""Shared plumbing for local text generation.

Summarization and plain-language rewriting differ in their prompts, not in
their mechanics: both chunk a document, call a local model, and hand the result
back for the author to review. That shared machinery lives here.
"""
