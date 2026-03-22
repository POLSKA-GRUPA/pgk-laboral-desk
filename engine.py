from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


FULL_TIME_WEEKLY_HOURS = 40.0
SEASONALITY_HINTS = {
    "temporada",
    "estacional",
    "campana",
    "campaña",
    "verano",
    "intermitente",
    "fines de semana de verano",
    "meses de verano",
}
SPANISH_ORIGIN_HINTS = {"peru", "perú", "chile", "latinoamerica", "latinoamérica"}


SPECIAL_ALIASES: dict[str, list[str]] = {
    "nivel a": ["socorrista nivel a", "socorrista a", "nivel a socorrista"],
    "nivel b": ["socorrista nivel b", "socorrista b", "nivel b socorrista"],
    "nivel c": ["socorrista nivel c", "socorrista c", "nivel c socorrista"],
    "socorrista correturnos": ["correturnos", "socorrista correturno", "socorrista correturnos"],
    "controlador de acceso al recinto de la instalacion": [
        "controlador de acceso",
        "controlador acceso",
    ],
    "tecnico de mantenimiento en instalaciones de piscinas": [
        "tecnico de mantenimiento",
        "mantenimiento piscinas",
        "tecnico mantenimiento piscinas",
    ],
    "instalador de montajes de circuitos de depuracion y fontaneria": [
        "instalador fontaneria",
        "instalador depuracion",
        "instalador circuitos depuracion",
    ],
    "recepcionista telefonista": ["recepcionista", "telefonista"],
    "monitor de natacion": ["monitor natacion", "monitor de natación"],
    "limpiador de piscinas": ["limpiador piscinas", "limpieza de piscinas"],
    "tecnico titulado": ["titulado", "tecnico titulado", "técnico titulado"],
    "tecnico diplomado": ["diplomado", "tecnico diplomado", "técnico diplomado"],
}


@dataclass(frozen=True)
class SalaryRow:
    section: str
    category: str
    monthly_14_payments_eur: float
    annual_eur: float
    hourly_ordinary_or_flexible_eur: float


class LaboralEngine:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.salary_rows = [SalaryRow(**row) for row in data["salarios_por_categoria"]]
        self.condition_index = {
            self._normalize_text(item["label"]): item
            for section in data["sections"]
            for item in section["items"]
        }
        self.alias_index = self._build_alias_index()

    @classmethod
    def from_json_file(cls, path: str | Path) -> "LaboralEngine":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data)

    def analyze(self, query: str) -> dict[str, Any]:
        normalized_query = self._normalize_text(query)
        category_match = self._match_category(normalized_query)
        contract_type = self._detect_contract_type(normalized_query)
        weekly_hours = self._extract_weekly_hours(normalized_query)
        jornada_ratio = round(weekly_hours / FULL_TIME_WEEKLY_HOURS, 4) if weekly_hours else None
        extras_prorated = self._detect_extras_prorated(normalized_query)
        seniority_years = self._extract_seniority_years(normalized_query)
        trienios = self._extract_trienios(normalized_query, seniority_years)
        fixed_discontinuous_fit = self._assess_fixed_discontinuous(contract_type, normalized_query)

        clarifications: list[str] = []
        if category_match["status"] != "clear":
            clarifications.append(self._build_category_clarification(normalized_query, category_match))
        if weekly_hours is None:
            clarifications.append("Indica la jornada: completa, media jornada o número de horas semanales.")
        if contract_type == "fijo-discontinuo" and fixed_discontinuous_fit["status"] != "clear":
            clarifications.append(
                "Describe el periodo real de actividad: temporada, meses concretos o carácter intermitente del servicio."
            )

        payroll_draft = None
        if category_match["status"] == "clear" and weekly_hours is not None:
            payroll_draft = self._build_payroll_draft(
                salary_row=category_match["row"],
                jornada_ratio=jornada_ratio or 1.0,
                extras_prorated=extras_prorated,
                trienios=trienios,
            )

        status = "ready" if payroll_draft is not None and not clarifications else "needs_clarification"

        return {
            "status": status,
            "answer": self._build_answer(
                query=query,
                category_match=category_match,
                contract_type=contract_type,
                weekly_hours=weekly_hours,
                extras_prorated=extras_prorated,
                trienios=trienios,
                fixed_discontinuous_fit=fixed_discontinuous_fit,
                payroll_draft=payroll_draft,
            ),
            "clarifications": clarifications,
            "request": {
                "query": query,
                "category_match": self._serialize_category_match(category_match),
                "contract_type": contract_type,
                "weekly_hours": weekly_hours,
                "jornada_ratio": jornada_ratio,
                "extras_prorated": extras_prorated,
                "seniority_years": seniority_years,
                "trienios": trienios,
                "mentions_foreign_origin": any(token in normalized_query for token in SPANISH_ORIGIN_HINTS),
            },
            "contract_fit": fixed_discontinuous_fit,
            "payroll_draft": payroll_draft,
            "relevant_sections": self._select_relevant_sections(contract_type),
            "convenio": self.data["convenio"],
            "sources": [
                "Art. 25-39 del convenio colectivo estatal de mantenimiento y conservación de instalaciones acuáticas",
                "Anexo I salarial del convenio",
            ],
        }

    def _build_alias_index(self) -> list[dict[str, Any]]:
        alias_index: list[dict[str, Any]] = []
        for row in self.salary_rows:
            normalized_category = self._normalize_text(row.category)
            aliases = {
                normalized_category,
                normalized_category.replace(" de ", " "),
                normalized_category.replace(" al ", " "),
            }
            aliases.update(SPECIAL_ALIASES.get(normalized_category, []))
            if normalized_category.startswith("auxiliar "):
                aliases.add(normalized_category.replace("auxiliar ", "aux "))
            if normalized_category.startswith("oficial "):
                aliases.add(normalized_category.replace("oficial ", "of "))
            alias_index.append(
                {
                    "row": row,
                    "normalized_category": normalized_category,
                    "aliases": [self._normalize_text(alias) for alias in aliases if len(alias.strip()) > 2],
                }
            )
        return alias_index

    def _match_category(self, query: str) -> dict[str, Any]:
        socorrista_resolution = self._resolve_socorrista_family(query)
        if socorrista_resolution is not None:
            return socorrista_resolution

        scored: list[tuple[float, SalaryRow]] = []
        query_tokens = set(query.split())

        for entry in self.alias_index:
            best_score = 0.0
            for alias in entry["aliases"]:
                alias_tokens = set(alias.split())
                overlap = len(alias_tokens & query_tokens) / len(alias_tokens) if alias_tokens else 0.0
                contains_score = 1.0 if alias in query else 0.0
                sequence_score = SequenceMatcher(None, alias, query).ratio()
                best_score = max(best_score, contains_score, overlap * 0.92, sequence_score * 0.55)
            scored.append((best_score, entry["row"]))

        scored.sort(key=lambda item: item[0], reverse=True)
        top_score, top_row = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0

        if top_score < 0.55:
            return {"status": "missing", "score": top_score, "row": None, "alternatives": []}
        if top_score >= 0.95 and second_score < 0.95:
            return {
                "status": "clear",
                "score": top_score,
                "row": top_row,
                "alternatives": [row.category for _, row in scored[:3]],
            }
        if top_score < 0.72 or abs(top_score - second_score) < 0.08:
            return {
                "status": "ambiguous",
                "score": top_score,
                "row": top_row,
                "alternatives": [row.category for _, row in scored[:3]],
            }
        return {
            "status": "clear",
            "score": top_score,
            "row": top_row,
            "alternatives": [row.category for _, row in scored[:3]],
        }

    def _detect_contract_type(self, query: str) -> str | None:
        if "fijo discontinu" in query or "fijo descontinu" in query:
            return "fijo-discontinuo"
        if "sustituc" in query:
            return "sustitucion"
        if "circunstancias de la produccion" in query or "circunstancias de la producción" in query:
            return "temporal-produccion"
        if "temporal" in query or "eventual" in query:
            return "temporal"
        if "indefinid" in query:
            return "indefinido"
        if "tiempo parcial" in query:
            return "tiempo-parcial"
        return None

    def _extract_weekly_hours(self, query: str) -> float | None:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:horas|h)\s*(?:semanales|semana)?", query)
        if match:
            return float(match.group(1).replace(",", "."))
        percent_match = re.search(r"(\d{1,3})\s*%", query)
        if percent_match:
            return round(FULL_TIME_WEEKLY_HOURS * (float(percent_match.group(1)) / 100.0), 2)
        if "media jornada" in query:
            return FULL_TIME_WEEKLY_HOURS / 2.0
        if "jornada completa" in query or "a tiempo completo" in query:
            return FULL_TIME_WEEKLY_HOURS
        return None

    def _detect_extras_prorated(self, query: str) -> bool | None:
        if "12 pagas" in query or "prorrat" in query:
            return True
        if "14 pagas" in query or "sin prorrat" in query:
            return False
        return None

    def _extract_seniority_years(self, query: str) -> int | None:
        patterns = (
            r"antiguedad de (\d+) anos",
            r"antigüedad de (\d+) años",
            r"(\d+) anos de antiguedad",
            r"(\d+) años de antigüedad",
            r"lleva (\d+) anos",
            r"lleva (\d+) años",
        )
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                return int(match.group(1))
        return None

    def _extract_trienios(self, query: str, seniority_years: int | None) -> int:
        match = re.search(r"(\d+)\s*trienios?", query)
        if match:
            return int(match.group(1))
        if seniority_years is not None:
            return math.floor(seniority_years / 3)
        return 0

    def _assess_fixed_discontinuous(self, contract_type: str | None, query: str) -> dict[str, str]:
        mentions_seasonality = any(hint in query for hint in SEASONALITY_HINTS)
        if contract_type != "fijo-discontinuo":
            return {
                "status": "not_requested",
                "message": "No se ha pedido expresamente un contrato fijo-discontinuo.",
            }
        if mentions_seasonality:
            return {
                "status": "clear",
                "message": "El fijo-discontinuo encaja de forma provisional porque la petición describe actividad estacional o intermitente.",
            }
        return {
            "status": "unclear",
            "message": "El convenio solo lo ampara para trabajos estacionales, de temporada o intermitentes; falta describir el periodo real de actividad.",
        }

    def _build_payroll_draft(
        self,
        salary_row: SalaryRow,
        jornada_ratio: float,
        extras_prorated: bool | None,
        trienios: int,
    ) -> dict[str, Any]:
        plus_transporte = self._extract_amount_from_condition("plus transporte")
        monthly_base = round(salary_row.monthly_14_payments_eur * jornada_ratio, 2)
        seniority_amount = round(monthly_base * 0.03 * trienios, 2)
        extra_prorrata = round(monthly_base / 6.0, 2) if extras_prorated else 0.0
        total_devengado = round(monthly_base + seniority_amount + plus_transporte + extra_prorrata, 2)

        devengos = [
            {
                "concept": "Salario base convenio",
                "amount_eur": monthly_base,
                "source": "Anexo I",
            },
            {
                "concept": f"Antiguedad ({trienios} trienios x 3%)",
                "amount_eur": seniority_amount,
                "source": "Art. 32",
            },
            {
                "concept": "Plus transporte",
                "amount_eur": plus_transporte,
                "source": "Art. 33 y Anexo I",
                "note": "No se ha minorado automaticamente porque el convenio extraido no fija regla especifica de prorrata para este concepto.",
            },
        ]
        if extras_prorated:
            devengos.append(
                {
                    "concept": "Prorrata de pagas extra",
                    "amount_eur": extra_prorrata,
                    "source": "Art. 31",
                    "note": "Calculada sobre salario convenio base del mes activo.",
                }
            )

        return {
            "category": salary_row.category,
            "section": salary_row.section,
            "jornada_ratio": jornada_ratio,
            "monthly_reference_14_payments_eur": round(salary_row.monthly_14_payments_eur, 2),
            "hourly_reference_eur": round(salary_row.hourly_ordinary_or_flexible_eur, 2),
            "extras_prorated": extras_prorated,
            "devengos": devengos,
            "totals": {
                "total_devengado_convenio_eur": total_devengado,
            },
            "pending_items": [
                "Cotizaciones del trabajador a Seguridad Social: requieren parametrizacion legal del caso concreto.",
                "IRPF: requiere situacion personal y fiscal.",
                "Nocturnidad, horas extra, IT o incidencias del mes: solo se calculan si se indican expresamente.",
            ],
        }

    def _build_answer(
        self,
        query: str,
        category_match: dict[str, Any],
        contract_type: str | None,
        weekly_hours: float | None,
        extras_prorated: bool | None,
        trienios: int,
        fixed_discontinuous_fit: dict[str, str],
        payroll_draft: dict[str, Any] | None,
    ) -> str:
        parts: list[str] = []

        if category_match["status"] == "clear":
            row: SalaryRow = category_match["row"]
            parts.append(
                f"La categoria que mejor encaja es {row.category.rstrip('.')} con salario base de {row.monthly_14_payments_eur:.2f} EUR en 14 pagas."
            )
        elif category_match["status"] == "ambiguous":
            parts.append(
                f"Veo varias categorias posibles: {', '.join(category_match['alternatives'])}. Necesito que cierres la categoria exacta."
            )
        else:
            parts.append("No puedo fijar todavia la categoria profesional del convenio.")

        if contract_type == "fijo-discontinuo":
            parts.append(fixed_discontinuous_fit["message"])
        elif contract_type is not None:
            parts.append(f"Has pedido modalidad {contract_type}.")
        else:
            parts.append("No has concretado la modalidad contractual.")

        if weekly_hours is not None:
            parts.append(f"La jornada detectada es de {weekly_hours:.2f} horas semanales.")
        else:
            parts.append("Me falta la jornada exacta para cerrar la pre-nomina.")

        if trienios:
            parts.append(f"He aplicado {trienios} trienios de antiguedad.")

        if extras_prorated is True:
            parts.append("He preparado la pre-nomina con pagas extra prorrateadas.")
        elif extras_prorated is False:
            parts.append("He preparado la lectura salarial en 14 pagas, sin prorrata de extras.")

        if payroll_draft is not None:
            total = payroll_draft["totals"]["total_devengado_convenio_eur"]
            parts.append(
                f"El total devengado de convenio del mes activo queda en {total:.2f} EUR, sin calcular aun Seguridad Social ni IRPF."
            )

        if any(token in self._normalize_text(query) for token in SPANISH_ORIGIN_HINTS):
            parts.append(
                "La nacionalidad u origen no cambia estas condiciones de convenio si el trabajo se presta en España; extranjeria se resuelve aparte."
            )

        return " ".join(parts)

    def _build_category_clarification(self, query: str, category_match: dict[str, Any]) -> str:
        if "socorrista" in query:
            return "Indica si el socorrista es Nivel A, Nivel B, Nivel C o socorrista correturnos."
        if category_match["alternatives"]:
            return (
                "Indica la categoría exacta del convenio. Las opciones más cercanas son: "
                + ", ".join(category_match["alternatives"])
                + "."
            )
        return "Indica la categoría exacta del convenio o una descripción más precisa del puesto."

    def _resolve_socorrista_family(self, query: str) -> dict[str, Any] | None:
        if "socorrista" not in query:
            return None

        if "correturn" in query:
            return self._clear_match_for_category("Socorrista correturnos.", 1.0)
        if "nivel a" in query or re.search(r"\bsocorrista a\b", query):
            return self._clear_match_for_category("Nivel A.", 1.0)
        if "nivel b" in query or re.search(r"\bsocorrista b\b", query):
            return self._clear_match_for_category("Nivel B.", 1.0)
        if "nivel c" in query or re.search(r"\bsocorrista c\b", query):
            return self._clear_match_for_category("Nivel C.", 1.0)

        return {
            "status": "ambiguous",
            "score": 0.9,
            "row": self._row_by_category("Nivel B."),
            "alternatives": ["Nivel A.", "Nivel B.", "Nivel C.", "Socorrista correturnos."],
        }

    def _clear_match_for_category(self, category: str, score: float) -> dict[str, Any]:
        row = self._row_by_category(category)
        return {
            "status": "clear",
            "score": score,
            "row": row,
            "alternatives": [row.category],
        }

    def _row_by_category(self, category: str) -> SalaryRow:
        for row in self.salary_rows:
            if row.category == category:
                return row
        raise KeyError(f"Category not found: {category}")

    def _serialize_category_match(self, category_match: dict[str, Any]) -> dict[str, Any]:
        row = category_match.get("row")
        return {
            "status": category_match["status"],
            "score": round(category_match["score"], 4),
            "row": {
                "category": row.category,
                "section": row.section,
                "monthly_14_payments_eur": row.monthly_14_payments_eur,
                "annual_eur": row.annual_eur,
                "hourly_ordinary_or_flexible_eur": row.hourly_ordinary_or_flexible_eur,
            }
            if row
            else None,
            "alternatives": category_match["alternatives"],
        }

    def _select_relevant_sections(self, contract_type: str | None) -> list[dict[str, Any]]:
        titles = {"Contratación y modalidad", "Jornada y descansos", "Retribución", "Vacaciones, permisos y coberturas"}
        if contract_type == "fijo-discontinuo":
            titles.add("Alertas de aplicación")
        return [section for section in self.data["sections"] if section["title"] in titles]

    def _extract_amount_from_condition(self, label: str) -> float:
        item = self.condition_index[self._normalize_text(label)]
        match = re.search(r"(\d+(?:\.\d+)?)\s*EUR", item["detail"])
        if not match:
            return 0.0
        return float(match.group(1))

    @staticmethod
    def _normalize_text(value: str) -> str:
        ascii_value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
        )
        ascii_value = re.sub(r"[^a-z0-9]+", " ", ascii_value)
        return re.sub(r"\s+", " ", ascii_value).strip()
