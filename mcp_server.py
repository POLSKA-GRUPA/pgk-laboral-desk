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
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

logger = logging.getLogger("laboral.mcp")

# ── Cargar tasas SS desde fuente de verdad (data/ss_config.json) ────
# Ref: Orden PJC/297/2026 (BOE-A-2026-7296) + RDL 3/2026 (BOE-A-2026-2548)

_SS_CONFIG_PATH = Path(__file__).parent / "data" / "ss_config.json"


def _load_ss_config() -> dict[str, object]:
    """Carga tasas SS desde data/ss_config.json.

    Fail-fast: si el JSON falta o esta corrupto lanzamos en import del
    modulo. AGENTS.md regla 8 prohibe hardcodear numeros fiscales fuera de
    `data/`; un servidor MCP con topes incorrectos es peor que uno que se
    niega a arrancar (el host IA recibiria calculos erroneos como si
    fueran oficiales). Claude/Cursor mostraran el error de import claro
    en el log del MCP y el usuario sabra que ha pasado.
    """
    try:
        with open(_SS_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"No se pudo cargar {_SS_CONFIG_PATH}: {e}. "
            "El servidor MCP no puede arrancar sin tasas SS verificadas."
        ) from e


_SS_CONFIG = _load_ss_config()


def _require_section(section: str) -> dict[str, object]:
    raw = _SS_CONFIG.get(section)
    if not isinstance(raw, dict):
        raise RuntimeError(
            f"ss_config.json: seccion '{section}' ausente o invalida. "
            "Revisa data/ss_config.json contra la Orden de cotizacion vigente."
        )
    return raw


def _ss_rate(section: str, key: str) -> Decimal:
    """Obtiene una tasa SS del config como Decimal (en tanto por uno).

    Fail-fast si la clave no existe: preferimos no calcular a calcular mal.
    """
    sec = _require_section(section)
    if key not in sec:
        raise RuntimeError(
            f"ss_config.json: falta '{section}.{key}'. "
            "Revisa data/ss_config.json contra la Orden de cotizacion vigente."
        )
    return Decimal(str(sec[key])) / Decimal("100")


def _ss_topes() -> tuple[Decimal, Decimal]:
    """Devuelve (base_min, base_max) mensuales en Decimal."""
    topes = _require_section("topes")
    missing = [k for k in ("base_min_mensual", "base_max_mensual") if k not in topes]
    if missing:
        raise RuntimeError(
            f"ss_config.json: faltan topes {missing}. "
            "Revisa data/ss_config.json contra la Orden de cotizacion vigente."
        )
    return Decimal(str(topes["base_min_mensual"])), Decimal(str(topes["base_max_mensual"]))


# ── MCP Tool Schemas ──────────────────────────────────────────────

MCP_TOOLS = [
    {
        "name": "laboral_calcular_nomina",
        "description": (
            "Calcular desglose de nomina: salario bruto y deducciones SS. "
            "IRPF y salario neto requieren laboral_estimar_irpf por separado."
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
            "Estimar retencion IRPF de un trabajador segun su situacion personal y familiar."
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
    method: str, params: dict[str, object] | None = None
) -> dict[str, object]:
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


async def _call_tool(name: str, arguments: dict[str, object]) -> dict[str, object]:
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


def _calcular_nomina(arguments: dict[str, object]) -> dict[str, object]:
    """Calcular desglose de nomina.

    Tasas: Orden PJC/297/2026 (BOE-A-2026-7296)
    """
    bruto_anual = Decimal(str(arguments["salario_bruto_anual"]))
    pagas_raw = arguments.get("pagas_extra")
    pagas = int(pagas_raw) if pagas_raw is not None else 2
    total_pagas = 12 + pagas
    bruto_mensual = (bruto_anual / Decimal(str(total_pagas))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Aplicar topes de cotizacion — Orden PJC/297/2026 (BOE-A-2026-7296)
    base_min, base_max = _ss_topes()
    base_cotizacion = max(base_min, min(base_max, bruto_mensual))

    # Tasas trabajador desde ss_config.json — Orden PJC/297/2026 (BOE-A-2026-7296)
    tasa_cc = _ss_rate("trabajador", "contingencias_comunes")
    tasa_desempleo = _ss_rate("trabajador", "desempleo_indefinido")
    tasa_fp = _ss_rate("trabajador", "formacion_profesional")
    tasa_mei = _ss_rate("trabajador", "mei")

    ss_trabajador = (base_cotizacion * tasa_cc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    desempleo = (base_cotizacion * tasa_desempleo).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    formacion = (base_cotizacion * tasa_fp).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    mei = (base_cotizacion * tasa_mei).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    total_deducciones_ss = ss_trabajador + desempleo + formacion + mei

    resultado = {
        "salario_bruto_anual": str(bruto_anual),
        "pagas_totales": total_pagas,
        "bruto_mensual": str(bruto_mensual),
        "deducciones_ss": {
            "contingencias_comunes": str(ss_trabajador),
            "desempleo": str(desempleo),
            "formacion_profesional": str(formacion),
            "mei": str(mei),
            "total_ss": str(total_deducciones_ss),
        },
        "ref_legal": "Orden PJC/297/2026 (BOE-A-2026-7296)",
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


def _consultar_convenio(arguments: dict[str, object]) -> dict[str, object]:
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


def _calcular_ss(arguments: dict[str, object]) -> dict[str, object]:
    """Calcular cuotas Seguridad Social.

    Tasas empresa: Orden PJC/297/2026 (BOE-A-2026-7296)
    """
    base_raw = Decimal(str(arguments["base_cotizacion"]))
    tipo_contrato = str(arguments.get("tipo_contrato", "indefinido") or "indefinido")

    # Aplicar topes de cotizacion — Orden PJC/297/2026 (BOE-A-2026-7296)
    base_min, base_max = _ss_topes()
    base = max(base_min, min(base_max, base_raw))

    # Tasas empresa desde ss_config.json — Orden PJC/297/2026 (BOE-A-2026-7296)
    tasa_cc = _ss_rate("empresa", "contingencias_comunes")
    if tipo_contrato in ("indefinido", "practicas", "formacion"):
        tasa_desempleo = _ss_rate("empresa", "desempleo_indefinido")
    else:
        tasa_desempleo = _ss_rate("empresa", "desempleo_temporal")
    tasa_fp = _ss_rate("empresa", "formacion_profesional")
    tasa_fogasa = _ss_rate("empresa", "fogasa")
    tasa_mei = _ss_rate("empresa", "mei")

    cc_empresa = (base * tasa_cc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    desempleo_empresa = (base * tasa_desempleo).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    formacion_empresa = (base * tasa_fp).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fogasa = (base * tasa_fogasa).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    mei_empresa = (base * tasa_mei).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    total_empresa = cc_empresa + desempleo_empresa + formacion_empresa + fogasa + mei_empresa

    resultado = {
        "base_cotizacion_original": str(base_raw),
        "base_cotizacion_aplicada": str(base),
        "topes": {"minimo": str(base_min), "maximo": str(base_max)},
        "tipo_contrato": tipo_contrato,
        "cuotas_empresa": {
            "contingencias_comunes": str(cc_empresa),
            "desempleo": str(desempleo_empresa),
            "formacion": str(formacion_empresa),
            "fogasa": str(fogasa),
            "mei": str(mei_empresa),
            "total": str(total_empresa),
        },
        "ref_legal": "Orden PJC/297/2026 (BOE-A-2026-7296)",
        "nota": "Tasas SS 2026 cargadas desde data/ss_config.json.",
    }

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(resultado, ensure_ascii=False, indent=2),
            }
        ]
    }


def _estimar_irpf(arguments: dict[str, object]) -> dict[str, object]:
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
