from core.config import get_config  # type: ignore
import sys

def get_endpoint(key):
    _cfg = get_config() or {}
    base_url = _cfg.get("hkube_api_url", "").rstrip("/")
    if not base_url:
        sys.exit("Error: 'hkube_api_url' must be set in config.yaml")

    path = _cfg.get("api_paths", {}).get(key)
    if not path:
        sys.exit(f"Error: Missing API path for key '{key}' in config.yaml under 'api_paths'")

    return f"{base_url}{path}"
