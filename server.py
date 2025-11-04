from core.logging_config import setup_logging
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import TextResource
from pathlib import Path
from importlib import import_module
import pkgutil
import inspect
import json
import sys
from typing import Dict, List, Tuple

# Set up logging using core.logging_config
logger = setup_logging()

# Initialize mcp later after resources are loaded so we can pass instructions via constructor
mcp = None  # type: ignore

logger.info("MCP server bootstrap starting.")

###################################################### MCP Resources ######################################################

logger.info("\n\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")
logger.info("Loading MCP resources...")
# Resources folder located next to this server.py file
resources_dir = (Path(__file__).resolve().parent / "resources").resolve()

# Build an in-memory list and map of available resources (name -> content)
resource_files: List[Tuple[Path, str]] = []
resource_map: Dict[str, str] = {}

if resources_dir.is_dir():
    for file_path in resources_dir.iterdir():
        if file_path.is_file():
            content = file_path.read_text(encoding="utf-8")
            resource_files.append((file_path, content))
            resource_map[file_path.stem.lower()] = content
    logger.info(f"Total resources discovered: {len(resource_files)}, resource names: {list(resource_map.keys())}")

# Expose resources via core.resources for tools that import it as a global
try:
    from core.resources import set_resource_map  # type: ignore

    set_resource_map(resource_map)
    logger.info("Populated core.resources.resource_map for tools to use.")
except Exception:
    logger.exception("Failed to populate core.resources")

# If assistant_instructions resource exists, use it as the FastMCP instructions during construction
instr = resource_map.get("assistant_instructions")

# Now instantiate FastMCP with the instructions parameter
try:
    mcp = FastMCP("hkube", instructions=instr)
    logger.info("MCP server instance created with instructions: %s", bool(instr))
except Exception:
    logger.exception("Failed to create FastMCP instance")
    raise

# Now register resources into the mcp instance
if mcp is not None:
    for file_path, content in resource_files:
        try:
            resource = TextResource(
                uri=f"resource://{file_path.stem.replace(' ', '_')}",
                name=file_path.stem,
                text=content,
                description=f"Contents of {file_path.name}",
                mime_type="text/markdown",
            )
            mcp.add_resource(resource)
        except Exception:
            logger.exception(f"Failed to add resource {file_path}")
    logger.info(f"Total resources loaded into MCP: {len(resource_files)}")

###################################################### MCP Tools ######################################################

logger.info("\n\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")
logger.info("Loading MCP tools...")

TOOLS_PACKAGE = "tools"
tools_path = Path(__file__).resolve().parent / TOOLS_PACKAGE
loaded_tool_count = 0
registered_tool_names: list[str] = []
if tools_path.is_dir():
    for finder, name, ispkg in pkgutil.iter_modules([str(tools_path)]):
        if name.startswith("_"):
            continue
        module_name = f"{TOOLS_PACKAGE}.{name}"
        try:
            mod = import_module(module_name)
            logger.info(f"Imported tools module: {module_name}")
            if hasattr(mod, "get_tools"):
                try:
                    sig = inspect.signature(mod.get_tools)
                    if len(sig.parameters) > 0:
                        mapping = mod.get_tools(resource_map)
                    else:
                        mapping = mod.get_tools()
                except Exception:
                    # Fallback: call without args
                    mapping = mod.get_tools()
                # mapping: tool_name -> { 'func': callable, 'title': str, 'description': str }
                for tool_name, meta in mapping.items():
                    func = None
                    title = None
                    description = None
                    if isinstance(meta, dict):
                        func = meta.get("func")
                        title = meta.get("title")
                        description = meta.get("description")
                    else:
                        # meta must be a callable
                        func = meta

                    if not func:
                        logger.warning(f"Tool {tool_name} in {module_name} did not provide a callable; skipping")
                        continue

                    # create a wrapper to call tools
                    def make_wrapper(_func):
                        try:
                            orig_sig = inspect.signature(_func)
                            orig_params = list(orig_sig.parameters.values())
                            inject_resource = bool(orig_params and orig_params[0].name == 'resource_map')
                            if inject_resource:
                                wrapper_params = orig_params[1:]
                            else:
                                wrapper_params = orig_params
                            wrapper_sig = inspect.Signature(parameters=wrapper_params)
                        except Exception:
                            inject_resource = False
                            wrapper_sig = None

                        async def _wrapped(*call_args, **call_kwargs):
                            def _maybe_parse(obj):
                                if isinstance(obj, str):
                                    try:
                                        return json.loads(obj)
                                    except Exception:
                                        return obj
                                return obj

                            if 'args' in call_kwargs or 'kwargs' in call_kwargs:
                                args_in = call_kwargs.get('args', None)
                                kwargs_in = call_kwargs.get('kwargs', None)
                            else:
                                args_in = call_args if call_args else None
                                kwargs_in = call_kwargs if call_kwargs else None

                            if args_in is None and kwargs_in is None:
                                if inject_resource:
                                    return await _func(resource_map)
                                return await _func()

                            if isinstance(args_in, (list, tuple)):
                                args_un = list(args_in)
                            else:
                                args_un = _maybe_parse(args_in) or []
                                if not isinstance(args_un, (list, tuple)):
                                    args_un = [args_un]

                            if isinstance(kwargs_in, dict):
                                kwargs_un = kwargs_in
                            else:
                                kwargs_un = _maybe_parse(kwargs_in) or {}
                                if not isinstance(kwargs_un, dict):
                                    kwargs_un = {}

                            if inject_resource:
                                return await _func(resource_map, *args_un, **kwargs_un)
                            return await _func(*args_un, **kwargs_un)

                        if wrapper_sig is not None:
                            _wrapped.__signature__ = wrapper_sig
                        return _wrapped

                    wrapper = make_wrapper(func)

                    # register via mcp.add_tool with metadata
                    try:
                        description = description + ". Always read the assistant instructions resource first (by using the instructions tool) before answering any question." if description else "Always read the assistant instructions resource first before answering any question."
                        mcp.add_tool(wrapper, name=tool_name, title=title, description=description)
                        logger.info(f"Added tool via add_tool: {tool_name} (title={title}) from {module_name}")
                        loaded_tool_count += 1
                        registered_tool_names.append(tool_name)
                    except Exception:
                        logger.exception(f"Failed to register tool {tool_name} from {module_name}")
        except Exception:
            logger.exception(f"Failed to load tools from module {module_name}")
    logger.info(f"Total tools registered: {loaded_tool_count} , tool names: {registered_tool_names}")

###################################################### Startup ######################################################

if __name__ == "__main__":
    logger.info("Starting MCP server...")
    try:
        mcp.run(transport="stdio")
        logger.info("MCP server shut down.")
    except Exception:
        logger.exception("Unhandled exception running MCP server")
        print("Unhandled exception occurred. See logs/server.log for details.", file=sys.stderr)
        sys.exit(-1)
