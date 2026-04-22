"""Tests del servidor MCP real (mcp_server_main)."""

from __future__ import annotations

import json

import pytest
from mcp import types

from mcp_server_main import SERVER_NAME, SERVER_VERSION, build_server


def test_server_metadata():
    server = build_server()
    assert server.name == SERVER_NAME
    assert SERVER_VERSION.count(".") >= 1


@pytest.mark.asyncio
async def test_list_tools_returns_four_tools():
    server = build_server()
    handler = server.request_handlers[types.ListToolsRequest]
    result = await handler(types.ListToolsRequest(method="tools/list"))
    names = {t.name for t in result.root.tools}
    assert names == {
        "laboral_calcular_nomina",
        "laboral_consultar_convenio",
        "laboral_calcular_ss",
        "laboral_estimar_irpf",
    }


@pytest.mark.asyncio
async def test_list_tools_schemas_valid_json_schema():
    server = build_server()
    handler = server.request_handlers[types.ListToolsRequest]
    result = await handler(types.ListToolsRequest(method="tools/list"))
    for tool in result.root.tools:
        assert isinstance(tool.description, str) and tool.description.strip()
        schema = tool.inputSchema
        assert schema.get("type") == "object"
        assert "properties" in schema


@pytest.mark.asyncio
async def test_list_resources_returns_three_resources():
    server = build_server()
    handler = server.request_handlers[types.ListResourcesRequest]
    result = await handler(types.ListResourcesRequest(method="resources/list"))
    uris = {str(r.uri) for r in result.root.resources}
    assert uris == {
        "laboral://nominas",
        "laboral://convenios",
        "laboral://seguridad-social",
    }


@pytest.mark.asyncio
async def test_call_tool_calcular_nomina_returns_deterministic_numbers():
    server = build_server()
    handler = server.request_handlers[types.CallToolRequest]
    result = await handler(
        types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="laboral_calcular_nomina",
                arguments={"salario_bruto_anual": 30000, "pagas_extra": 2},
            ),
        )
    )
    assert result.root.content, "MCP call should return content"
    payload = json.loads(result.root.content[0].text)
    # Pagas totales = 12 + 2 = 14; bruto mensual = 30000 / 14 = 2142.86
    assert payload["pagas_totales"] == 14
    assert payload["bruto_mensual"] == "2142.86"
    # Fuente legal explicita
    assert "Orden ISM/31/2026" in payload["ref_legal"]


@pytest.mark.asyncio
async def test_call_tool_calcular_ss_applies_topes():
    server = build_server()
    handler = server.request_handlers[types.CallToolRequest]
    result = await handler(
        types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="laboral_calcular_ss",
                arguments={"base_cotizacion": 999999, "tipo_contrato": "indefinido"},
            ),
        )
    )
    payload = json.loads(result.root.content[0].text)
    topes = payload["topes"]
    # La base aplicada debe estar acotada por el tope maximo
    assert float(payload["base_cotizacion_aplicada"]) <= float(topes["maximo"])
    assert float(payload["base_cotizacion_original"]) == 999999


@pytest.mark.asyncio
async def test_call_tool_unknown_tool_raises_value_error():
    server = build_server()
    handler = server.request_handlers[types.CallToolRequest]
    result = await handler(
        types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="laboral_tool_que_no_existe",
                arguments={},
            ),
        )
    )
    # MCP wraps exceptions into isError=True + error text content
    assert result.root.isError is True
    assert any("laboral_tool_que_no_existe" in c.text for c in result.root.content)


def test_sse_endpoint_bypasses_starlette_request_response_wrapper():
    """Regression test: `Route(endpoint=_SSEEndpoint(...))` must NOT be wrapped
    by Starlette's `request_response()`.

    If Starlette wraps us, it will `await response(scope, receive, send)` after
    our handler returns, producing a duplicate `http.response.start` because
    `SseServerTransport.connect_sse` already sent the SSE response on the raw
    ASGI `send`. Making the endpoint a callable class (not a function) keeps
    Starlette in the ASGI branch (`self.app = endpoint`) and avoids the double
    send.
    """
    from mcp.server.sse import SseServerTransport
    from starlette.routing import Route

    from mcp_server_main import _SSEEndpoint, _initialization_options, build_server

    server = build_server()
    endpoint = _SSEEndpoint(
        SseServerTransport("/messages/"), server, _initialization_options(server)
    )
    route = Route("/sse", endpoint=endpoint)
    assert route.app is endpoint, (
        "Starlette wrapped the endpoint; it will send a duplicate response"
    )


@pytest.mark.asyncio
async def test_call_tool_missing_required_argument_returns_error():
    """No pasa `salario_bruto_anual` → el tool debe devolver error, no crashear."""
    server = build_server()
    handler = server.request_handlers[types.CallToolRequest]
    result = await handler(
        types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="laboral_calcular_nomina",
                arguments={},
            ),
        )
    )
    assert result.root.isError is True
