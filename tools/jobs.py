from typing import Any
import httpx
from datetime import datetime, timedelta, timezone
from utils.get_endpoint import get_endpoint  # type: ignore
import json

async def search_jobs(resource_map: dict[str, str] | None = None,
                      experiment_name: str | None = None,
                      pipeline_name: str | None = None,
                      pipeline_type: str | None = None,
                      algorithm_name: str | None = None,
                      pipeline_status: str | None = None,
                      tags: str | None = None,
                      dates_range: dict[str, str] | None = None,
                      fields: dict[str, bool] | None = None,
                      limit: int = 10) -> str:
    """Search jobs via the hkube exec search API and return the JSON result as string.

    This tool accepts multiple invocation styles (for FastMCP compatibility):
    - new-style typed args (experiment_name, pipeline_name, ...)
    - kwargs containing raw_payload or other top-level keys

    Important: do NOT rewrite or replace a string `sort` value provided by the caller.
    If the caller sets sort to the string "desc" we preserve it as-is.
    """
    # Base endpoint
    search_url = get_endpoint("exec_search")

    # default date range
    if not dates_range:
        now = datetime.now(timezone.utc)
        dates_range = {
            'from': (now - timedelta(days=1)).isoformat(),
            'to': now.isoformat(),
        }

    default_fields = {
        'jobId': True,
        'userPipeline.name': True,
        'pipeline.startTime': True,
        'pipeline.priority': True,
        'pipeline.tags': True,
        'pipeline.types': True,
        'status.data.details': True,
        'result.timeTook': True,
        'graph': True,
    }
    if fields:
        default_fields.update(fields)

    # === Parse incoming args/kwargs for raw payloads or compact shapes ===
    raw_payload = None

    # 1. If caller passed a raw_payload in kwargs (possibly JSON string)
    if 'raw_payload' in kwargs:
        raw_payload = kwargs.get('raw_payload')
        if isinstance(raw_payload, str):
            try:
                raw_payload = json.loads(raw_payload)
            except Exception:
                # keep as string (will fail later)
                pass

    # 2. If args supplied and the first arg looks like a JSON string or dict, use it
    if raw_payload is None and args:
        first = args[0]
        if isinstance(first, str):
            try:
                parsed = json.loads(first)
                if isinstance(parsed, (dict, list)):
                    raw_payload = parsed
            except Exception:
                # not JSON; ignore
                pass
        elif isinstance(first, (dict, list)):
            raw_payload = first

    # 3. If kwargs contains likely top-level keys (sort/limit/status) treat kwargs as raw_payload
    if raw_payload is None:
        potential_keys = {'sort', 'limit', 'size', 'status', 'query'}
        if any(k in kwargs for k in potential_keys):
            # shallow copy
            raw_payload = dict(kwargs)

    # === Build canonical payload_to_send ===
    if raw_payload is not None:
        payload_to_send = dict(raw_payload) if isinstance(raw_payload, dict) else {'query': {}}

        # Map size -> limit
        if 'size' in payload_to_send and 'limit' not in payload_to_send:
            try:
                payload_to_send['limit'] = int(payload_to_send.pop('size'))
            except Exception:
                payload_to_send['limit'] = payload_to_send.pop('size')

        # If top-level status provided, map to query.pipelineStatus
        if 'status' in payload_to_send:
            q = payload_to_send.get('query', {}) or {}
            q['pipelineStatus'] = payload_to_send.pop('status')
            payload_to_send['query'] = q

        # If top-level pipelineName/pipeline_name into query
        for key in ('pipelineName', 'pipeline_name'):
            if key in payload_to_send:
                q = payload_to_send.get('query', {}) or {}
                q['pipelineName'] = payload_to_send.pop(key)
                payload_to_send['query'] = q

        # If top-level datesRange move it under query
        if 'datesRange' in payload_to_send and 'query' not in payload_to_send:
            payload_to_send['query'] = {'datesRange': payload_to_send.pop('datesRange')}

        # Ensure pagination defaults
        if 'limit' not in payload_to_send:
            payload_to_send['limit'] = limit
        if 'pageNum' not in payload_to_send:
            payload_to_send['pageNum'] = 1
        if 'fields' not in payload_to_send:
            payload_to_send['fields'] = default_fields

        # Ensure there is a query object
        if 'query' not in payload_to_send:
            payload_to_send['query'] = {}

    else:
        # Build payload from typed params (legacy style)
        payload_to_send = {
            'query': {
                'datesRange': dates_range,
                'experimentName': experiment_name,
                'pipelineName': pipeline_name,
                'pipelineType': pipeline_type,
                'algorithmName': algorithm_name,
                'pipelineStatus': pipeline_status,
                'tags': tags,
            },
            'sort': 'desc',
            'pageNum': 1,
            'limit': limit,
            'fields': default_fields,
        }
        payload_to_send['query'] = {k: v for k, v in payload_to_send['query'].items() if v is not None}

    # Final safety: ensure query is present
    if 'query' not in payload_to_send:
        payload_to_send['query'] = {}

    payload_to_send['sort'] = 'desc'

    # --- Recursive sanitizer: ensure name-like fields anywhere in the query are strings ---
    def _ensure_string(value):
        if value is None:
            return value
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        try:
            return json.dumps(value)
        except Exception:
            return str(value)

    name_keys = {'experimentName', 'pipelineName', 'pipelineType', 'algorithmName', 'pipelineStatus'}

    def _sanitize(obj):
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if k in name_keys:
                    obj[k] = _ensure_string(v)
                else:
                    obj[k] = _sanitize(v)
            return obj
        elif isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        else:
            return obj

    payload_to_send['query'] = _sanitize(payload_to_send.get('query', {})) or {}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(search_url, json=payload_to_send, timeout=30.0)
            try:
                resp.raise_for_status()
                return str(resp.json())
            except httpx.HTTPStatusError:
                return f"HTTP {resp.status_code}: {resp.text}"
        except Exception as e:
            return f"Failed to search jobs: {e}"


def get_tools(resource_map: dict[str, str]) -> dict[str, Any]:
    return {"search_jobs_tool": {"func": search_jobs, "title": "Search jobs", "description": "Search the hkube exec API for jobs matching filters and return the results. If the user asks for job logs, you should read resource://Accessing_job_logs_in_HKube"}}
