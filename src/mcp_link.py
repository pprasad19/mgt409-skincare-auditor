"""Attach the MCP server to an agent, or carry on without it.

The agents can look an ingredient up mid-task through the same tools any
other MCP client would use. They do not need to — the engine computes the
verdict either way — so a server that fails to start costs a capability, not
an audit.

That fallback is the whole reason this file is separate. A spawned subprocess
is the least reliable thing in the system: it depends on a path resolving, an
interpreter existing, and a handshake completing, and the project is graded in
part on a stranger getting this running inside ten minutes on a machine
nobody has seen. Optional-with-a-fallback is the only shape that is worth
having here.

Paths in .mcp.json are relative to the repo root on purpose, so the file
stays valid for other MCP clients. They are resolved against the root here
rather than the working directory, which is what stops the spawn failing with
"the system cannot find the file specified" when the process was started from
somewhere else — the same trap the Homework 5 code documents.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".mcp.json"

_warned = False


def _resolve(value: str) -> str:
    path = ROOT / value
    return str(path) if path.exists() else value


def load_toolsets() -> list:
    """Return MCP toolsets, or an empty list if the server cannot be reached.

    Never raises. Every failure here is survivable, and none of them should
    take an audit down with it.
    """
    global _warned
    try:
        from fastmcp.client.transports import StdioTransport
        from pydantic_ai.mcp import MCPToolset

        if not CONFIG.is_file():
            return []
        config = json.loads(CONFIG.read_text(encoding="utf-8"))

        toolsets = []
        for name, server in (config.get("mcpServers") or {}).items():
            command = server.get("command")
            if not command:
                continue
            # On Windows the child needs the real environment; a bare env
            # strips PATH and SystemRoot and the spawn fails obscurely.
            env = {**os.environ, **(server.get("env") or {})}
            transport = StdioTransport(
                command=_resolve(command),
                args=[_resolve(a) for a in (server.get("args") or [])],
                env=env,
                cwd=str(ROOT),
            )
            toolsets.append(MCPToolset(transport, id=name))
        return toolsets

    except Exception as exc:  # noqa: BLE001
        if not _warned:
            print(
                f"[mcp] tools unavailable, continuing without them: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            _warned = True
        return []
