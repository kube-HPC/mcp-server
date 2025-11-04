from typing import Any
from core.resources import get_resource_map  # type: ignore
import json
import re

async def list_resources() -> str:
    # Placeholder; the actual closure will be provided in get_tools
    return ""

async def read_resource(resource_name: str | None = None) -> str:
    # Placeholder; actual closure will be provided in get_tools
    return ""


def get_tools() -> dict[str, Any]:
    # Implement closures that capture resource_map but expose clean signatures
    resource_map = get_resource_map()

    async def _list_resources() -> str:
        names = sorted(name for name in resource_map.keys())
        return "\n".join(names) if names else "No resources available."

    def _extract_from_payload(s: str) -> str | None:
        """Try to extract the intended resource name from a payload string.

        Handles:
        - plain string names
        - JSON object strings like {"args":"name","kwargs":"..."}
        - concatenated JSON objects (NDJSON-like) by taking the last object's 'args' value
        """
        if not s:
            return None
        # If it's already a simple name, return it
        if not ('{' in s and '}' in s):
            return s

        # Try plain JSON
        try:
            obj = json.loads(s)
            if isinstance(obj, dict) and 'args' in obj:
                return obj.get('args')
        except Exception:
            pass

        # Try to find all "args":"..." occurrences and return the last
        try:
            matches = re.findall(r'"args"\s*:\s*"([^"}]*)"', s)
            if matches:
                return matches[-1]
        except Exception:
            pass

        # Try raw_decode successive JSON objects and take last one's 'args'
        try:
            decoder = json.JSONDecoder()
            pos = 0
            last = None
            L = len(s)
            while pos < L:
                # skip whitespace
                while pos < L and s[pos].isspace():
                    pos += 1
                if pos >= L:
                    break
                obj, idx = decoder.raw_decode(s, pos)
                last = obj
                pos += idx
            if isinstance(last, dict) and 'args' in last:
                return last.get('args')
        except Exception:
            pass

        return None

    async def _read_resource(resource_name: str | None = None) -> str:
        # Normalize and extract actual resource name if the input is JSON/concatenated
        q = resource_name
        if isinstance(q, str):
            q = q.strip()
            extracted = _extract_from_payload(q)
            if extracted:
                q = extracted
        # final check
        if not q:
            return "Please provide a resource name to read. Use `list_resources()` to see available resources."

        q = str(q).strip().lower()

        # exact
        if q in resource_map:
            return resource_map[q]

        # partial matches
        matches = [name for name in resource_map.keys() if q in name or name in q]
        if len(matches) == 1:
            return resource_map[matches[0]]
        if len(matches) > 1:
            return "Multiple resources match your query:\n" + "\n".join(matches)

        # try filename contains words
        matches = [name for name in resource_map.keys() if all(part in name for part in q.split())]
        if len(matches) == 1:
            return resource_map[matches[0]]
        if len(matches) > 1:
            return "Multiple resources match your query:\n" + "\n".join(matches)

        return f"No resource found matching '{q}'. Use list_resources() to see available resources."

    return {
        "list_resources": {"func": _list_resources, "title": "List resources", "description": "Return a newline-separated list of available resource names."},
        "read_resource": {"func": _read_resource, "title": "Read resource", "description": "Return the content of a resource given a name or partial name."}
    }
