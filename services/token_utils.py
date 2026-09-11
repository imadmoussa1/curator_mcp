"""
Token Optimization and Serialization Utilities.

Provides high-performance, idempotent utilities to compact verbose textual payloads,
filter sparse dictionaries, and prune redundant fields before serialization to LLM context.
These utilities ensure that personal library data remains high-signal while strictly
respecting LLM prompt token constraints.
"""

from typing import Any, Dict, List, Optional, Sequence


def compact_text(text: Optional[str], max_chars: int = 140) -> str:
    """
    Normalizes whitespace and truncates verbose text to a bounded character ceiling.

    Args:
        text: Raw text string (e.g., long reviews, notes, synopses), or None.
        max_chars: Maximum allowable character length including the trailing ellipsis.
            Defaults to 140 characters. Must be a positive integer.

    Returns:
        Whitespace-normalized and truncated string with '...' appended if truncated,
        or an empty string if input is None or whitespace-only.

    Examples:
        >>> compact_text("   A masterpiece   of   cinema.   ", max_chars=50)
        'A masterpiece of cinema.'
        >>> compact_text("This is an exceptionally long review...", max_chars=15)
        'This is an e...'
    """
    if not text:
        return ""

    normalized = " ".join(str(text).strip().split())
    if not normalized:
        return ""

    if len(normalized) <= max_chars:
        return normalized

    if max_chars <= 3:
        return normalized[:max_chars]

    return normalized[: max_chars - 3].rstrip() + "..."


def compact_dict(
    data: Optional[Dict[str, Any]],
    allowed_keys: Sequence[str],
    max_str_len: int = 200,
) -> Dict[str, Any]:
    """
    Extracts a projection of a dictionary containing only specified keys with populated values.

    Omits keys with None or empty collection values, and truncates long string fields
    to conserve token footprint.

    Args:
        data: Source dictionary to project.
        allowed_keys: Sequence of keys to retain in the projection.
        max_str_len: Maximum character length for string values before truncation.

    Returns:
        A new dictionary containing only populated allowed keys with bounded values.

    Examples:
        >>> compact_dict({"title": "Dune", "review": "A" * 300, "notes": None}, ["title", "review"])
        {'title': 'Dune', 'review': 'AAAA...'}
    """
    if not data or not isinstance(data, dict):
        return {}

    projected: Dict[str, Any] = {}
    for key in allowed_keys:
        if key not in data:
            continue
        val = data[key]
        if val is None or val == "" or val == [] or val == {}:
            continue
        if isinstance(val, str) and len(val) > max_str_len:
            val = compact_text(val, max_str_len)
        projected[key] = val

    return projected


def strip_none_and_empty(data: Any) -> Any:
    """
    Recursively prunes None and empty collections from nested data structures.

    Leaves booleans, integers, floats, and non-empty strings/collections intact.

    Args:
        data: Arbitrary nested object (dict, list, primitive).

    Returns:
        A new cleaned structure with nulls and empty sub-collections removed.
    """
    if isinstance(data, dict):
        return {
            k: strip_none_and_empty(v)
            for k, v in data.items()
            if v is not None and v != "" and v != [] and v != {}
        }
    if isinstance(data, list):
        return [strip_none_and_empty(v) for v in data if v is not None and v != ""]
    return data
