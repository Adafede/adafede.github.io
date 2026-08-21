"""Small string-conversion helpers shared across the pipeline."""

from __future__ import annotations


def snake_to_camel(snake_str: str) -> str:
    """Convert a snake_case identifier to camelCase.

    Used for CiTO ontology property names (e.g. ``cites_as_evidence`` →
    ``citesAsEvidence``) embedded in annotation spans.
    """
    parts = snake_str.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])
