"""MCP Server — Expone capacidades de pgk-laboral-desk como herramientas MCP.

Patron inspirado en cross-validated-search/mcp_server.py (wd041216-bit).
Permite que Claude/Cursor/PGK-Despacho-Desktop interactuen con
el asistente laboral via Model Context Protocol.

Herramientas expuestas:
- laboral_calcular_nomina: Calcular desglose de nomina
- laboral_consultar_convenio: Consultar tablas salariales de convenio
- laboral_calcular_ss: Calcular cuotas Seguridad Social
- laboral_estimar_irpf: Estimar retencion IRPF de un trabajador
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("laboral.mcp")


# ── MCP Tool Schemas ──────────────────────────────────────────────

MCP_TOOLS = [
    {
        "name": "laboral_calcular_nomina",
        "description": (
            "Calcular desglose de nomina: salario bruto, deducciones SS, "
            "retencion IRPF, salario neto."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "salario_bruto_anual": {
                    "type": "number",
                    "description": "Salario bruto anual en euros",
                },
                "categoria": {
                    "type": "string",
                    "description": "Categoria profesional (ej: 'ingeniero', 'administrativo')",
                },
                "pagas_extra": {
                    "type": "integer",
                    "description": "Numero de pagas extra (default 2)",
                },
            },
            "required": ["salario_bruto_anual"],
        },
    },
    {
        "name": "laboral_consultar_convenio",
        "description": (
            "Consultar tablas salariales de un convenio colectivo. "
            "Devuelve salario base, pluses y complementos por categoria."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "convenio": {
                    "type": "string",
                    "description": "Nombre o codigo del convenio colectivo",
                },
                "categoria": {
                    "type": "string",
                    "description": "Categoria o grupo profesional (opcional)",
                },
            },
            "required": ["convenio"],
        },
    },
    {
        "name": "laboral_calcular_ss",
        "description": (
            "Calcular cuotas de Seguridad Social para un trabajador. "
            "Incluye contingencias comunes, desempleo, formacion, FOGASA."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "base_cotizacion": {
                    "type": "number",
                    "description": "Base de cotizacion mensual en euros",
                },
                "tipo_contrato": {
                    "type": "string",
                    "description": "Tipo de contrato",
                    "enum": ["indefinido", "temporal", "practicas", "formacion"],
                },
            },
            "required": ["base_cotizacion"],
        },
    },
    {
        "name": "laboral_estimar_irpf",
        "description": (
            "Estimar retencion IRPF de un trabajador segun su situacion "
            "personal y familiar."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "salario_bruto_anual": {
                    "type": "number",
                    "description": "Salario bruto anual en euros",
                },
                "situacion_familiar": {
                    "type": "string",
                    "description": "Situacion: soltero, casado_1_perceptor, casado_2_perceptores",
                    "enum": [
                        "soltero",
                        "casado_1_perceptor",
                        "casado_2_perceptores",
                    ],
                },
                "hijos": {
                    "type": "integer",
                    "description": "Numero de hijos (default 0)",
                },
                "discapacidad": {
                    "type": "integer",
                    "description": "Porcentaje de discapacidad (default 0)",
                },
            },
            "required": ["salario_bruto_anual"],
        },
    },
]


# ── MCP Request Handler ──────────────────────────────────────────


async def handle_mcp_request(
    method: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Handle an MCP protocol request.

    Supports: tools/list, tools/call, resources/list
    """
    params = params or {}

    if method == "tools/list":
        return {"tools": MCP_TOOLS}

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        return await _call_tool(tool_name, arguments)

    if method == "resources/list":
        return {
            "resources": [
                {
                    "uri": "laboral://nominas",
                    "name": "Calculadora de Nominas",
                    "description": "Desglose de nominas con SS e IRPF",
                    "mimeType": "application/json",
                },
                {
                    "uri": "laboral://convenios",
                    "name": "Convenios Colectivos",
                    "description": "Tablas salariales de convenios colectivos",
                    "mimeType": "application/json",
                },
                {
                    "uri": "laboral://seguridad-social",
                    "name": "Seguridad Social",
                    "description": "Bases y tipos de cotizacion SS",
                    "mimeType": "application/json",
                },
            ]
        }

    return {"error": {"code": -32601, "message": f"Method not found: {method}"}}


async def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute an MCP tool and return the result."""
    try:
        if name == "laboral_calcular_nomina":
            return _calcular_nomina(arguments)

        if name == "laboral_consultar_convenio":
            return _consultar_convenio(arguments)

        if name == "laboral_calcular_ss":
            return _calcular_ss(arguments)

        if name == "laboral_estimar_irpf":
            return _estimar_irpf(arguments)

        return {"error": {"code": -32602, "message": f"Unknown tool: {name}"}}

    except Exception as e:
        logger.error("MCP tool error %s: %s", name, e)
        return {"error": {"code": -32603, "message": str(e)}}


def _calcular_nomina(arguments: dict[str, Any]) -> dict[str, Any]:
    """Calcular desglose de nomina."""
    bruto_anual = arguments["salario_bruto_anual"]
    pagas = arguments.get("pagas_extra", 2)
    total_pagas = 12 + pagas
    bruto_mensual = bruto_anual / total_pagas

    # Contingencias comunes trabajador: 4.70%
    ss_trabajador = bruto_mensual * 0.0470
    # Desempleo trabajador (indefinido): 1.55%
    desempleo = bruto_mensual * 0.0155
    # Formacion profesional: 0.10%
    formacion = bruto_mensual * 0.001
    # MEI trabajador: 0.15%
    mei = bruto_mensual * 0.0015

    total_deducciones_ss = ss_trabajador + desempleo + formacion + mei

    resultado = {
        "salario_bruto_anual": bruto_anual,
        "pagas_totales": total_pagas,
        "bruto_mensual": round(bruto_mensual, 2),
        "deducciones_ss": {
            "contingencias_comunes": round(ss_trabajador, 2),
            "desempleo": round(desempleo, 2),
            "formacion_profesional": round(formacion, 2),
            "mei": round(mei, 2),
            "total_ss": round(total_deducciones_ss, 2),
        },
        "nota": (
            "Conectar con irpf_estimator.py para calculo exacto de retencion IRPF. "
            "Conectar con ss_calculator.py para bases y tipos actualizados."
        ),
    }

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(resultado, ensure_ascii=False, indent=2),
            }
        ]
    }


def _consultar_convenio(arguments: dict[str, Any]) -> dict[str, Any]:
    """Consultar tablas salariales de convenio."""
    convenio = arguments["convenio"]
    categoria = arguments.get("categoria")

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "convenio": convenio,
                        "categoria": categoria,
                        "nota": (
                            "Conectar con convenio_verifier.py para verificar "
                            "tablas salariales del convenio solicitado."
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            }
        ]
    }


def _calcular_ss(arguments: dict[str, Any]) -> dict[str, Any]:
    """Calcular cuotas Seguridad Social."""
    base = arguments["base_cotizacion"]
    tipo_contrato = arguments.get("tipo_contrato", "indefinido")

    # Tipos SS empresa (general)
    cc_empresa = base * 0.2360  # Contingencias comunes
    desempleo_empresa = base * (0.0550 if tipo_contrato == "indefinido" else 0.0670)
    formacion_empresa = base * 0.006
    fogasa = base * 0.002
    mei_empresa = base * 0.0075  # MEI empresa

    total_empresa = cc_empresa + desempleo_empresa + formacion_empresa + fogasa + mei_empresa

    resultado = {
        "base_cotizacion": base,
        "tipo_contrato": tipo_contrato,
        "cuotas_empresa": {
            "contingencias_comunes": round(cc_empresa, 2),
            "desempleo": round(desempleo_empresa, 2),
            "formacion": round(formacion_empresa, 2),
            "fogasa": round(fogasa, 2),
            "mei": round(mei_empresa, 2),
            "total": round(total_empresa, 2),
        },
        "nota": "Tipos SS 2026. Verificar con ss_calculator.py para datos actualizados.",
    }

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(resultado, ensure_ascii=False, indent=2),
            }
        ]
    }


def _estimar_irpf(arguments: dict[str, Any]) -> dict[str, Any]:
    """Estimar retencion IRPF."""
    bruto = arguments["salario_bruto_anual"]
    situacion = arguments.get("situacion_familiar", "soltero")
    hijos = arguments.get("hijos", 0)

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "salario_bruto_anual": bruto,
                        "situacion_familiar": situacion,
                        "hijos": hijos,
                        "nota": (
                            "Conectar con irpf_estimator.py para calculo exacto "
                            "de retencion IRPF con tablas 2026 actualizadas."
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            }
        ]
    }
