"""Pydantic schemas: the wire contract between the backend and the editor.

These models are the only place the JSON shape of the API is defined. Two
conventions hold throughout, and both exist so the frontend needs no adapter
layer of its own (``frontend/src/lib/types.ts`` mirrors this package):

* field names are serialised in ``camelCase``, because the consumer is
  JavaScript, while the Python attributes stay ``snake_case``;
* character offsets are UTF-16 code units, converted once at the boundary in
  ``ritarinn.text.offsets`` and declared in the response rather than assumed.

Nothing here imports from ``ritarinn.services``: the contract has to be
readable without knowing which engine produced a given issue.
"""
