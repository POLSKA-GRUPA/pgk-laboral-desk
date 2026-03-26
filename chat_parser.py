"""Parser conversacional para PGK Laboral Desk.

Flujo:
1. Usuario escribe en lenguaje natural.
2. El parser extrae: categoría probable, jornada, contrato, antigüedad, pagas.
3. Si la categoría es ambigua → genera pregunta de aclaración.
4. Si faltan datos → pregunta lo que falta.
5. Cuando todo está claro → devuelve los parámetros para engine.simulate().

Sin IA externa. Solo reglas + keywords + scoring.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

_DETAIL_PATH = Path(__file__).resolve().parent / "data" / "categorias_detalle.json"

# Stop words españolas comunes (para ignorar en matching de keywords)
_STOP_WORDS = {
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "un",
    "una",
    "unos",
    "unas",
    "en",
    "al",
    "a",
    "y",
    "o",
    "por",
    "para",
    "con",
    "que",
    "es",
    "su",
    "se",
    "lo",
    "como",
    "mas",
    "pero",
    "sus",
    "le",
    "ya",
    "mi",
    "si",
    "sin",
    "sobre",
    "este",
    "entre",
    "cuando",
    "muy",
    "nos",
    "ni",
    "otro",
    "ese",
    "eso",
    "ante",
    "ellos",
    "e",
    "esto",
    "me",
    "hasta",
    "hay",
    "donde",
    "quien",
    "desde",
    "todo",
    "durante",
    "todos",
    "uno",
    "les",
    "contra",
    "otros",
    "necesito",
    "quiero",
    "contratar",
    "alguien",
}


# Campos extra por tipo de contrato (inspirado en Findiur DefaultTriajeData)
_CONTRACT_EXTRA_FIELDS: dict[str, list[dict[str, str]]] = {
    "fijo-discontinuo": [
        {
            "key": "cx_periodo_actividad",
            "question": "¿Cuál es el periodo de actividad? (ej: mayo-septiembre, temporada de verano)",
            "extract_hints": [
                "mayo",
                "junio",
                "julio",
                "agosto",
                "septiembre",
                "verano",
                "temporada",
                "meses",
            ],
        },
    ],
    "temporal": [
        {
            "key": "cx_causa",
            "question": "¿Cuál es la causa? (circunstancias de la producción, acumulación de tareas, sustitución)",
            "extract_hints": ["produccion", "acumulacion", "demanda", "evento", "sustitucion"],
        },
        {
            "key": "cx_duracion_meses",
            "question": "¿Duración prevista en meses? (máximo 6 meses según convenio Art. 26)",
            "extract_hints": [],
        },
    ],
    "temporal-produccion": [
        {
            "key": "cx_duracion_meses",
            "question": "¿Duración prevista? (máximo 6 meses, Art. 26)",
            "extract_hints": [],
        },
    ],
    "sustitucion": [
        {
            "key": "cx_trabajador_sustituido",
            "question": "¿A quién sustituye? (nombre o puesto del trabajador ausente)",
            "extract_hints": [],
        },
    ],
}


def _normalize(text: str) -> str:
    """Normaliza texto: minúsculas, sin acentos, solo alfanumérico."""
    v = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    v = re.sub(r"[^a-z0-9]+", " ", v)
    return re.sub(r"\s+", " ", v).strip()


class ChatParser:
    """Parser de consultas laborales en lenguaje natural."""

    def __init__(self, detail_path: str | Path | None = None) -> None:
        path = Path(detail_path) if detail_path else _DETAIL_PATH
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.categorias: list[dict[str, Any]] = raw["categorias"]
        self.familias: dict[str, Any] = raw["familias_ambiguas"]
        self.grupos: list[dict[str, Any]] = raw["grupos"]

        # Precalcular keywords normalizadas
        for cat in self.categorias:
            cat["_keywords_norm"] = [_normalize(k) for k in cat.get("keywords", [])]
            cat["_nombre_norm"] = _normalize(cat.get("nombre_corto", ""))
            cat["_category_norm"] = _normalize(cat["category"])

    def parse(self, message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Parsea un mensaje y devuelve una respuesta estructurada.

        Args:
            message: Texto libre del usuario.
            context: Estado de la conversación (categorías candidatas, datos recopilados).

        Returns:
            dict con: action, message, options, params, context
        """
        ctx = dict(context) if context else {}
        norm = _normalize(message)
        # Guardar original en minúsculas para extractores que necesitan % y otros símbolos
        ctx["_raw"] = message.lower()

        # Si estamos esperando una respuesta a una pregunta previa
        if ctx.get("waiting_for") == "category_selection":
            return self._handle_category_selection(norm, message, ctx)
        if ctx.get("waiting_for") == "missing_params":
            return self._handle_param_response(norm, message, ctx)
        if ctx.get("waiting_for") == "budget_category_selection":
            return self._handle_budget_category_selection(norm, message, ctx)

        # Detectar consulta inversa (presupuesto) antes del flujo normal
        budget = self._extract_budget(ctx.get("_raw", message.lower()))
        if budget is None:
            budget = self._extract_budget(norm)
        if budget is not None:
            ctx["budget"] = budget
            return self._handle_budget_query(norm, ctx)

        # Primera interacción: buscar categoría
        category_result = self._match_category(norm)

        if category_result["status"] == "exact":
            # Categoría clara, buscar parámetros
            ctx["category"] = category_result["category"]
            ctx["category_info"] = category_result["info"]
            return self._check_params(norm, ctx)

        if category_result["status"] == "family":
            # Familia ambigua (socorrista, administrativo, etc.)
            ctx["waiting_for"] = "category_selection"
            ctx["candidates"] = category_result["options"]
            family = category_result["family"]
            fam_data = self.familias[family]

            # Construir opciones con salarios
            options = []
            for cat_name in fam_data["opciones"]:
                cat_info = self._get_cat_info(cat_name)
                if cat_info:
                    options.append(
                        {
                            "category": cat_name,
                            "label": cat_info["nombre_corto"],
                            "salary": self._get_salary_hint(cat_name),
                            "description": cat_info.get("diferencia_clave", ""),
                        }
                    )

            return {
                "action": "clarify_category",
                "message": fam_data["mensaje"] + ".\n" + fam_data["pregunta"],
                "options": options,
                "context": ctx,
            }

        if category_result["status"] == "ambiguous":
            # Varias categorías posibles, no es una familia conocida
            ctx["waiting_for"] = "category_selection"
            ctx["candidates"] = [m["category"] for m in category_result["matches"]]

            options = []
            for m in category_result["matches"][:4]:
                cat_info = self._get_cat_info(m["category"])
                options.append(
                    {
                        "category": m["category"],
                        "label": cat_info["nombre_corto"] if cat_info else m["category"],
                        "salary": self._get_salary_hint(m["category"]),
                        "description": cat_info["descripcion"][:80] + "..." if cat_info else "",
                        "score": m["score"],
                    }
                )

            return {
                "action": "clarify_category",
                "message": "He encontrado varias categorías que podrían encajar. ¿Cuál necesitas?",
                "options": options,
                "context": ctx,
            }

        # No se encontró nada
        return {
            "action": "not_found",
            "message": "No he podido identificar la categoría profesional. Intenta describir el puesto con más detalle o elige directamente del formulario.",
            "options": [],
            "context": ctx,
        }

    def _match_category(self, norm_text: str) -> dict[str, Any]:
        """Intenta mapear el texto a una categoría."""

        # 1. Detectar familias ambiguas primero
        for family_key, family_data in self.familias.items():
            family_norm = _normalize(family_key)
            if family_norm in norm_text:
                # Verificar si hay pistas que resuelvan la ambigüedad
                resolved = self._try_resolve_family(norm_text, family_key, family_data)
                if resolved:
                    return resolved
                return {
                    "status": "family",
                    "family": family_key,
                    "options": family_data["opciones"],
                }

        # 2. Scoring por keywords
        scored: list[dict[str, Any]] = []
        tokens = set(norm_text.split())
        # Quitar stop words para matching de keywords multi-palabra
        content_tokens = tokens - _STOP_WORDS

        for cat in self.categorias:
            score = 0.0

            # Match en nombre normalizado
            if cat["_nombre_norm"] in norm_text:
                score += 3.0
            if cat["_category_norm"] in norm_text:
                score += 3.0

            # Match en keywords
            for kw in cat["_keywords_norm"]:
                if kw in norm_text:
                    score += 2.0
                else:
                    kw_tokens = set(kw.split()) - _STOP_WORDS
                    if kw_tokens:
                        overlap = len(kw_tokens & content_tokens)
                        ratio = overlap / len(kw_tokens)
                        if ratio >= 1.0:
                            # Todas las palabras clave presentes (ignorando stop words)
                            score += 2.0
                        elif overlap > 0:
                            score += overlap * 0.5

            if score > 0:
                scored.append({"category": cat["category"], "score": score, "info": cat})

        scored.sort(key=lambda x: x["score"], reverse=True)

        if not scored:
            return {"status": "not_found"}

        top = scored[0]
        second = scored[1] if len(scored) > 1 else None

        # Match claro: top score alto y bien separado del segundo
        if top["score"] >= 2.0 and (second is None or top["score"] - second["score"] >= 0.5):
            return {"status": "exact", "category": top["category"], "info": top["info"]}

        # Ambiguo: varios candidatos cercanos
        close_matches = [s for s in scored if s["score"] >= top["score"] * 0.6]
        return {"status": "ambiguous", "matches": close_matches[:4]}

    def _try_resolve_family(
        self, norm_text: str, family: str, family_data: dict
    ) -> dict[str, Any] | None:
        """Intenta resolver una familia ambigua con pistas en el texto."""

        if family == "socorrista":
            if "nivel a" in norm_text or "coordinador" in norm_text or "jefe" in norm_text:
                return self._exact("Nivel A.")
            if "nivel b" in norm_text or "estandar" in norm_text:
                return self._exact("Nivel B.")
            if "nivel c" in norm_text or "basico" in norm_text or "apoyo" in norm_text:
                return self._exact("Nivel C.")
            if "correturn" in norm_text or "sustitut" in norm_text or "cubrir" in norm_text:
                return self._exact("Socorrista correturnos.")

        if family == "administrativo":
            if "jefe" in norm_text or "director" in norm_text or "responsable" in norm_text:
                return self._exact("Jefe Administrativo.")
            if "oficial" in norm_text or "autonomi" in norm_text:
                return self._exact("Oficial Administrativo.")
            if "auxiliar" in norm_text or "basico" in norm_text or "apoyo" in norm_text:
                return self._exact("Auxiliar Administrativo.")

        if family == "conductor":
            if (
                "camion" in norm_text
                or "pesado" in norm_text
                or "especial" in norm_text
                or "adr" in norm_text
            ):
                return self._exact("Conductor especialista.")
            if "furgoneta" in norm_text or "ligero" in norm_text:
                return self._exact("Conductor.")

        if family == "instalador":
            if "electri" in norm_text:
                return self._exact("Instalador de montajes eléctricos.")
            if "fontan" in norm_text or "depura" in norm_text or "tuberi" in norm_text:
                return self._exact(
                    "Instalador de montajes de circuitos de depuración y fontanería."
                )

        if family == "auxiliar":
            if "admin" in norm_text or "oficina" in norm_text:
                return self._exact("Auxiliar Administrativo.")
            if "oficio" in norm_text or "peon" in norm_text:
                return self._exact("Auxiliar de oficios.")
            if "instalacion" in norm_text or "piscina" in norm_text:
                return self._exact("Auxiliar de instalaciones.")

        if family == "mantenimiento":
            if "electri" in norm_text:
                return self._exact("Instalador de montajes eléctricos.")
            if "fontan" in norm_text or "tuberi" in norm_text:
                return self._exact(
                    "Instalador de montajes de circuitos de depuración y fontanería."
                )
            if "encargado" in norm_text or "jefe" in norm_text or "supervisor" in norm_text:
                return self._exact("Encargado.")
            if (
                "piscina" in norm_text
                or "agua" in norm_text
                or "quimic" in norm_text
                or "cloro" in norm_text
            ):
                return self._exact("Técnico de Mantenimiento en Instalaciones de Piscinas.")

        return None

    def _exact(self, category: str) -> dict[str, Any]:
        info = self._get_cat_info(category)
        return {"status": "exact", "category": category, "info": info}

    def _handle_category_selection(self, norm: str, original: str, ctx: dict) -> dict[str, Any]:
        """El usuario responde eligiendo una categoría."""
        candidates = ctx.get("candidates", [])

        # Intentar match por nombre o número
        for i, cat_name in enumerate(candidates):
            cat_info = self._get_cat_info(cat_name)
            cat_norm = _normalize(cat_name)
            short_norm = _normalize(cat_info["nombre_corto"]) if cat_info else ""

            # Match por texto
            if cat_norm in norm or short_norm in norm:
                ctx["category"] = cat_name
                ctx["category_info"] = cat_info
                ctx.pop("waiting_for", None)
                ctx.pop("candidates", None)
                return self._check_params(norm, ctx)

            # Match por número (1, 2, 3...)
            if str(i + 1) in norm.split():
                ctx["category"] = cat_name
                ctx["category_info"] = cat_info
                ctx.pop("waiting_for", None)
                ctx.pop("candidates", None)
                return self._check_params(norm, ctx)

        # Match parcial por keywords
        for cat_name in candidates:
            cat_info = self._get_cat_info(cat_name)
            if cat_info:
                for kw in cat_info.get("_keywords_norm", []):
                    if kw in norm:
                        ctx["category"] = cat_name
                        ctx["category_info"] = cat_info
                        ctx.pop("waiting_for", None)
                        ctx.pop("candidates", None)
                        return self._check_params(norm, ctx)

        # No se entendió
        return {
            "action": "clarify_category",
            "message": "No he entendido tu elección. Indica el nombre o el número de la opción.",
            "options": [
                {
                    "category": c,
                    "label": (self._get_cat_info(c) or {}).get("nombre_corto", c),
                    "salary": self._get_salary_hint(c),
                }
                for c in candidates
            ],
            "context": ctx,
        }

    def _check_params(self, norm: str, ctx: dict) -> dict[str, Any]:
        """Verifica si tenemos todos los parámetros necesarios. Si no, pregunta."""
        # Extraer parámetros del texto — usar raw para símbolos como %
        raw = ctx.get("_raw", norm)
        params = ctx.get("params", {})
        params["category"] = ctx["category"]

        # Jornada (usar raw para capturar %)
        if (
            "jornada" not in params
            or params["jornada"] is None
            or self._is_parcial_sentinel(params.get("jornada"))
        ):
            hours = self._extract_hours(raw)
            if hours is None:
                hours = self._extract_hours(norm)
            if hours is not None:
                params["jornada"] = hours  # puede ser -1 (centinela parcial)

        # Tipo de contrato
        if "contract_type" not in params or params["contract_type"] is None:
            ct = self._extract_contract_type(norm)
            if ct is None:
                ct = self._extract_contract_type(raw)
            if ct is not None:
                params["contract_type"] = ct

        # Antigüedad
        if "seniority" not in params:
            sen = self._extract_seniority(norm)
            if sen is not None:
                params["seniority"] = sen

        # Pagas
        if "extras_prorated" not in params:
            ep = self._extract_extras(norm)
            if ep is not None:
                params["extras_prorated"] = ep

        ctx["params"] = params

        # ¿Falta algo crítico? (básicos primero)
        missing = []
        jornada_val = params.get("jornada")
        if jornada_val is None or self._is_parcial_sentinel(jornada_val):
            missing.append("jornada")
        if params.get("contract_type") is None:
            missing.append("contract_type")

        if missing:
            ctx["waiting_for"] = "missing_params"
            ctx["missing"] = missing
            ctx["_had_questions"] = True
            questions = []
            if "jornada" in missing:
                if self._is_parcial_sentinel(jornada_val):
                    # Usuario ya dijo "parcial" → preguntar cuántas horas exactamente
                    questions.append("¿Cuántas horas semanales? (ej: 20h, 25h, 30h, 32h)")
                else:
                    questions.append("¿Jornada completa (40h) o cuántas horas semanales?")
            if "contract_type" in missing:
                questions.append("¿Tipo de contrato? Indefinido, temporal, fijo-discontinuo...")

            cat_info = ctx.get("category_info") or self._get_cat_info(params["category"])
            cat_label = cat_info["nombre_corto"] if cat_info else params["category"]

            return {
                "action": "need_params",
                "message": f"Categoría: **{cat_label}** ({self._get_salary_hint(params['category'])}).\n"
                + "\n".join(f"• {q}" for q in questions),
                "missing": missing,
                "context": ctx,
            }

        # Campos específicos por tipo de contrato (patrón Findiur)
        # Solo preguntar si ya estamos en flujo multi-turno (el usuario ya respondió algo)
        contract_extra = _CONTRACT_EXTRA_FIELDS.get(params.get("contract_type", ""), [])
        for field in contract_extra:
            if field["key"] not in params:
                extracted = self._extract_contract_extra(norm, raw, field["key"])
                if extracted is not None:
                    params[field["key"]] = extracted

        # Solo preguntar extras si ya hubo al menos una pregunta previa (multi-turno)
        is_multiturn = ctx.get("_extras_asked") is not None or ctx.get("_had_questions")
        if is_multiturn and not ctx.get("_extras_asked"):
            extra_missing = [f for f in contract_extra if f["key"] not in params]
            if extra_missing:
                ctx["waiting_for"] = "missing_params"
                ctx["missing"] = [f["key"] for f in extra_missing]
                ctx["_extras_asked"] = True
                ctx["params"] = params
                questions = [f"• {f['question']}" for f in extra_missing]
                ct_label = params.get("contract_type", "")
                return {
                    "action": "need_params",
                    "message": f"Para un contrato **{ct_label}**, necesito saber:\n"
                    + "\n".join(questions),
                    "missing": [f["key"] for f in extra_missing],
                    "context": ctx,
                }

        # Todo listo — construir avisos específicos del contrato
        avisos = self._build_contract_warnings(params)

        return {
            "action": "ready",
            "message": None,
            "params": {
                "category": params["category"],
                "contract_type": params.get("contract_type", "indefinido"),
                "weekly_hours": params.get("jornada", 40.0),
                "seniority_years": params.get("seniority", 0),
                "extras_prorated": params.get("extras_prorated", False),
                "num_children": params.get("num_children", 0),
                "children_under_3": 0,
            },
            "contract_extras": {k: v for k, v in params.items() if k.startswith("cx_")},
            "contract_warnings": avisos,
            "context": ctx,
        }

    def _handle_param_response(self, norm: str, original: str, ctx: dict) -> dict[str, Any]:
        """El usuario responde con datos que faltaban."""
        raw = ctx.get("_raw", original.lower())
        ctx["_raw"] = raw
        params = ctx.get("params", {})

        # Extraer lo que podamos — usar raw primero (tiene %, acentos)
        hours = self._extract_hours(raw)
        if hours is None:
            hours = self._extract_hours(norm)
        if hours is not None:
            params["jornada"] = hours

        ct = self._extract_contract_type(norm)
        if ct is None:
            ct = self._extract_contract_type(raw)
        if ct is not None:
            params["contract_type"] = ct

        sen = self._extract_seniority(norm)
        if sen is None:
            sen = self._extract_seniority(raw)
        if sen is not None:
            params["seniority"] = sen

        ep = self._extract_extras(norm)
        if ep is None:
            ep = self._extract_extras(raw)
        if ep is not None:
            params["extras_prorated"] = ep

        ctx["params"] = params
        ctx.pop("waiting_for", None)
        ctx.pop("missing", None)

        return self._check_params(norm, ctx)

    # ------------------------------------------------------------------
    # Extractores de parámetros
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_hours(text: str) -> float | None:
        # Horas explícitas: "20 horas", "20h", "20 h/semana", "20 horas semanales"
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:horas?|h)\b", text)
        if m:
            return float(m.group(1).replace(",", "."))

        # Porcentaje de jornada: "50%", "75 %", "80%"
        pct = re.search(r"(\d{1,3})\s*%", text)
        if pct:
            return round(40.0 * float(pct.group(1)) / 100, 2)

        # Fracciones: tres cuartos, 3/4 → 30h
        if "tres cuartos" in text or "3/4" in text or "3 4" in text:
            return 30.0

        # Media jornada (sin número) → 20h
        if "media jornada" in text or "medio tiempo" in text or "jornada media" in text:
            return 20.0

        # Jornada completa → 40h
        _completa_hints = [
            "jornada completa",
            "tiempo completo",
            "40 horas",
            "jornada entera",
            "jornada total",
        ]
        if any(h in text for h in _completa_hints):
            return 40.0
        if "completa" in text and ("jornada" in text or "horas" in text):
            return 40.0

        # Jornada parcial sin número → centinela -1 (caller preguntará las horas)
        _parcial_hints = [
            "jornada parcial",
            "tiempo parcial",
            "a tiempo parcial",
            "media jornada",
            "jornada reducida",
            "reducida",
        ]
        if (
            any(h in text for h in _parcial_hints)
            or (
                "parcial" in text and "jornada" not in text  # "parcial" a secas
            )
            or text.strip() in ("parcial", "tiempo parcial", "jornada parcial")
        ):
            return -1.0  # señal: el usuario dijo parcial pero falta el número de horas

        return None

    @staticmethod
    def _is_parcial_sentinel(hours: float | None) -> bool:
        """True si el valor es el centinela de 'parcial sin horas'."""
        return hours is not None and hours < 0

    @staticmethod
    def _extract_contract_type(text: str) -> str | None:
        if "fijo discontinu" in text or "fijo descontinu" in text:
            return "fijo-discontinuo"
        if "sustituc" in text:
            return "sustitucion"
        if "circunstancias" in text and "produccion" in text:
            return "temporal-produccion"
        if "temporal" in text or "eventual" in text:
            return "temporal"
        if "indefinid" in text or "fijo" in text:
            return "indefinido"
        # NOTA: "tiempo parcial" NO es un tipo de contrato, es una jornada.
        # Se gestiona en _extract_hours como centinela -1.
        return None

    @staticmethod
    def _extract_seniority(text: str) -> int | None:
        patterns = [
            r"(\d+)\s*(?:anos?|años?)\s*(?:de\s*)?(?:antiguedad|antigüedad)?",
            r"(?:antiguedad|antigüedad)\s*(?:de\s*)?(\d+)",
            r"lleva\s*(\d+)\s*(?:anos?|años?)",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return int(m.group(1))
        if (
            "sin antiguedad" in text
            or "sin antigüedad" in text
            or "nuevo" in text
            or "nueva" in text
        ):
            return 0
        return None

    @staticmethod
    def _extract_extras(text: str) -> bool | None:
        if "12 pagas" in text or "prorrat" in text:
            return True
        if "14 pagas" in text or "sin prorrat" in text:
            return False
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_contract_extra(norm: str, raw: str, key: str) -> str | None:
        """Intenta extraer un campo extra del contrato desde el texto."""
        if key == "cx_periodo_actividad":
            # Buscar patrones de meses o temporada
            meses = [
                "enero",
                "febrero",
                "marzo",
                "abril",
                "mayo",
                "junio",
                "julio",
                "agosto",
                "septiembre",
                "octubre",
                "noviembre",
                "diciembre",
            ]
            found = [m for m in meses if m in raw]
            if len(found) >= 2:
                return f"{found[0].title()}-{found[-1].title()}"
            if "verano" in raw or "temporada" in raw:
                return "Temporada de verano"
            if "invierno" in raw:
                return "Temporada de invierno"
        if key == "cx_duracion_meses":
            m = re.search(r"(\d+)\s*mes", norm)
            if m:
                return m.group(1)
        if key == "cx_causa":
            if "produccion" in norm or "demanda" in norm:
                return "Circunstancias de la producción"
            if "acumulacion" in norm or "exceso" in norm:
                return "Acumulación de tareas"
            if "sustitu" in norm:
                return "Sustitución"
        return None

    @staticmethod
    def _build_contract_warnings(params: dict) -> list[str]:
        """Genera avisos legales específicos según el tipo de contrato."""
        warnings = []
        ct = params.get("contract_type", "")
        if ct == "fijo-discontinuo":
            warnings.append(
                "Art. 26: Solo procede para trabajos estacionales, de temporada o de prestación intermitente."
            )
            warnings.append(
                "Art. 32: La antigüedad computa toda la relación laboral, no solo el tiempo trabajado."
            )
            if not params.get("cx_periodo_actividad"):
                warnings.append(
                    "⚠ No se ha definido el periodo de actividad. Requerido para formalizar el contrato."
                )
        elif ct in ("temporal", "temporal-produccion"):
            warnings.append(
                "Art. 26: Duración máxima 6 meses. Debe expresar la causa con precisión en el contrato."
            )
            dur = params.get("cx_duracion_meses")
            if dur and int(dur) > 6:
                warnings.append(f"⚠ {dur} meses excede el máximo de 6 meses del convenio.")
        elif ct == "sustitucion":
            warnings.append(
                "Debe identificar al trabajador sustituido y la causa de la ausencia en el contrato."
            )
        elif ct == "indefinido":
            warnings.append("Art. 26: El contrato se presume indefinido por defecto.")
        # Periodo de prueba
        cat = params.get("category", "")
        if "Nivel" in cat or "Socorrista" in cat or "correturnos" in cat.lower():
            warnings.append("Periodo de prueba: 15 días (Arts. 20-21).")
        elif any(x in cat for x in ["Técnico", "Jefe", "Oficial", "Comercial"]):
            warnings.append("Periodo de prueba: hasta 3 meses (Arts. 20-21).")
        else:
            warnings.append("Periodo de prueba: hasta 30 días (Arts. 20-21).")
        return warnings

    # ------------------------------------------------------------------
    # Consulta inversa (presupuesto)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_spanish_number(raw: str) -> float:
        """Parse a number that may use Spanish/European formatting.

        Spanish format: period = thousands separator, comma = decimal.
        - "1.200" → 1200.0
        - "2.500,50" → 2500.50
        - "1200" → 1200.0
        - "1,5" → 1.5
        """
        # If it contains both period and comma, period is thousands sep
        if "." in raw and "," in raw:
            return float(raw.replace(".", "").replace(",", "."))
        # Period followed by exactly 3 digits → thousands separator
        if re.match(r"^\d{1,3}(\.\d{3})+$", raw):
            return float(raw.replace(".", ""))
        # Otherwise comma is decimal separator
        return float(raw.replace(",", "."))

    @staticmethod
    def _extract_budget(text: str) -> float | None:
        """Extrae el presupuesto máximo de una frase.

        Patrones reconocidos:
        - "máximo 1200", "max 1200", "maximo 1200 euros"
        - "presupuesto 1200", "presupuesto de 1200"
        - "pagar 1200", "pagarle 1200", "gastar 1200"
        - "1200 euros máximo", "1200€ max"
        - "hasta 1200€", "no más de 1200", "tope 1200"
        - "por 1200€", "con 1200€"
        """
        # Number pattern: supports "1200", "1.200", "1.200,50", "1200,50"
        _n = r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)"
        patterns = [
            rf"(?:maximo|max|presupuesto|pagar|pagarle|gastar|gastarm?e|tope|limite)\s+(?:de\s+)?(?:hasta\s+)?{_n}",
            rf"{_n}\s*(?:€|euros?|eur)\s*(?:maximo|max|como\s+mucho|de\s+tope)",
            rf"hasta\s+{_n}\s*(?:€|euros?|eur)",
            rf"no\s+mas\s+de\s+{_n}",
            rf"(?:por|con)\s+{_n}\s*(?:€|euros?|eur)",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                val = ChatParser._parse_spanish_number(m.group(1))
                if 100 <= val <= 50000:  # rango razonable para coste mensual
                    return val
        return None

    def _handle_budget_query(self, norm: str, ctx: dict) -> dict[str, Any]:
        """Procesa una consulta de presupuesto: detecta categoría y devuelve opciones."""
        budget = ctx["budget"]
        category_result = self._match_category(norm)

        if category_result["status"] == "exact":
            return {
                "action": "budget_search",
                "params": {
                    "category": category_result["category"],
                    "max_monthly_cost": budget,
                },
                "context": ctx,
            }

        if category_result["status"] == "family":
            family = category_result["family"]
            fam_data = self.familias[family]
            ctx["waiting_for"] = "budget_category_selection"
            ctx["candidates"] = fam_data["opciones"]
            options = []
            for cat_name in fam_data["opciones"]:
                cat_info = self._get_cat_info(cat_name)
                if cat_info:
                    options.append(
                        {
                            "category": cat_name,
                            "label": cat_info["nombre_corto"],
                            "salary": self._get_salary_hint(cat_name),
                            "description": cat_info.get("diferencia_clave", ""),
                        }
                    )
            return {
                "action": "clarify_category",
                "message": f"Presupuesto: **{budget:.0f} €/mes**. {fam_data['mensaje']}.\n{fam_data['pregunta']}",
                "options": options,
                "context": ctx,
            }

        if category_result["status"] == "ambiguous":
            ctx["waiting_for"] = "budget_category_selection"
            ctx["candidates"] = [m["category"] for m in category_result["matches"]]
            options = []
            for m in category_result["matches"][:4]:
                cat_info = self._get_cat_info(m["category"])
                options.append(
                    {
                        "category": m["category"],
                        "label": cat_info["nombre_corto"] if cat_info else m["category"],
                        "salary": self._get_salary_hint(m["category"]),
                    }
                )
            return {
                "action": "clarify_category",
                "message": f"Presupuesto: **{budget:.0f} €/mes**. ¿Qué categoría necesitas?",
                "options": options,
                "context": ctx,
            }

        return {
            "action": "not_found",
            "message": "No he podido identificar la categoría profesional. Intenta describir el puesto.",
            "options": [],
            "context": ctx,
        }

    def _handle_budget_category_selection(
        self, norm: str, original: str, ctx: dict
    ) -> dict[str, Any]:
        """El usuario selecciona categoría para una consulta de presupuesto."""
        candidates = ctx.get("candidates", [])

        # Intentar match directo por número ("1", "2", etc.)
        try:
            idx = int(norm.strip()) - 1
            if 0 <= idx < len(candidates):
                ctx.pop("waiting_for", None)
                ctx.pop("candidates", None)
                return {
                    "action": "budget_search",
                    "params": {
                        "category": candidates[idx],
                        "max_monthly_cost": ctx["budget"],
                    },
                    "context": ctx,
                }
        except ValueError:
            pass

        # Intentar match por keywords
        for cat_name in candidates:
            cat_norm = _normalize(cat_name)
            if cat_norm in norm or norm in cat_norm:
                ctx.pop("waiting_for", None)
                ctx.pop("candidates", None)
                return {
                    "action": "budget_search",
                    "params": {
                        "category": cat_name,
                        "max_monthly_cost": ctx["budget"],
                    },
                    "context": ctx,
                }

        # Usar scoring general
        category_result = self._match_category(norm)
        if category_result["status"] == "exact":
            ctx.pop("waiting_for", None)
            ctx.pop("candidates", None)
            return {
                "action": "budget_search",
                "params": {
                    "category": category_result["category"],
                    "max_monthly_cost": ctx["budget"],
                },
                "context": ctx,
            }

        return {
            "action": "clarify_category",
            "message": "No he entendido la categoría. ¿Puedes elegir una opción?",
            "options": [
                {
                    "category": c,
                    "label": (self._get_cat_info(c) or {}).get("nombre_corto", c),
                }
                for c in candidates
            ],
            "context": ctx,
        }

    def _get_cat_info(self, category: str) -> dict[str, Any] | None:
        for cat in self.categorias:
            if cat["category"] == category:
                return cat
        return None

    def _get_salary_hint(self, category: str) -> str:
        """Devuelve hint de salario para mostrar al usuario."""
        # Esto se podría sacar del convenio JSON, pero por ahora hardcodeamos
        # las referencias del Anexo I
        salary_map = {
            "Técnico Titulado.": "2.008 €/mes",
            "Técnico Diplomado.": "1.620 €/mes",
            "Jefe Administrativo.": "1.415 €/mes",
            "Oficial Administrativo.": "1.292 €/mes",
            "Auxiliar Administrativo.": "1.184 €/mes",
            "Recepcionista-telefonista.": "1.184 €/mes",
            "Nivel A.": "1.297 €/mes",
            "Nivel B.": "1.184 €/mes",
            "Nivel C.": "1.184 €/mes",
            "Socorrista correturnos.": "1.297 €/mes",
            "Monitor de natación.": "1.184 €/mes",
            "Comercial.": "1.413 €/mes",
            "Encargado.": "1.393 €/mes",
            "Conductor especialista.": "1.348 €/mes",
            "Conductor.": "1.282 €/mes",
            "Instalador de montajes eléctricos.": "1.348 €/mes",
            "Técnico de Mantenimiento en Instalaciones de Piscinas.": "1.327 €/mes",
            "Instalador de montajes de circuitos de depuración y fontanería.": "1.348 €/mes",
            "Ayudante de maquinista.": "1.260 €/mes",
            "Almacenero.": "1.184 €/mes",
            "Controlador de acceso al recinto de la instalación.": "1.184 €/mes",
            "Auxiliar de oficios.": "1.184 €/mes",
            "Limpiador de piscinas.": "1.184 €/mes",
            "Auxiliar de instalaciones.": "1.184 €/mes",
        }
        return salary_map.get(category, "—")
