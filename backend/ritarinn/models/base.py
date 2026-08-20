"""Shared model configuration.

Every schema in this package serialises to ``camelCase`` and accepts either
spelling on input. Defining that once means a new field cannot accidentally
reach the frontend as ``snake_case`` — which would be a silent contract break,
since JavaScript would simply read ``undefined``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class RitarinnModel(BaseModel):
    """Base for every schema on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        # Server-side construction uses the Python names (``start_char=…``);
        # the alias is what goes over the wire.
        populate_by_name=True,
    )
