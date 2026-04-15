"""CodeAct Agent para PGK Laboral Desk.

Implementa la arquitectura CodeAct (usada por Manus.im) sobre LangGraph:
el LLM escribe código Python ejecutable que llama a las herramientas del motor
laboral, en vez de generar JSON de tool-calling.

Ventajas:
- Combina múltiples herramientas en un solo paso
- Razonamiento complejo (comparaciones, optimizaciones)
- Variables persistentes entre turnos
- Cualquier pregunta en lenguaje natural (no limitado a regex)
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import io
import logging
import os
import re
from typing import Any

from app.services.engine import LaboralEngine

logger = logging.getLogger("laboral.agent")

# ---------------------------------------------------------------------------
# Modelo LLM
# ---------------------------------------------------------------------------

_SAFE_BUILTINS = {
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "divmod",
    "enumerate",
    "filter",
    "float",
    "format",
    "frozenset",
    "int",
    "isinstance",
    "issubclass",
    "iter",
    "len",
    "list",
    "map",
    "max",
    "min",
    "next",
    "print",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "slice",
    "sorted",
    "str",
    "sum",
    "tuple",
    "type",
    "zip",
    "True",
    "False",
    "None",
}


def _get_model():
    """Inicializa el modelo LLM según las API keys disponibles."""
    # Intentar Google Gemini primero
    google_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if google_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            model_name = os.environ.get("DEFAULT_MODEL", "gemini-2.5-flash")
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=google_key,
                temperature=0.1,
                max_output_tokens=4096,
            )
        except Exception:
            logger.warning("Google Gemini no disponible, intentando Anthropic...")

    # Intentar Anthropic (via z.ai proxy o directo)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            from langchain_anthropic import ChatAnthropic

            base_url = os.environ.get("ANTHROPIC_BASE_URL")
            kwargs: dict[str, Any] = {
                "model": "claude-sonnet-4-20250514",
                "api_key": anthropic_key,
                "temperature": 0.1,
                "max_tokens": 4096,
            }
            if base_url:
                kwargs["base_url"] = base_url
            return ChatAnthropic(**kwargs)
        except Exception:
            logger.warning("Anthropic no disponible.")

    return None


# ---------------------------------------------------------------------------
# Sandbox seguro para ejecución de código
# ---------------------------------------------------------------------------


_BLOCKED_DUNDERS = {
    "__class__",
    "__bases__",
    "__subclasses__",
    "__globals__",
    "__init__",
    "__mro__",
    "__dict__",
    "__import__",
    "__builtins__",
    "__loader__",
    "__spec__",
    "__code__",
    "__func__",
    "__self__",
    "__module__",
    "__qualname__",
    "__reduce__",
    "__reduce_ex__",
    "__getattr__",
    "__setattr__",
    "__delattr__",
}


def _validate_code_safety(code: str) -> str | None:
    """Analiza el AST del código para bloquear accesos a atributos dunder peligrosos.

    Returns None if safe, or an error message if unsafe.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr.startswith("__")
            and node.attr.endswith("__")
            and node.attr in _BLOCKED_DUNDERS
        ):
            return f"Acceso bloqueado a atributo restringido: {node.attr}"
        if isinstance(node, ast.Name) and node.id == "__import__":
            return "Uso de __import__ no permitido"
    return None


def _create_sandbox(tools_context: dict[str, Any]):
    """Crea un entorno de ejecución restringido con las herramientas disponibles."""

    safe_builtins_dict = {k: getattr(builtins, k) for k in _SAFE_BUILTINS if hasattr(builtins, k)}

    def execute(code: str, _locals: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        # AST validation to block sandbox escape via dunder introspection
        safety_error = _validate_code_safety(code)
        if safety_error:
            return f"Error de seguridad: {safety_error}", {}

        original_keys = set(_locals.keys())
        sandbox_globals = {**safe_builtins_dict, "__builtins__": safe_builtins_dict}
        sandbox_locals = {**_locals, **tools_context}

        try:
            with contextlib.redirect_stdout(io.StringIO()) as f:
                exec(code, sandbox_globals, sandbox_locals)
            result = f.getvalue()
            if not result:
                result = "<código ejecutado, sin output>"
        except Exception as e:
            result = f"Error: {e!r}"

        new_keys = set(sandbox_locals.keys()) - original_keys - set(tools_context.keys())
        new_vars = {key: sandbox_locals[key] for key in new_keys}
        return result, new_vars

    return execute


# ---------------------------------------------------------------------------
# Herramientas del motor laboral
# ---------------------------------------------------------------------------


def _build_tools(engine: LaboralEngine) -> dict[str, Any]:
    """Construye las herramientas disponibles para el agente."""

    def simular_contrato(
        categoria: str,
        tipo_contrato: str = "indefinido",
        horas_semanales: float = 40.0,
        antiguedad_anos: int = 0,
        extras_prorrateadas: bool = False,
        num_hijos: int = 0,
        hijos_menores_3: int = 0,
        region: str = "generica",
    ) -> dict:
        """Simula el coste completo de contratar a un trabajador.

        Args:
            categoria: Categoría profesional (ej: 'Nivel A.', 'Nivel B.', 'Socorrista correturnos.')
            tipo_contrato: 'indefinido', 'temporal', 'fijo-discontinuo', 'sustitucion'
            horas_semanales: Horas por semana (40=completa, 20=media jornada)
            antiguedad_anos: Años de antigüedad del trabajador
            extras_prorrateadas: True para prorratear pagas extras en 12 meses
            num_hijos: Número de hijos (afecta IRPF)
            hijos_menores_3: Hijos menores de 3 años (afecta IRPF)
            region: Región IRPF ('generica', 'madrid', 'cataluna', 'andalucia', 'valencia')

        Returns:
            dict con: coste_total_empresa_mes_eur, bruto_mensual_eur, neto_mensual_eur,
                      ss_empresa_mes_eur, ss_trabajador_mes_eur, irpf_retencion_pct, etc.
        """
        return engine.simulate(
            category=categoria,
            contract_type=tipo_contrato,
            weekly_hours=horas_semanales,
            seniority_years=antiguedad_anos,
            extras_prorated=extras_prorrateadas,
            num_children=num_hijos,
            children_under_3=hijos_menores_3,
            region=region,
        )

    def buscar_por_presupuesto(
        categoria: str,
        presupuesto_maximo_mes: float,
        antiguedad_anos: int = 0,
        region: str = "generica",
    ) -> dict:
        """Busca combinaciones de contrato/jornada que caben en un presupuesto.

        Args:
            categoria: Categoría profesional
            presupuesto_maximo_mes: Máximo coste empresa al mes en euros
            antiguedad_anos: Años de antigüedad
            region: Región IRPF

        Returns:
            dict con: opciones (lista de combinaciones), mensaje
        """
        return engine.find_contracts_by_budget(
            category=categoria,
            max_monthly_cost=presupuesto_maximo_mes,
            seniority_years=antiguedad_anos,
            region=region,
        )

    def calcular_despido(
        tipo_despido: str,
        fecha_inicio: str,
        salario_bruto_mensual: float,
        fecha_despido: str = "",
        dias_vacaciones_pendientes: int = 0,
        horas_semanales: float = 40.0,
    ) -> dict:
        """Calcula el coste de un despido/extinción laboral.

        Args:
            tipo_despido: 'improcedente', 'objetivo', 'disciplinario', 'voluntario',
                          'mutuo_acuerdo', 'ere', 'fin_contrato_temporal'
            fecha_inicio: Fecha inicio contrato (ISO: 'YYYY-MM-DD')
            salario_bruto_mensual: Salario bruto mensual en euros
            fecha_despido: Fecha del despido (ISO), vacío = hoy
            dias_vacaciones_pendientes: Días de vacaciones sin disfrutar
            horas_semanales: Horas semanales del contrato

        Returns:
            dict con: indemnizacion_eur, finiquito, total_eur, escenarios, consejo
        """
        return engine.calcular_despido(
            tipo_despido=tipo_despido,
            fecha_inicio=fecha_inicio,
            salario_bruto_mensual=salario_bruto_mensual,
            fecha_despido=fecha_despido or None,
            dias_vacaciones_pendientes=dias_vacaciones_pendientes,
            weekly_hours=horas_semanales,
        )

    def listar_categorias() -> list[dict]:
        """Lista todas las categorías profesionales disponibles en el convenio.

        Returns:
            Lista de dicts con: value (nombre exacto), label (nombre para mostrar)
        """
        return engine.get_categories()

    def listar_tipos_contrato() -> list[dict]:
        """Lista los tipos de contrato disponibles.

        Returns:
            Lista de dicts con: value, label
        """
        return engine.get_contract_types()

    def info_convenio() -> dict:
        """Devuelve información del convenio colectivo aplicable.

        Returns:
            dict con: nombre, ambito, vigencia, secciones
        """
        convenio = engine.data.get("convenio", {})
        return {
            "nombre": convenio.get("nombre", ""),
            "ambito": convenio.get("ambito", ""),
            "vigencia": f"{convenio.get('vigencia_desde_ano', '?')}–{convenio.get('vigencia_hasta_ano', '?')}",
            "pagas": engine._convenio_pagas,
            "num_categorias": len(engine.salary_rows),
        }

    def listar_tipos_despido() -> list[dict]:
        """Lista los tipos de despido/extinción laboral disponibles.

        Returns:
            Lista de dicts con: value, label, descripcion, dias_por_año
        """
        return engine.get_tipos_despido()

    return {
        "simular_contrato": simular_contrato,
        "buscar_por_presupuesto": buscar_por_presupuesto,
        "calcular_despido": calcular_despido,
        "listar_categorias": listar_categorias,
        "listar_tipos_contrato": listar_tipos_contrato,
        "listar_tipos_despido": listar_tipos_despido,
        "info_convenio": info_convenio,
    }


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """Eres un experto en derecho laboral español y asesor de contratación.
Trabajas para la empresa que usa el convenio colectivo: {convenio_nombre}.
Vigencia: {convenio_vigencia}. Pagas: {convenio_pagas}.

Tu trabajo es ayudar al usuario a:
1. Calcular el coste de contratar trabajadores
2. Buscar opciones dentro de un presupuesto
3. Calcular costes de despido/extinción
4. Explicar conceptos laborales españoles
5. Comparar diferentes escenarios de contratación

REGLAS IMPORTANTES:
- Responde SIEMPRE en español
- Usa las herramientas disponibles para hacer cálculos reales (no inventes números)
- Cuando muestres resultados, formatea los importes como "1.234,56 €"
- Cita artículos del convenio o del ET cuando sea relevante
- Si el usuario pide algo que no puedes calcular, explica por qué
- Para comparaciones, llama a simular_contrato varias veces y presenta una tabla
- Sé conciso pero completo

HERRAMIENTAS DISPONIBLES (llama desde código Python):

```
def simular_contrato(categoria, tipo_contrato='indefinido', horas_semanales=40.0,
                     antiguedad_anos=0, extras_prorrateadas=False, num_hijos=0,
                     hijos_menores_3=0, region='generica') -> dict:
    \"\"\"Simula coste completo de contratación. Devuelve dict con:
    coste_total_empresa_mes_eur, bruto_mensual_eur, neto_mensual_eur,
    ss_empresa_mes_eur, ss_trabajador_mes_eur, irpf_retencion_pct, irpf_mensual_eur,
    coste_total_empresa_anual_eur, devengos, ss_detalle, etc.\"\"\"

def buscar_por_presupuesto(categoria, presupuesto_maximo_mes, antiguedad_anos=0,
                           region='generica') -> dict:
    \"\"\"Busca combinaciones contrato/jornada dentro del presupuesto. Devuelve dict con:
    opciones (lista), mensaje\"\"\"

def calcular_despido(tipo_despido, fecha_inicio, salario_bruto_mensual,
                     fecha_despido='', dias_vacaciones_pendientes=0,
                     horas_semanales=40.0) -> dict:
    \"\"\"Calcula coste despido. Devuelve dict con: indemnizacion_eur, finiquito, total_eur,
    escenarios, consejo\"\"\"

def listar_categorias() -> list[dict]:
    \"\"\"Lista categorías profesionales disponibles.\"\"\"

def listar_tipos_contrato() -> list[dict]:
    \"\"\"Lista tipos de contrato disponibles.\"\"\"

def listar_tipos_despido() -> list[dict]:
    \"\"\"Lista tipos de despido/extinción.\"\"\"

def info_convenio() -> dict:
    \"\"\"Info del convenio colectivo aplicable.\"\"\"
```

CATEGORÍAS DISPONIBLES:
{categorias_lista}

TIPOS DE CONTRATO: indefinido, temporal, fijo-discontinuo, sustitucion, temporal-produccion

Para hacer cálculos, escribe código Python en un bloque ```python ... ```.
Usa print() para mostrar resultados. Las variables se mantienen entre turnos.

Cuando tengas el resultado, formatea una respuesta clara para el usuario.
NO uses código si la pregunta es puramente informativa (ej: "¿qué tipos de contrato hay?").
"""


def _build_system_prompt(engine: LaboralEngine) -> str:
    convenio = engine.data.get("convenio", {})
    cats = engine.get_categories()
    cats_str = "\n".join(f"- {c['label']}" for c in cats)
    return _SYSTEM_PROMPT_TEMPLATE.format(
        convenio_nombre=convenio.get("nombre", "N/A"),
        convenio_vigencia=f"{convenio.get('vigencia_desde_ano', '?')}–{convenio.get('vigencia_hasta_ano', '?')}",
        convenio_pagas=engine._convenio_pagas,
        categorias_lista=cats_str,
    )


# ---------------------------------------------------------------------------
# CodeAct Agent (implementación directa, sin dependencia del paquete archivado)
# ---------------------------------------------------------------------------

_CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


class LaboralAgent:
    """Agente CodeAct para consultas laborales."""

    def __init__(self, engine: LaboralEngine) -> None:
        self.engine = engine
        self.model = _get_model()
        self.tools = _build_tools(engine)
        self.system_prompt = _build_system_prompt(engine)
        self._sandbox_fn = _create_sandbox(self.tools)

        if self.model is None:
            logger.warning("No hay modelo LLM disponible. El agente no funcionará.")

    @property
    def available(self) -> bool:
        """True si hay un modelo LLM configurado."""
        return self.model is not None

    def chat(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Procesa un mensaje del usuario y devuelve la respuesta.

        Args:
            message: Mensaje del usuario
            history: Historial de mensajes [{"role": "user"/"assistant", "content": "..."}]
            context: Variables persistentes entre turnos

        Returns:
            dict con: response (str), context (dict), tool_calls (list)
        """
        if not self.available:
            return {
                "response": "El agente IA no está disponible. Configura GOOGLE_API_KEY o ANTHROPIC_API_KEY.",
                "context": context or {},
                "tool_calls": [],
            }

        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        ctx = dict(context) if context else {}
        tool_calls: list[dict[str, str]] = []
        max_iterations = 5

        for _iteration in range(max_iterations):
            response = self.model.invoke(messages)
            content = response.content if hasattr(response, "content") else str(response)

            # Extraer bloques de código
            code_blocks = _CODE_BLOCK_RE.findall(content)

            if not code_blocks:
                # Sin código — respuesta final
                return {
                    "response": content,
                    "context": ctx,
                    "tool_calls": tool_calls,
                }

            # Ejecutar código en sandbox
            combined_code = "\n\n".join(code_blocks)
            tool_calls.append({"code": combined_code})

            output, new_vars = self._sandbox_fn(combined_code, ctx)
            ctx.update(new_vars)

            # Añadir respuesta del LLM y resultado de ejecución al historial
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": f"Resultado de la ejecución:\n{output}"})

        # Si llegamos aquí, el agente no convergió
        return {
            "response": "He realizado varios cálculos. ¿Necesitas algo más específico?",
            "context": ctx,
            "tool_calls": tool_calls,
        }

    def stream_chat(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
    ):
        """Genera la respuesta token por token (generador).

        Yields:
            dict con: type ('token'|'code'|'result'|'done'), content (str)
        """
        if not self.available:
            yield {"type": "done", "content": "El agente IA no está disponible."}
            return

        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        ctx = dict(context) if context else {}
        max_iterations = 5

        for _iteration in range(max_iterations):
            # Acumular respuesta completa para detectar código
            full_content = ""

            try:
                for chunk in self.model.stream(messages):
                    token = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if token:
                        full_content += token
                        yield {"type": "token", "content": token}
            except Exception as e:
                logger.error("Error streaming LLM: %s", e)
                yield {"type": "done", "content": f"Error del modelo: {e}"}
                return

            # Verificar si hay código para ejecutar
            code_blocks = _CODE_BLOCK_RE.findall(full_content)

            if not code_blocks:
                # Respuesta final
                yield {"type": "done", "content": full_content, "context": ctx}
                return

            # Ejecutar código
            combined_code = "\n\n".join(code_blocks)
            yield {"type": "code", "content": combined_code}

            output, new_vars = self._sandbox_fn(combined_code, ctx)
            ctx.update(new_vars)
            yield {"type": "result", "content": output}

            # Añadir al historial y continuar
            messages.append({"role": "assistant", "content": full_content})
            messages.append({"role": "user", "content": f"Resultado de la ejecución:\n{output}"})

        yield {"type": "done", "content": "", "context": ctx}
