"""Utilities for robustly parsing HTTP response bodies returned as text.

Provides `robust_parse_text` to handle:
- Normal JSON (json.loads)
- NDJSON (newline-delimited JSON, returns list or single object)
- Text containing a JSON object plus extra data (uses json.JSONDecoder().raw_decode)
- Falls back to returning the original text if parsing fails

This lives in utils so tools can reuse the logic consistently.
"""
from __future__ import annotations

import json
from typing import Any


def robust_parse_text(text: str) -> Any:
    """Try to parse text as JSON. If it fails, try NDJSON (one JSON per line), then raw_decode the first JSON object, else return raw text.

    Returns the parsed Python object (dict/list/primitive) or the original text string if parsing failed.
    """
    # Try canonical JSON first
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try NDJSON: parse each non-empty line as JSON
    try:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        objs = [json.loads(ln) for ln in lines]
        if objs:
            return objs if len(objs) > 1 else objs[0]
    except Exception:
        pass

    # Try to extract the first JSON object from a noisy text blob
    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text)
        return obj
    except Exception:
        pass

    # Give up and return raw text
    return text

