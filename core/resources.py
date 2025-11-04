"""Module that holds the server's resource map as a module-global.

Tools can import `from core.resources import resource_map` to access available resources.
The server populates this module during startup using `set_resource_map()`.
"""
from typing import Dict

resource_map: Dict[str, str] = {}


def set_resource_map(mapping: Dict[str, str]) -> None:
    global resource_map
    resource_map = mapping


def get_resource_map() -> Dict[str, str]:
    return resource_map

