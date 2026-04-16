"""Parser de nóminas PDF para auditoría — PGK Laboral Desk.

Extiende el parser de conta-pgk-hispania (contabilizar_nominas.py) para extraer
TODOS los campos necesarios para una auditoría completa de nóminas:

- Cada línea de devengo (salario base, antigüedad, transporte, prorrata extras, etc.)
- Cada línea de deducción (CC, desempleo, FP, MEI, IRPF, embargos)
- Base de cotización SS (usada realmente en el PDF)
- Grupo de cotización y categoría profesional
- Fecha de antigüedad, NIF, NAF (número afiliación SS)
- Periodo de liquidación (mes, año, días)
- Aportaciones empresa (CC, AT/EP, desempleo, FP, FOGASA)
- Coste total empresa

Formato soportado: Sage/A3 Nómina (layout SEPE estándar).
Usa pdftotext -layout para preservar columnas.

Referencia de diseño: conta-pgk-hispania/scripts/contabilizar_nominas.py
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _num(s: str) -> float:
    """Convierte '1.234,56' → 1234.56."""
    if not s:
        return 0.0
    return float(s.replace(".", "").replace(",", "."))


def _safe_group(m: re.Match | None, group: int = 1, default: str = "") -> str:
    """Extrae grupo de un match, con fallback seguro."""
    return m.group(group).strip() if m else default


# ─── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class DevengoLine:
    """Línea individual de devengo extraída del PDF."""

    concepto: str
    importe: float

    # Clasificación automática del tipo de devengo
    tipo: str = ""  # "salario_base", "antiguedad", "transporte", "prorrata_extra",
    # "complemento", "horas_extras", "otro"


@dataclass
class DeduccionLine:
    """Línea individual de deducción extraída del PDF."""

    concepto: str
    base: float  # Base sobre la que se aplica
    tipo_pct: float  # Porcentaje aplicado
    importe: float

    # Clasificación
    tipo: str = ""  # "cc", "desempleo", "fp", "mei", "irpf", "embargo", "otro"


@dataclass
class AportacionEmpresa:
    """Línea de aportación de la empresa extraída del PDF."""

    concepto: str
    base: float
    tipo_pct: float
    importe: float

    tipo: str = ""  # "cc", "at_ep", "desempleo", "fp", "fogasa", "mei", "otro"


@dataclass
class ParsedNomina:
    """Nómina completamente parseada desde PDF para auditoría."""

    # Identificación
    nombre_trabajador: str
    nif: str
    naf: str  # Número afiliación SS
    numero_empleado: str

    # Empresa
    empresa_nombre: str
    empresa_cif: str
    empresa_domicilio: str
    empresa_ccc: str  # Código Cuenta de Cotización

    # Clasificación profesional
    grupo_profesional: str  # Categoría del convenio
    grupo_cotizacion: str  # Grupo SS (01-11)
    fecha_antiguedad: str  # DD/MM/AAAA

    # Periodo
    periodo_desde: str  # DD
    periodo_mes: str  # Nombre del mes
    periodo_hasta: str  # DD
    periodo_anio: str  # AAAA
    periodo_dias: int  # Total días

    # Devengos
    devengos: list[DevengoLine] = field(default_factory=list)
    total_devengado: float = 0.0

    # Deducciones
    deducciones_ss: list[DeduccionLine] = field(default_factory=list)
    irpf_base: float = 0.0
    irpf_pct: float = 0.0
    irpf_importe: float = 0.0
    embargos: list[dict[str, Any]] = field(default_factory=list)
    total_deducciones: float = 0.0

    # Resultado
    liquido: float = 0.0

    # SS Trabajador (resumen)
    ss_trab_total: float = 0.0

    # Empresa: aportaciones y coste
    aportaciones_empresa: list[AportacionEmpresa] = field(default_factory=list)
    base_cotizacion_ss: float = 0.0  # La base real usada en el PDF
    ss_emp_total: float = 0.0
    coste_total_empresa: float = 0.0

    # Base sujeta a IRPF
    base_irpf: float = 0.0

    # Metadata
    pdf_filename: str = ""
    parse_errors: list[str] = field(default_factory=list)


# ─── Clasificadores de concepto ───────────────────────────────────────────────

_DEVENGO_CLASSIFY = [
    (r"(?i)salario\s*base", "salario_base"),
    (r"(?i)antig.*edad", "antiguedad"),
    (r"(?i)plus\s*transporte|transporte", "transporte"),
    (r"(?i)p\.?p\.?\s*verano|prorrata.*verano", "prorrata_extra"),
    (r"(?i)p\.?p\.?\s*navidad|prorrata.*navidad", "prorrata_extra"),
    (r"(?i)prorrata\s*pagas|paga\s*extra", "prorrata_extra"),
    (r"(?i)horas\s*extra", "horas_extras"),
    (r"(?i)complemento|productividad|a\s*cuenta", "complemento"),
    (r"(?i)gratificaci.*extraordinaria", "gratificacion_extra"),
    (r"(?i)salario\s*en\s*especie", "especie"),
]

_DEDUC_CLASSIFY = [
    (r"(?i)contingencias\s*comunes|c\.c\.?", "cc"),
    (r"(?i)desempleo", "desempleo"),
    (r"(?i)formaci.*n\s*profesional|f\.?p\.?", "fp"),
    (r"(?i)m\.?e\.?i\.?|mecanismo\s*equidad", "mei"),
    (r"(?i)horas\s*extras?\s*(fuerza\s*mayor|resto)", "he_ss"),
    (r"(?i)irpf|renta\s*de\s*las\s*personas", "irpf"),
    (r"(?i)embargo|tgss|juzgado", "embargo"),
]

_EMPRESA_CLASSIFY = [
    (r"(?i)contingencias\s*comunes", "cc"),
    (r"(?i)at\s*y\s*ep|accidentes", "at_ep"),
    (r"(?i)desempleo", "desempleo"),
    (r"(?i)formaci.*n\s*profesional", "fp"),
    (r"(?i)fondo\s*garant|fogasa", "fogasa"),
    (r"(?i)m\.?e\.?i\.?|mecanismo\s*equidad", "mei"),
]


def _classify(text: str, rules: list[tuple[str, str]]) -> str:
    """Clasifica un concepto usando reglas regex ordenadas por prioridad."""
    for pattern, label in rules:
        if re.search(pattern, text):
            return label
    return "otro"


# ─── Parser principal ─────────────────────────────────────────────────────────


def pdf_to_text(pdf_path: str | Path) -> str:
    """Extrae texto de un PDF usando pdftotext -layout."""
    r = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return r.stdout


def parse_nomina(pdf_path: str | Path) -> ParsedNomina | None:
    """Parsea un PDF de nómina Sage/A3 y devuelve estructura completa para auditoría.

    Args:
        pdf_path: Ruta al archivo PDF de nómina.

    Returns:
        ParsedNomina con todos los campos extraídos, o None si no es una nómina válida.
    """
    pdf_path = Path(pdf_path)
    text = pdf_to_text(pdf_path)

    # Verificar que es una nómina
    if "Trabajador:" not in text and "trabajador:" not in text.lower():
        return None

    nom = ParsedNomina(
        nombre_trabajador="",
        nif="",
        naf="",
        numero_empleado="",
        empresa_nombre="",
        empresa_cif="",
        empresa_domicilio="",
        empresa_ccc="",
        grupo_profesional="",
        grupo_cotizacion="",
        fecha_antiguedad="",
        periodo_desde="",
        periodo_mes="",
        periodo_hasta="",
        periodo_anio="",
        periodo_dias=0,
        pdf_filename=pdf_path.name,
    )

    # ── Cabecera: Trabajador ──
    m = re.search(r"Trabajador:\s+(.+?)(?:\s{2,}|\n)", text)
    if m:
        nom.nombre_trabajador = m.group(1).strip()
    else:
        return None  # Sin nombre no hay nómina

    # ── Cabecera: NIF ──
    m = re.search(r"NIF:\s+([\w\d]+)", text)
    if m:
        nom.nif = m.group(1).strip()

    # ── NAF (Número afiliación SS) ──
    m = re.search(r"[Nn][úu]mero\s+de\s+afiliaci[oó]n[^:]*:\s*([\d]+)", text)
    if m:
        nom.naf = m.group(1).strip()

    # ── Número empleado ──
    m = re.search(r"[Nn][úu]mero\s+empleado[^:]*:\s*(\S+)", text)
    if m:
        nom.numero_empleado = m.group(1).strip()

    # ── Grupo profesional ──
    m = re.search(r"Grupo profesional:\s+(.+?)(?:\s{2,}|\n)", text)
    if m:
        nom.grupo_profesional = m.group(1).strip()

    # ── Grupo de Cotización SS ──
    m = re.search(r"Grupo de Cotizaci[oó]n:\s*(\d+)", text)
    if m:
        nom.grupo_cotizacion = m.group(1).strip()

    # ── Fecha de antigüedad ──
    m = re.search(r"Fecha de antig[üu]edad:\s*(\d{2}/\d{2}/\d{2,4})", text)
    if m:
        nom.fecha_antiguedad = m.group(1).strip()

    # ── Empresa ──
    m = re.search(r"Empresa:\s+(.+?)(?:\s{2,}|\n)", text)
    if m:
        nom.empresa_nombre = m.group(1).strip()
    # La segunda parte del nombre puede estar en la misma línea
    m2 = re.search(r"Empresa:.*?INTEGRAL\s+(.*?)Trabajador:", text, re.DOTALL)
    if m2:
        # Reconstruir nombre completo (la empresa MPC se divide en dos columnas)
        pass

    m = re.search(r"CIF:\s+([\w\d]+)", text)
    if m:
        nom.empresa_cif = m.group(1).strip()

    m = re.search(r"Domicilio:\s+(.+?)(?:\s{2,}|\n)", text)
    if m:
        nom.empresa_domicilio = m.group(1).strip()

    m = re.search(r"[Cc][oó]digo\s+de\s+Cuenta\s+de\s+Cotizaci[oó]n[^:]*:\s*([\d]+)", text)
    if m:
        nom.empresa_ccc = m.group(1).strip()

    # ── Periodo de liquidación ──
    # "del    1     de    Marzo  al 31 de  Marzo  de 2026  Total días [ 30 ]"
    m = re.search(
        r"del\s+(\d+)\s+de\s+(\w+)\s+al\s+(\d+)\s+de\s+\w+\s+de\s+(\d{4})\s+"
        r"Total\s+d[ií]as\s*\[\s*(\d+)\s*\]",
        text,
    )
    if m:
        nom.periodo_desde = m.group(1)
        nom.periodo_mes = m.group(2)
        nom.periodo_hasta = m.group(3)
        nom.periodo_anio = m.group(4)
        nom.periodo_dias = int(m.group(5))

    # ── Total devengado (parse before devengos for subtotal dedup check) ──
    m = re.search(r"A\.\s+TOTAL DEVENGADO.*?([\d.]+,\d{2})", text, re.MULTILINE)
    if m:
        nom.total_devengado = _num(m.group(1))

    # ── Devengos individuales (sección I) ──
    _parse_devengos(text, nom)

    # ── Deducciones SS (sección II.1) ──
    _parse_deducciones_ss(text, nom)

    # ── IRPF ──
    m = re.search(
        r"(?:f[ií]sicas|IRPF)\s+([\d.]+,\d{2})\s+([\d]+[,.]?\d*)\s*%?\s*([\d.]+,\d{2})",
        text,
    )
    if m:
        nom.irpf_base = _num(m.group(1))
        nom.irpf_pct = float(m.group(2).replace(",", "."))
        nom.irpf_importe = _num(m.group(3))

    # ── Embargos / retenciones adicionales ──
    _parse_embargos(text, nom)

    # ── Total deducciones ──
    m = re.search(r"B\.\s+TOTAL A DEDUCIR.*?([\d.]+,\d{2})", text, re.MULTILINE)
    if m:
        nom.total_deducciones = _num(m.group(1))

    # ── Líquido ──
    m = re.search(r"L[IÍ]QUIDO TOTAL A PERCIBIR.*?([\d.]+,\d{2})", text, re.MULTILINE)
    if m:
        nom.liquido = _num(m.group(1))

    # ── Total aportaciones trabajador ──
    m = re.search(r"TOTAL APORTACIONES\s*\.+\s*([\d.]+,\d{2})", text)
    if m:
        nom.ss_trab_total = _num(m.group(1))

    # ── Base de cotización SS y aportaciones empresa ──
    _parse_aportaciones_empresa(text, nom)

    # ── Coste total empresa ──
    # Sage/A3 variations:
    #   "Total coste:  1.273,01" (same line)
    #   "Total coste:\n  1.273,01  Total: 312,25" (next line, mixed with Total:)
    #   "Total coste:\n\n  1.273,01" (line after blank)
    coste_patterns = [
        r"Total\s+coste.*?:\s*([\d.]+,\d{2})",
        r"Total\s+coste.*?:\s*\n\s*([\d.]+,\d{2})",
        r"Total\s+coste.*?:\s*\n[^\d]*([\d.]+,\d{2})",
        r"Total\s+coste\s+empresa.*?:\s*([\d.]+,\d{2})",
    ]
    for cp in coste_patterns:
        m = re.search(cp, text, re.IGNORECASE)
        if m:
            nom.coste_total_empresa = _num(m.group(1))
            break

    # ── Base IRPF ──
    m = re.search(r"Base sujeta a retenci[oó]n del IRPF\s+([\d.]+,\d{2})", text)
    if m:
        nom.base_irpf = _num(m.group(1))

    # ── Verificación de integridad ──
    _verify_integrity(nom)

    return nom


# ─── Sub-parsers ──────────────────────────────────────────────────────────────


def _parse_devengos(text: str, nom: ParsedNomina) -> None:
    """Extrae cada línea de devengo de la sección I del PDF.

    Layout típico (pdftotext -layout):

        Salario base                                        1.221,00
        ANTIGÜEDAD                                             101,00
        P.P.VERANO                                             101,75
        P.P.NAVIDAD                                            101,75
        PLUS TRANSPORTE                                        114,45
        A CUENTA CONVENIO                                       56,89

    Nota: pdftotext puede romper caracteres UTF-8 (U mayus + diéresis → 2 bytes, etc).
    Los patrones usan rangos Unicode explicitos en lugar de ``\\w`` para robustez.
    """
    m_section = re.search(r"I\. DEVENGOS(.*?)A\.\s+TOTAL DEVENGADO", text, re.DOTALL)
    devengo_section = m_section.group(1) if m_section else text

    seen_concepts: set[str] = set()

    specific_devengos = [
        (r"Salario base\s+([\d.]+,\d{2})", "Salario base"),
        (r"Horas extraordinarias\s+([\d.]+,\d{2})", "Horas extraordinarias"),
    ]
    for pattern, label in specific_devengos:
        m = re.search(pattern, devengo_section, re.MULTILINE)
        if m:
            _add_devengo(nom, label, _num(m.group(1)), seen_concepts)

    skip_concepts = {
        "IMPORTE",
        "TOTALES",
        "TOTAL",
        "PERCEPCIONES SALARIALES",
        "PERCEPCIONES NO SALARIALES",
        "Complementos salariales",
        "Gratificaciones extraordinarias",
        "Salario en especie",
        "Indemnizaciones o suplidos",
    }

    # Sage/A3 layout has two columns per PDF row:
    #   col1 (Percepciones salariales) | col2 (Percepciones no salariales)
    # pdftotext merges them on one line. Amount at pos ~53-60 = col1, right text = col2.
    for m in re.finditer(
        r"^\s{2,}([A-ZÁÉÍÓÚÑÜ\.\s]+?)\s{2,}([\d.]+,\d{2})",
        devengo_section,
        re.MULTILINE,
    ):
        concepto = m.group(1).strip()
        if not concepto or concepto in skip_concepts:
            continue
        concepto_clean = re.sub(r"\s+", " ", concepto).strip()
        if not concepto_clean:
            continue
        _add_devengo(nom, concepto_clean, _num(m.group(2)), seen_concepts)

    # Sage/A3: "Percepciones no salariales" subtotal appears as a standalone amount
    # at column position ~53 (same as left IMPORTE), with no concept label on the line.
    # Only add it if we haven't already captured the individual items it represents.
    subtotal_label = "Percepciones no salariales (subtotal)"
    if subtotal_label not in seen_concepts:
        sum_before_subtotal = sum(d.importe for d in nom.devengos)
        for m in re.finditer(
            r"^\s{40,}([\d.]+,\d{2})\s*$",
            devengo_section,
            re.MULTILINE,
        ):
            amount = _num(m.group(1))
            if amount > 0 and abs(sum_before_subtotal + amount - nom.total_devengado) < 0.50:
                # Adding this subtotal would make the sum ≈ total_devengado,
                # but individual items might already account for it.
                # Only add if the current sum is far from total_devengado.
                if abs(sum_before_subtotal - nom.total_devengado) > 1.00:
                    _add_devengo(nom, subtotal_label, amount, seen_concepts)
            elif amount > 0 and abs(sum_before_subtotal - nom.total_devengado) > 1.00:
                _add_devengo(nom, subtotal_label, amount, seen_concepts)


def _add_devengo(nom: ParsedNomina, concepto: str, importe: float, seen: set[str]) -> None:
    """Añade una línea de devengo clasificada."""
    if concepto in seen or importe <= 0:
        return
    seen.add(concepto)
    tipo = _classify(concepto, _DEVENGO_CLASSIFY)
    nom.devengos.append(DevengoLine(concepto=concepto, importe=importe, tipo=tipo))


def _parse_deducciones_ss(text: str, nom: ParsedNomina) -> None:
    """Extrae cada línea de cotización SS del trabajador de la sección II.1.

    Layout típico (pdftotext -layout):

        Contingencias comunes1.525,50 4,70 % 71,70
        Desempleo             1.525,50 1,55 % 23,65
        Formación Profesional 1.525,50 0,10 %  1,53
        M.E.I.                1.525,50 0,15     2,29

    Nota: 'Contingencias comunes' pega la base al nombre del concepto (sin espacio).
    """
    # "II. DEDUCCIONES" to "DETERMINACIÓN DE LAS BASES" — only the deductions,
    # not the empresa bases section which has similar line patterns.
    ss_section = text
    m_section = re.search(
        r"II\. DEDUCCIONES(.*?)DETERMINACI",
        text,
        re.DOTALL,
    )
    if not m_section:
        m_section = re.search(
            r"II\. DEDUCCIONES(.*?)B\.\s+TOTAL A DEDUCIR",
            text,
            re.DOTALL,
        )
    if m_section:
        ss_section = m_section.group(1)

    # Patrón universal: CONCEPTO + BASE + PCT + IMPORTE
    # La base puede ir pegada al concepto (CC) o separada por espacios
    deducciones_config = [
        (
            r"Contingencias\s*comunes\s*([\d.]+,\d{2})\s+([\d,\.]+)\s*%?\s*([\d.]+,\d{2})",
            "Contingencias comunes",
            "cc",
        ),
        (r"Desempleo\s+([\d.]+,\d{2})\s+([\d,\.]+)\s*%\s*([\d.]+,\d{2})", "Desempleo", "desempleo"),
        (
            r"Formaci.*?n\s*Profesional\s+([\d.]+,\d{2})\s+([\d,\.]+)\s*%?\s*([\d.]+,\d{2})",
            "Formación Profesional",
            "fp",
        ),
        (r"M\.?\s*E\.?\s*I\.?\s+([\d.]+,\d{2})\s+([\d,\.]+)\s+([\d.]+,\d{2})", "M.E.I.", "mei"),
        (
            r"Horas\s*extras\s*Fuerza\s*mayor\s*([\d.]+,\d{2})?\s*([\d,\.]+)?\s*%?\s*([\d.]+,\d{2})?",
            "Horas extras Fuerza mayor",
            "he_ss",
        ),
        (
            r"Horas\s*extras\s*Resto\s*([\d.]+,\d{2})?\s*([\d,\.]+)?\s*%?\s*([\d.]+,\d{2})?",
            "Horas extras Resto",
            "he_ss",
        ),
    ]

    for pattern, concepto, tipo_default in deducciones_config:
        m = re.search(pattern, ss_section)
        if m:
            base = _num(m.group(1)) if m.group(1) else 0.0
            tipo_pct = float(m.group(2).replace(",", ".")) if m.group(2) else 0.0
            importe = _num(m.group(3)) if m.group(3) else 0.0
            if importe > 0:
                nom.deducciones_ss.append(
                    DeduccionLine(
                        concepto=concepto,
                        base=base,
                        tipo_pct=tipo_pct,
                        importe=importe,
                        tipo=tipo_default,
                    )
                )


def _parse_embargos(text: str, nom: ParsedNomina) -> None:
    """Extrae embargos y retenciones adicionales (sección II.5).

    Sage/A3 layout splits embargo across 3 lines:

        Horas extras Fuerza mayor         %         EMBARGO
                                                     5. Otras           TGSS
                                                       deducciones                                     230,60
    """
    # Multi-line embargo: EMBARGO...TGSS...deducciones...230,60
    m = re.search(
        r"EMBARGO\s*\n.*?TGSS\s*\n.*?deducciones\s+([\d.]+,\d{2})",
        text,
        re.DOTALL,
    )
    if m:
        nom.embargos.append(
            {"tipo": "embargo_tgss", "concepto": "Embargo TGSS", "importe": _num(m.group(1))}
        )
        return

    # Single-line: EMBARGO TGSS 230,60
    m = re.search(r"EMBARGO\s+TGSS\s+([\d.]+,\d{2})", text)
    if m:
        nom.embargos.append(
            {"tipo": "embargo_tgss", "concepto": "Embargo TGSS", "importe": _num(m.group(1))}
        )
        return

    # Generic embargo with amount
    m = re.search(r"EMBARGO\s*\n.*?([\d.]+,\d{2})", text, re.DOTALL)
    if m:
        nom.embargos.append({"tipo": "embargo", "concepto": "Embargo", "importe": _num(m.group(1))})


def _parse_aportaciones_empresa(text: str, nom: ParsedNomina) -> None:
    """Extrae aportaciones de la empresa desde la sección de cálculo de bases.

    Layout típico (tabular):

        Contingencias comunes ... 1.525,50  24,35  371,46
        AT y EP .................. 1.525,50   1,85   28,23
        Desempleo ............... 1.525,50   5,50   83,90
        Formación Profesional ... 1.525,50   0,60    9,15
        Fondo Garantía Salarial .. 1.525,50   0,20    3,05
    """
    # Buscar la sección de aportaciones empresa
    # El límite derecho varía: "Total coste", "Total  coste", o fin del documento
    m_section = re.search(
        r"APORTACI[NÓ].*?EMPRESA(.*?)(?:Total\s+coste|Z_ECUE|Recibo|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not m_section:
        return

    section = m_section.group(1)

    aportaciones_config = [
        # "TOTAL" line under "1. Contingencias comunes" section
        (
            r"TOTAL\s+\.+\s*([\d.]+,\d{2})\s+([\d,\.]+)\s+([\d.]+,\d{2})",
            "Contingencias comunes",
            "cc",
        ),
        (r"AT\s*y\s*EP.*?([\d.]+,\d{2})\s+([\d,\.]+)\s+([\d.]+,\d{2})", "AT y EP", "at_ep"),
        (r"Desempleo.*?([\d.]+,\d{2})\s+([\d,\.]+)\s+([\d.]+,\d{2})", "Desempleo", "desempleo"),
        (
            r"Formaci.*?n\s*Profesional.*?([\d.]+,\d{2})\s+([\d,\.]+)\s+([\d.]+,\d{2})",
            "Formación Profesional",
            "fp",
        ),
        (
            r"Fondo\s*Garant.*?([\d.]+,\d{2})\s+([\d,\.]+)\s+([\d.]+,\d{2})",
            "Fondo Garantía Salarial",
            "fogasa",
        ),
    ]

    for pattern, concepto, tipo_default in aportaciones_config:
        m = re.search(pattern, section)
        if m:
            base = _num(m.group(1))
            tipo_pct = float(m.group(2).replace(",", "."))
            importe = _num(m.group(3))
            if importe > 0:
                nom.aportaciones_empresa.append(
                    AportacionEmpresa(
                        concepto=concepto,
                        base=base,
                        tipo_pct=tipo_pct,
                        importe=importe,
                        tipo=tipo_default,
                    )
                )

    # Extraer Total: empresa
    # "Total:" in empresa section shows sum of all empresa aportaciones
    # It appears after "4. Base sujeta a retención del IRPF"
    m_total = re.search(r"Total:\s+([\d.]+,\d{2})\s*$", text, re.MULTILINE)
    if m_total:
        nom.ss_emp_total = _num(m_total.group(1))

    # La base de cotización SS es la que aparece en la sección de empresa
    # (puede diferir del total devengado si hay topes)
    # "Importe remuneración mensual" es la primera línea
    m_base = re.search(r"Importe remuneraci[oó]n mensual.*?([\d.]+,\d{2})", text)
    if m_base:
        nom.base_cotizacion_ss = _num(m_base.group(1))

    # Si no encontró la base en la sección empresa, usar la de Contingencias comunes
    if nom.base_cotizacion_ss == 0.0 and nom.aportaciones_empresa:
        nom.base_cotizacion_ss = nom.aportaciones_empresa[0].base


def _verify_integrity(nom: ParsedNomina) -> None:
    """Verifica integridad básica del parseo y registra errores."""
    # Total devengado = suma de devengos individuales
    suma_devengos = sum(d.importe for d in nom.devengos)
    if nom.total_devengado > 0 and abs(suma_devengos - nom.total_devengado) > 0.02:
        nom.parse_errors.append(
            f"Suma devengos ({suma_devengos:.2f}) != Total devengado ({nom.total_devengado:.2f})"
        )

    # SS trabajador = suma de deducciones SS
    suma_ss = sum(d.importe for d in nom.deducciones_ss)
    if nom.ss_trab_total > 0 and abs(suma_ss - nom.ss_trab_total) > 0.02:
        nom.parse_errors.append(
            f"Suma SS trab ({suma_ss:.2f}) != Total aportaciones ({nom.ss_trab_total:.2f})"
        )

    # SS empresa = suma de aportaciones empresa
    suma_emp = sum(a.importe for a in nom.aportaciones_empresa)
    if nom.ss_emp_total > 0 and abs(suma_emp - nom.ss_emp_total) > 0.02:
        nom.parse_errors.append(
            f"Suma SS emp ({suma_emp:.2f}) != Total SS emp ({nom.ss_emp_total:.2f})"
        )

    # Coste empresa = devengos salariales + SS empresa
    devengos_salariales = nom.total_devengado  # Simplificado
    coste_calculado = devengos_salariales + nom.ss_emp_total
    if (
        nom.coste_total_empresa > 0
        and nom.ss_emp_total > 0
        and abs(coste_calculado - nom.coste_total_empresa) > 0.02
    ):
        nom.parse_errors.append(
            f"Coste calculado ({coste_calculado:.2f}) != Coste PDF ({nom.coste_total_empresa:.2f})"
        )


# ─── Batch parsing ────────────────────────────────────────────────────────────


def parse_month_folder(folder: str | Path) -> list[ParsedNomina]:
    """Parsea todos los PDFs de nóminas de una carpeta de mes."""
    folder = Path(folder)
    records: list[ParsedNomina] = []
    seen_names: set[str] = set()

    for fname in sorted(folder.iterdir()):
        if not fname.suffix.upper() == ".PDF":
            continue

        parsed = parse_nomina(fname)
        if parsed is None:
            continue

        if parsed.total_devengado <= 0:
            continue

        if parsed.nombre_trabajador in seen_names:
            # Duplicado — nómina complementaria o liquidación
            continue

        records.append(parsed)
        seen_names.add(parsed.nombre_trabajador)

    return records


def parse_trimester(root_folder: str | Path) -> dict[str, list[ParsedNomina]]:
    """Parsea todos los meses de una carpeta de trimestre.

    Args:
        root_folder: Carpeta con subcarpetas por mes (ENERO/, FEBRERO/, MARZO/)

    Returns:
        Dict {nombre_mes: [ParsedNomina, ...]}
    """
    root = Path(root_folder)
    result: dict[str, list[ParsedNomina]] = {}

    for month_dir in sorted(root.iterdir()):
        if not month_dir.is_dir():
            continue

        records = parse_month_folder(month_dir)
        if records:
            # Capitalizar nombre del mes
            month_name = month_dir.name.capitalize()
            result[month_name] = records

    return result
