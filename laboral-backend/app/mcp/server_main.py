"""Servidor MCP real para pgk-laboral-desk (stdio + SSE opcional).

Expone las herramientas definidas en `app.mcp.server.MCP_TOOLS` como un servidor
Model Context Protocol funcional, de forma que hosts como Claude Desktop,
Cursor o ChatGPT Desktop puedan conectarse directamente.

Uso rapido:

  # stdio (para Claude Desktop / Cursor / cualquier host que lance el binario)
  python -m app.mcp.server_main

  # SSE (para hosts que consumen MCP sobre HTTP/SSE, ej. ChatGPT Desktop)
  python -m app.mcp.server_main --transport sse --host 0.0.0.0 --port 8001

Tambien instalable como entry-point `pgk-laboral-mcp` (ver pyproject.toml raiz).

Referencia legal: Orden ISM/31/2026 (BOE-A-2026-1921) + RDL 3/2026
(BOE-A-2026-2548). Las tasas salen siempre de `data/ss_config.json`, nunca
del LLM ni del codigo Python.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from app.mcp.server import MCP_TOOLS, _call_tool

__all__ = [
    "SERVER_NAME",
    "SERVER_VERSION",
    "build_server",
    "run",
    "run_sse",
    "run_stdio",
]

SERVER_NAME = "pgk-laboral-desk"
SERVER_VERSION = "0.2.0"

# Recursos que un host puede listar y leer via MCP.
_RESOURCES: list[dict[str, str]] = [
    {
        "uri": "laboral://nominas",
        "name": "Calculadora de nominas",
        "description": "Desglose de nominas con Seguridad Social e IRPF (2026).",
        "mimeType": "application/json",
    },
    {
        "uri": "laboral://convenios",
        "name": "Convenios colectivos",
        "description": "Tablas salariales de convenios cargados en data/convenio_*.json.",
        "mimeType": "application/json",
    },
    {
        "uri": "laboral://seguridad-social",
        "name": "Seguridad Social 2026",
        "description": "Bases, tipos y topes SS segun Orden ISM/31/2026.",
        "mimeType": "application/json",
    },
]

logger = logging.getLogger("laboral.mcp.server")


def build_server() -> Server:
    """Construye el `Server` MCP con las herramientas y recursos de laboral."""
    server: Server = Server(SERVER_NAME)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in MCP_TOOLS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
        result = await _call_tool(name, arguments or {})
        if "error" in result:
            err = result["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise ValueError(f"{name}: {msg}")

        out: list[types.TextContent] = []
        for item in result.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                out.append(types.TextContent(type="text", text=str(item.get("text", ""))))
        if not out:
            out.append(types.TextContent(type="text", text="{}"))
        return out

    @server.list_resources()
    async def list_resources() -> list[types.Resource]:
        return [
            types.Resource(
                uri=r["uri"],  # type: ignore[arg-type]
                name=r["name"],
                description=r["description"],
                mimeType=r["mimeType"],
            )
            for r in _RESOURCES
        ]

    return server


def _initialization_options(server: Server) -> InitializationOptions:
    return InitializationOptions(
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )


async def run_stdio() -> None:
    """Ejecuta el servidor MCP sobre stdio (transporte por defecto)."""
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, _initialization_options(server))


class _SSEEndpoint:
    """ASGI endpoint para el handshake SSE del servidor MCP.

    Se implementa como *callable-class* (no funcion) a proposito: Starlette
    envuelve los `Route(endpoint=<funcion>)` con `request_response()`, que al
    terminar el handler llama `await response(scope, receive, send)` sobre el
    `Response()` devuelto. Pero `SseServerTransport.connect_sse` **ya** envia
    un `http.response.start` + body por el `send` ASGI crudo dentro del
    `async with`. Devolver un `Response()` provoca un segundo
    `http.response.start` y `RuntimeError` en uvicorn en cada desconexion SSE.

    Al pasar una instancia de clase (no funcion), `starlette.routing.Route`
    entra en la rama ASGI (`self.app = endpoint`) y no re-envuelve con
    `request_response`, evitando el envio duplicado.
    """

    def __init__(self, sse: Any, server: Server, init_options: InitializationOptions) -> None:
        self._sse = sse
        self._server = server
        self._init_options = init_options

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        async with self._sse.connect_sse(scope, receive, send) as (
            read_stream,
            write_stream,
        ):
            await self._server.run(read_stream, write_stream, self._init_options)


async def run_sse(host: str = "127.0.0.1", port: int = 8001) -> None:
    """Ejecuta el servidor MCP sobre SSE (HTTP).

    Requiere `starlette` y `uvicorn` (ambos ya son deps transitivas de `mcp`).
    """
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route

    server = build_server()
    init_options = _initialization_options(server)
    sse = SseServerTransport("/messages/")

    app = Starlette(
        debug=False,
        routes=[
            # methods=["GET"] explicit: Starlette only auto-sets {"GET","HEAD"}
            # when the endpoint is a function; for an ASGI class instance it
            # leaves methods=None, which would silently route POST/DELETE/... to
            # our SSE handler and crash inside connect_sse.
            Route(
                "/sse",
                endpoint=_SSEEndpoint(sse, server, init_options),
                methods=["GET"],
            ),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    uvicorn_server = uvicorn.Server(config)
    await uvicorn_server.serve()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pgk-laboral-mcp",
        description="Servidor MCP para pgk-laboral-desk (stdio | sse).",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transporte MCP. 'stdio' (default) para Claude Desktop / Cursor; "
        "'sse' para hosts HTTP.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host SSE (default 127.0.0.1).")
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Puerto SSE (default 8001). Evita colision con app.py Flask en 8765.",
    )
    parser.add_argument("--debug", action="store_true", help="Logging nivel DEBUG.")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> None:
    """Entry-point sincrono. Usado por `[project.scripts] pgk-laboral-mcp`."""
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.transport == "sse":
        asyncio.run(run_sse(host=args.host, port=args.port))
    else:
        asyncio.run(run_stdio())


if __name__ == "__main__":
    run()
