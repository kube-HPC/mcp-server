#!/usr/bin/env python3.10
"""mcp-cli: simple chat client for MCP /api/generate

Features:
- Single prompt mode: --prompt "..."
- Interactive REPL: --chat
- Uses JSON payload {model, prompt, stream}
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx
import logging

# moved local imports to top-level per refactor request
import os
import re
import io
import contextlib
import asyncio
import importlib.util
import threading
import subprocess
import atexit
import signal
from dotenv import load_dotenv
import os

load_dotenv()  # Loads variables from .env into the environment

# config loader
from config import get_config  # type: ignore

# runtime debug toggle (set in main from config.debug)
DEBUG = False
ASSISTANT_NAME = "HKube Chat"

# Require Python 3.10
if sys.version_info < (3, 10) or sys.version_info >= (3, 11):
    sys.stderr.write("mcp-cli requires Python 3.10.x. Please run with python3.10.\n")
    raise SystemExit(1)


DEFAULT_URL = None


def build_payload(model: str, prompt: str, stream: bool) -> dict[str, Any]:
    return {"model": model, "prompt": prompt, "stream": stream}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="mcp-cli interactive chat client for /api/generate")
    p.add_argument("--auto-tools", action="store_true", help="Ask the LLM whether to use a tool and orchestrate the call")
    p.add_argument("--stream", action="store_true", help="Ask server to stream responses if supported")
    p.add_argument("--timeout", type=float, default=60.0, help="Request timeout seconds")
    p.add_argument("--no-verify", action="store_true", help="Do not verify TLS certificates")
    return p.parse_args()


def print_json(obj: Any) -> None:
    try:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    except Exception:
        print(obj)


def display(msg: Any) -> None:
    """Print a message with a blank line before and after.
    If msg is not a string, pretty-print JSON via print_json.
    """
    print()
    if isinstance(msg, str):
        print(msg)
    else:
        print_json(msg)
    print()


def assistant_display(obj: Any) -> None:
    """Print assistant-labeled output with blank lines.
    If obj is a string, prefix with assistant name. If obj is a dict/object, print the name then pretty JSON.
    """
    print()
    if isinstance(obj, str):
        print(f"{ASSISTANT_NAME}: {obj}")
    else:
        print(f"{ASSISTANT_NAME}:")
        print_json(obj)
    print()


def call_generate(url: str, payload: dict[str, Any], stream: bool, timeout: float, verify: bool) -> int:
    headers = {"Content-Type": "application/json"}
    try:
        if stream:
            with httpx.Client(timeout=timeout, verify=verify) as client:
                with client.stream("POST", url, headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    for chunk in resp.iter_lines():
                        if not chunk:
                            continue
                        try:
                            obj = json.loads(chunk)
                            # In non-debug mode only print the 'response' field if present
                            if DEBUG:
                                assistant_display(obj)
                            else:
                                if isinstance(obj, dict) and "response" in obj:
                                    assistant_display(obj.get("response"))
                                else:
                                    assistant_display(obj)
                        except Exception:
                            print(chunk.decode("utf-8", errors="replace"))
            return 0
        else:
            payload["max_tokens"] = 1000000000
            resp = httpx.post(url, headers=headers, json=payload, timeout=timeout, verify=verify)
            # Diagnostic logging:
            print(">>> SENT payload size:", len(json.dumps(payload).encode('utf-8')), "bytes", file=sys.stderr)
            print(">>> RECEIVED status:", resp.status_code, "content-length header:", resp.headers.get('content-length'), file=sys.stderr)
            print(">>> RECEIVED bytes:", len(resp.content), "encoding:", resp.encoding, file=sys.stderr)
            print(">>> FIRST 2000 chars of response:", resp.text[:2000], file=sys.stderr)
            resp.raise_for_status()
            try:
                data = resp.json()
                # Only show full JSON when debugging; otherwise show only the 'response' key if present
                if DEBUG:
                    assistant_display(data)
                else:
                    if isinstance(data, dict) and "response" in data:
                        assistant_display(data.get("response"))
                    else:
                        # fallback to entire text if response key missing
                        try:
                            assistant_display(data)
                        except Exception:
                            print(resp.text)
            except Exception:
                print(resp.text)
            return 0
    except httpx.HTTPError as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 2


def ask_model_for_tool(mll_url: str, prompt: str, model: str, timeout: float, verify: bool, tool_catalog: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Ask the LLM whether to use a tool. Expects a JSON response like:
    {"use_tool": true/false, "tool_name": "...", "tool_prompt": "..."}
    """
    system_instruction = (
        "You are an assistant that decides whether to call MCP tools.\n"
        "If a tool is needed to answer the user's request, reply with a JSON object only, without extra text, in the form:\n"
        "{\"use_tool\": true, \"tool_name\": \"<toolname>\", \"tool_prompt\": \"<prompt for the tool>\"}\n"
        "If no tool is necessary, reply with: {\"use_tool\": false}."
    )
    if tool_catalog:
        system_instruction = system_instruction + "\nAvailable tools:\n" + tool_catalog + "\n"
    full_prompt = system_instruction + "\nUser: " + prompt
    payload = {"model": model, "prompt": full_prompt, "stream": False}
    gen_url = mll_url.rstrip("/") + "/api/generate"
    try:
        resp = httpx.post(gen_url, json=payload, timeout=timeout, verify=verify)
        resp.raise_for_status()
        data = None
        text = None
        # Try to get JSON body first, but also capture raw text
        try:
            data = resp.json()
        except Exception:
            pass
        try:
            text = resp.text
        except Exception:
            text = None

        # If JSON structure includes a 'response' field, prefer that
        if isinstance(data, dict) and "response" in data:
            response_text = data["response"]
        elif isinstance(data, str):
            response_text = data
        else:
            response_text = text if text is not None else (json.dumps(data) if data is not None else None)

        if response_text is None:
            return None, text

        # try to parse JSON from response_text
        try:
            parsed = json.loads(response_text)
            return parsed, response_text
        except Exception:
            # attempt to extract JSON substring
            m = re.search(r"\{.*\}", response_text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0)), response_text
                except Exception:
                    return None, response_text
            return None, response_text
    except httpx.HTTPError as e:
        err = f"Model call failed: {e}"
        print(err, file=sys.stderr)
        # return a consistent tuple (decision, raw_text)
        return None, err


def orchestrate_with_tools(mll_url: str, mcp_url: str | None, local_tools: dict[str, Any] | None, user_prompt: str, model: str, timeout: float, verify: bool) -> int:
    # Ask model whether to use a tool
    # build tool catalog string from local_tools if available, else use defaults
    tool_catalog = None
    if local_tools:
        parts = []
        for k, fn in local_tools.items():
            desc = getattr(fn, "__doc__", "").strip() if getattr(fn, "__doc__", None) else ""
            parts.append(f"{k}: {desc}")
        tool_catalog = "\n".join(parts)
    else:
        # if we don't have local tools, we cannot perform orchestration
        display("Cannot load local tools; tool orchestration requires available local tools.")
        return 2

    got = ask_model_for_tool(mll_url, user_prompt, model, timeout, verify, tool_catalog)
    # ensure we always have a (decision, raw) tuple
    if isinstance(got, tuple) and len(got) == 2:
        decision, raw = got
    else:
        # defensive fallback
        decision, raw = None, None
    # show raw model decision only in debug mode
    if DEBUG and raw:
        display("Model decision response (raw):\n" + raw)
    if not decision:
        display("Model did not return a valid tool decision JSON.")
        return 2
    if not decision.get("use_tool"):
        # Model decided no tool; ask model to answer directly
        gen_url = mll_url.rstrip("/") + "/api/generate"
        payload = {"model": model, "prompt": user_prompt, "stream": False}
        return call_generate(gen_url, payload, False, timeout, verify)

    tool_name = decision.get("tool_name")
    tool_prompt = decision.get("tool_prompt", "")
    if not tool_name:
        print("Model requested a tool but did not provide tool_name.", file=sys.stderr)
        return 2

    # Simple heuristic: if user asked for algorithms and model didn't choose tool, force list_algorithms
    if (not decision.get("use_tool")) and ("algorithm" in user_prompt.lower() or "algorithms" in user_prompt.lower()):
        if (local_tools and "list_algorithms" in local_tools) or (not local_tools):
            print("Heuristic: user asked about algorithms; forcing use of 'list_algorithms' tool.")
            tool_name = "list_algorithms"
            tool_prompt = ""

    # invoke tool (local or remote)
    tool_out = None
    if local_tools is not None and tool_name in local_tools:
        # run local tool and capture stdout by executing and returning printed output
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                invoke_local_tool(local_tools, tool_name, tool_prompt)
            tool_out = buf.getvalue()
        finally:
            buf.close()
    else:
        if not mcp_url:
            print("mcp_url is required to call remote tools", file=sys.stderr)
            return 2
        # call remote tool and capture output by calling call_tool which prints to stdout; we can't easily capture that without refactor, so call HTTP directly here
        headers = {"Content-Type": "application/json"}
        try:
            resp = httpx.post(mcp_url.rstrip("/") + f"/api/tool/{tool_name}", headers=headers, json={"model": model, "prompt": tool_prompt, "stream": False}, timeout=timeout, verify=verify)
            resp.raise_for_status()
            try:
                tool_out = json.dumps(resp.json())
            except Exception:
                tool_out = resp.text
        except httpx.HTTPError as e:
            print(f"Remote tool call failed: {e}", file=sys.stderr)
            return 2

    # print tool output for debugging (only when DEBUG)
    if DEBUG and tool_out is not None:
        print("Tool output:\n" + str(tool_out))

    # send tool output back to the model for final answer
    gen_url = mll_url.rstrip("/") + "/api/generate"
    followup = "The tool returned:\n" + (tool_out or "") + "\nUsing that, please answer the original user request: " + user_prompt
    payload = {"model": model, "prompt": followup, "stream": False}
    return call_generate(gen_url, payload, False, timeout, verify)


def call_hkube_endpoint(hkube_base: str, endpoint: str, timeout: float, verify: bool) -> int:
    url = hkube_base.rstrip("/") + endpoint
    try:
        resp = httpx.get(url, timeout=timeout, verify=verify)
        resp.raise_for_status()
        try:
            data = resp.json()
            print_json(data)
        except Exception:
            print(resp.text)
        return 0
    except httpx.HTTPError as e:
        print(f"HKube request failed: {e}", file=sys.stderr)
        return 2



def call_tool(mcp_base: str, tool_name: str, prompt: str, model: str, stream: bool, timeout: float, verify: bool, hkube_url: str | None) -> int:
    """Invoke a tool on the MCP server (no fallbacks)."""
    tool_url = mcp_base.rstrip("/") + f"/api/tool/{tool_name}"
    payload = build_payload(model, prompt, stream)
    headers = {"Content-Type": "application/json"}

    try:
        resp = httpx.post(tool_url, headers=headers, json=payload, timeout=timeout, verify=verify)
        resp.raise_for_status()
        try:
            print_json(resp.json())
        except Exception:
            print(resp.text)
        return 0
    except httpx.HTTPError as e:
        print(f"Tool request failed: {e}", file=sys.stderr)
        return 2


def load_local_tools(server_path: str) -> dict[str, Any]:
    """Dynamically load server.py and return a mapping of tool name -> callable.
    Assumes server.py defines functions with the tool names (e.g., list_algorithms).
    """
    spec = importlib.util.spec_from_file_location("local_server", os.path.abspath(server_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {server_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    tools: dict[str, Any] = {}
    # collect callables with expected names
    for name in ("list_algorithms", "list_pipelines", "say_hello", "quick_hello"):
        if hasattr(module, name):
            tools[name] = getattr(module, name)
    return tools


def invoke_local_tool(tools: dict[str, Any], tool_name: str, prompt: str) -> int:
    if tool_name not in tools:
        print(f"Local tool '{tool_name}' not found", file=sys.stderr)
        return 2
    fn = tools[tool_name]
    # handle async functions
    try:
        if asyncio.iscoroutinefunction(fn):
            result = asyncio.run(fn()) if fn.__code__.co_argcount == 0 else asyncio.run(fn())
        else:
            result = fn() if fn.__code__.co_argcount == 0 else fn()
        # print result
        if result is not None:
            print(result)
        return 0
    except Exception as e:
        print(f"Local tool invocation failed: {e}", file=sys.stderr)
        return 2


def main() -> int:
    args = parse_args()
    # load server path from config.yaml (config.get_config returns a dict)
    _cfg = get_config() or {}
    if not _cfg:
        print("Failed to load configuration (config.yaml) via config.get_config(); exiting.", file=sys.stderr)
        return 2
    server_path = _cfg.get("server_path", "./server.py")
    # assistant name from config
    global ASSISTANT_NAME
    ASSISTANT_NAME = str(_cfg.get("assistant_name", ASSISTANT_NAME))
    # set debug flag from config
    global DEBUG
    DEBUG = bool(_cfg.get("debug", False))
    if DEBUG:
        logging.basicConfig(level=logging.DEBUG)
        # enable httpx debug logs if desired
        logging.getLogger("httpx").setLevel(logging.DEBUG)
        logging.getLogger("httpcore").setLevel(logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
        # ensure httpx/httpcore do not emit debug HTTP Request/Response lines
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
    # Model/LLM URL and model name must be provided in config.yaml
    mll_url = os.getenv("mll_url")
    if not mll_url:
        print("Missing 'mll_url' in config.yaml (required).", file=sys.stderr)
        return 2
    base = mll_url.rstrip("/")
    generate_url = base + "/api/generate"
    model_name = _cfg.get("model")
    if not model_name:
        print("Missing 'model' in config.yaml (required).", file=sys.stderr)
        return 2
    verify = not args.no_verify

    # if requested, launch server.py as a subprocess; auto-enable local-tools
    # always launch server before doing anything; exit on failure
    server_proc = None
    try:
        # ensure no previous server.py processes are running attached to this terminal
        try:
            pids_raw = subprocess.check_output(["pgrep", "-f", "server.py"], text=True).strip().splitlines()
        except subprocess.CalledProcessError:
            pids_raw = []
        pids = []
        for line in pids_raw:
            try:
                pid = int(line.strip())
            except Exception:
                continue
            # skip our current process
            if pid == os.getpid():
                continue
            pids.append(pid)
        if pids:
            print(f"Found existing server.py processes: {pids}. Terminating them to avoid stdin capture.")
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
            # wait briefly and force kill if still alive
            import time

            time.sleep(0.5)
            for pid in pids:
                try:
                    os.kill(pid, 0)
                    # still exists
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except Exception:
                        pass
                except Exception:
                    # process gone
                    pass

        cmd = [sys.executable, server_path]
        server_proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"Launched server process (pid={server_proc.pid})")
        # stream server stdout/stderr to our console in background threads

        def _pipe_reader(pipe, prefix):
            try:
                for line in iter(pipe.readline, ""):
                    if not line:
                        break
                    print(f"[server {prefix}] {line.rstrip()}")
            except Exception:
                pass

        if server_proc.stdout:
            t_out = threading.Thread(target=_pipe_reader, args=(server_proc.stdout, 'OUT'), daemon=True)
            t_out.start()
        if server_proc.stderr:
            t_err = threading.Thread(target=_pipe_reader, args=(server_proc.stderr, 'ERR'), daemon=True)
            t_err.start()
    except Exception as e:
        print(f"Failed to launch server: {e}", file=sys.stderr)
        return 2

    # ensure cleanup on exit
    def _cleanup():
        try:
            if server_proc and server_proc.poll() is None:
                server_proc.terminate()
                server_proc.wait(timeout=5)
        except Exception:
            pass

    atexit.register(_cleanup)
    # also catch SIGINT/SIGTERM to cleanup
    try:
        def _handle(signum, frame):
            _cleanup()
            sys.exit(0)

        signal.signal(signal.SIGINT, _handle)
        signal.signal(signal.SIGTERM, _handle)
    except Exception:
        pass

    # always use local tools (server.py is launched)
    # args.local_tools concept removed; we always attempt to load local tools

    # Always start interactive chat REPL and show options menu
    print("Starting interactive chat against:", generate_url)
    print()
    print("Options:")
    print("- /quit or Ctrl-C to exit.")
    print("- /tools to get all available tools")
    print()
    local_tools = None
    try:
        local_tools = load_local_tools(server_path)
    except Exception as e:
        print(f"Failed to load local tools: {e}", file=sys.stderr)
        local_tools = None
    try:
        while True:
            # blank line before prompt
            print()
            prompt = input("You: ")
            if not prompt:
                continue
            if prompt.strip() in ("/quit", "/exit"):
                break
            # support special /tool command inside REPL
            # list available tools
            if prompt.strip() == "/tools":
                if local_tools:
                    parts = []
                    for name, fn in local_tools.items():
                        desc = getattr(fn, "__doc__", "").strip() if getattr(fn, "__doc__", None) else ""
                        parts.append(f"{name}: {desc}")
                    display("Available tools:\n" + "\n".join(parts))
                else:
                    display("No local tools available")
                continue

            if prompt.startswith("/tool "):
                parts = prompt.split(maxsplit=1)
                if len(parts) == 2 and parts[1].strip():
                    tool_name = parts[1].strip()
                    if local_tools is not None:
                        # call local tool and display result
                        invoke_local_tool(local_tools, tool_name, "")
                    else:
                        display(f"Local tool '{tool_name}' not available")
                    continue
                else:
                    print("Usage: /tool <tool_name>")
                    continue

            # if auto-tools enabled, orchestrate
            if args.auto_tools:
                orchestrate_with_tools(mll_url, None, local_tools, prompt, model_name, args.timeout, verify)
                continue

            payload = build_payload(model_name, prompt, args.stream)
            call_generate(generate_url, payload, args.stream, args.timeout, verify)
    except KeyboardInterrupt:
        print("\nBye")
    return 0

    # single-shot
    # if --tool provided, run tool invocation
    # interactive-only CLI - no single-shot paths
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
