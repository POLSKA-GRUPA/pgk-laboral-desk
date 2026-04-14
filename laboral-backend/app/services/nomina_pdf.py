"""Generador de pre-nómina PDF — formato oficial español.

Basado en la Orden de 27 de diciembre de 1994 (BOE-A-1995-912),
modificada por Orden ESS/2098/2014 (BOE-A-2014-11637).

Genera un "RECIBO INDIVIDUAL JUSTIFICATIVO DEL PAGO DE SALARIOS"
con todos los campos requeridos legalmente.

IMPORTANTE: Es una PRE-NÓMINA orientativa. No sustituye al software
de nóminas oficial (Sage, A3, NominaPlus, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

# WeasyPrint para PDF; fallback a HTML si no está instalado
try:
    from weasyprint import HTML as WeasyprintHTML

    _HAS_WEASYPRINT = True
except ImportError:
    _HAS_WEASYPRINT = False


@dataclass
class DatosEmpresa:
    nombre: str = ""
    cif: str = ""
    domicilio: str = ""
    ccc: str = ""  # Código Cuenta Cotización


@dataclass
class DatosTrabajador:
    nombre: str = ""
    nif: str = ""
    naf: str = ""  # Número Afiliación SS
    categoria: str = ""
    grupo_profesional: str = ""
    grupo_cotizacion: str = ""
    puesto: str = ""
    antiguedad: str = ""


@dataclass
class PeriodoLiquidacion:
    desde: str = ""
    hasta: str = ""
    total_dias: int = 30


@dataclass
class ConceptoNomina:
    """Un concepto (devengo o deducción) de la nómina."""

    concepto: str
    importe: float
    porcentaje: float | None = None  # solo para deducciones
    es_devengo: bool = True
    es_salarial: bool = True  # False = percepción no salarial
    cotiza_ss: bool = True
    cotiza_irpf: bool = True


@dataclass
class ResultadoNomina:
    """Datos completos para generar la pre-nómina PDF."""

    empresa: DatosEmpresa
    trabajador: DatosTrabajador
    periodo: PeriodoLiquidacion

    # Devengos
    devengos: list[ConceptoNomina] = field(default_factory=list)

    # Deducciones
    deducciones: list[ConceptoNomina] = field(default_factory=list)

    # Totales
    total_devengado: float = 0.0
    total_deducciones: float = 0.0
    liquido: float = 0.0

    # Bases de cotización
    base_cc: float = 0.0
    base_cp: float = 0.0  # contingencias profesionales
    base_irpf: float = 0.0

    # Aportación empresa
    aportacion_empresa: list[ConceptoNomina] = field(default_factory=list)
    total_empresa: float = 0.0
    coste_total_empresa: float = 0.0


def build_nomina_from_simulation(
    sim: dict[str, Any],
    empresa: DatosEmpresa | None = None,
    trabajador_extra: dict[str, Any] | None = None,
    periodo_str: str | None = None,
) -> ResultadoNomina:
    """Construye un ResultadoNomina a partir del resultado de engine.simulate().

    Args:
        sim: Resultado de LaboralEngine.simulate()
        empresa: Datos de la empresa (opcional, se rellena con defaults)
        trabajador_extra: Datos adicionales del trabajador (nif, naf, etc.)
        periodo_str: Periodo en formato "YYYY-MM" (default: mes actual)
    """
    if "error" in sim:
        raise ValueError(f"Simulación con error: {sim['error']}")

    emp = empresa or DatosEmpresa()
    tex = trabajador_extra or {}

    # Periodo
    if periodo_str:
        year, month = map(int, periodo_str.split("-"))
    else:
        today = date.today()
        year, month = today.year, today.month

    import calendar

    _, last_day = calendar.monthrange(year, month)
    periodo = PeriodoLiquidacion(
        desde=f"01/{month:02d}/{year}",
        hasta=f"{last_day}/{month:02d}/{year}",
        total_dias=last_day,
    )

    # Trabajador
    trabajador = DatosTrabajador(
        nombre=tex.get("nombre", ""),
        nif=tex.get("nif", ""),
        naf=tex.get("naf", ""),
        categoria=sim.get("categoria", ""),
        grupo_profesional=sim.get("categoria", ""),
        grupo_cotizacion=sim.get("grupo_cotizacion_ss", ""),
        puesto=tex.get("puesto", sim.get("categoria", "")),
        antiguedad=tex.get("antiguedad", f"{sim.get('antiguedad_anos', 0)} años"),
    )

    # --- DEVENGOS ---
    devengos: list[ConceptoNomina] = []
    for d in sim.get("devengos", []):
        concepto = d.get("concepto", "")
        importe = d.get("eur", 0.0)
        # Plus transporte es percepción no salarial (exento parcial SS)
        es_salarial = "transporte" not in concepto.lower()
        devengos.append(
            ConceptoNomina(
                concepto=concepto,
                importe=importe,
                es_devengo=True,
                es_salarial=es_salarial,
            )
        )

    total_devengado = sim.get("bruto_mensual_eur", 0.0)

    # --- DEDUCCIONES ---
    ss_det = sim.get("ss_detalle", {})
    trab = ss_det.get("trabajador", {})
    irpf_det = sim.get("irpf_detalle", {})

    deducciones: list[ConceptoNomina] = []

    # SS trabajador
    ss_items = [
        ("Contingencias comunes", trab.get("contingencias_comunes", 0), 4.70),
        ("Desempleo", trab.get("desempleo", 0), None),
        ("Formación profesional", trab.get("formacion_profesional", 0), 0.10),
        ("MEI", trab.get("mei", 0), 0.15),
    ]
    # Calcular % desempleo real
    base_cot = ss_det.get("base_cotizacion_eur", total_devengado)
    for label, importe, pct in ss_items:
        if importe > 0:
            if pct is None and base_cot > 0:
                pct = round(importe / base_cot * 100, 2)
            deducciones.append(
                ConceptoNomina(
                    concepto=label,
                    importe=importe,
                    porcentaje=pct,
                    es_devengo=False,
                )
            )

    # IRPF
    irpf_pct = sim.get("irpf_retencion_pct", 0)
    irpf_eur = sim.get("irpf_mensual_eur", 0)
    if irpf_eur > 0:
        deducciones.append(
            ConceptoNomina(
                concepto="I.R.P.F.",
                importe=irpf_eur,
                porcentaje=irpf_pct,
                es_devengo=False,
            )
        )

    total_deducciones = round(sum(d.importe for d in deducciones), 2)
    liquido = round(total_devengado - total_deducciones, 2)

    # --- APORTACIÓN EMPRESA ---
    emp_det = ss_det.get("empresa", {})
    aportacion: list[ConceptoNomina] = []
    emp_items = [
        ("Contingencias comunes", emp_det.get("contingencias_comunes", 0), 23.60),
        ("Desempleo", emp_det.get("desempleo", 0), None),
        ("Formación profesional", emp_det.get("formacion_profesional", 0), 0.60),
        ("FOGASA", emp_det.get("fogasa", 0), 0.20),
        ("AT y EP", emp_det.get("at_ep", 0), None),
        ("MEI", emp_det.get("mei", 0), 0.75),
    ]
    for label, importe, pct in emp_items:
        if importe > 0:
            if pct is None and base_cot > 0:
                pct = round(importe / base_cot * 100, 2)
            aportacion.append(
                ConceptoNomina(
                    concepto=label,
                    importe=importe,
                    porcentaje=pct,
                    es_devengo=False,
                )
            )

    total_emp = round(sum(a.importe for a in aportacion), 2)
    coste_total = round(total_devengado + total_emp, 2)

    return ResultadoNomina(
        empresa=emp,
        trabajador=trabajador,
        periodo=periodo,
        devengos=devengos,
        deducciones=deducciones,
        total_devengado=total_devengado,
        total_deducciones=total_deducciones,
        liquido=liquido,
        base_cc=base_cot,
        base_cp=base_cot,
        base_irpf=irpf_det.get("base_liquidable_eur", total_devengado * 12),
        aportacion_empresa=aportacion,
        total_empresa=total_emp,
        coste_total_empresa=coste_total,
    )


def render_nomina_html(r: ResultadoNomina) -> str:
    """Genera el HTML del recibo de salario en formato oficial español."""

    devengos_salariales = [d for d in r.devengos if d.es_salarial]
    devengos_no_salariales = [d for d in r.devengos if not d.es_salarial]

    def fmt(v: float) -> str:
        """Formatea euros con 2 decimales y separador de miles."""
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def pct(v: float | None) -> str:
        if v is None or v == 0:
            return ""
        return f"{v:.2f}%"

    devengos_sal_rows = ""
    for d in devengos_salariales:
        devengos_sal_rows += f'<tr><td class="concepto">{d.concepto}</td><td class="importe">{fmt(d.importe)}</td></tr>\n'

    devengos_nosal_rows = ""
    for d in devengos_no_salariales:
        devengos_nosal_rows += f'<tr><td class="concepto">{d.concepto}</td><td class="importe">{fmt(d.importe)}</td></tr>\n'

    deduccion_rows = ""
    for d in r.deducciones:
        deduccion_rows += f'<tr><td class="concepto">{d.concepto}</td><td class="pct">{pct(d.porcentaje)}</td><td class="importe">{fmt(d.importe)}</td></tr>\n'

    aportacion_rows = ""
    for a in r.aportacion_empresa:
        aportacion_rows += f'<tr><td class="concepto">{a.concepto}</td><td class="pct">{pct(a.porcentaje)}</td><td class="importe">{fmt(a.importe)}</td></tr>\n'

    today_str = datetime.now().strftime("%d/%m/%Y")
    convenio_nota = "PRE-NÓMINA ORIENTATIVA — No sustituye al recibo oficial de salarios"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 15mm 12mm;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 9pt;
    color: #1a1a1a;
    line-height: 1.35;
  }}
  .watermark {{
    position: fixed;
    top: 40%;
    left: 50%;
    transform: translate(-50%, -50%) rotate(-35deg);
    font-size: 60pt;
    color: rgba(200, 50, 50, 0.06);
    font-weight: bold;
    white-space: nowrap;
    z-index: -1;
    pointer-events: none;
  }}
  .header-title {{
    text-align: center;
    font-size: 10pt;
    font-weight: bold;
    border: 2px solid #333;
    padding: 6px;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .pre-nota {{
    text-align: center;
    font-size: 7.5pt;
    color: #b91c1c;
    margin-bottom: 6px;
    font-weight: 600;
  }}
  .id-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 8px;
  }}
  .id-box {{
    border: 1px solid #555;
    padding: 6px 8px;
  }}
  .id-box h3 {{
    font-size: 8pt;
    text-transform: uppercase;
    color: #555;
    border-bottom: 1px solid #ccc;
    padding-bottom: 2px;
    margin-bottom: 4px;
  }}
  .id-row {{
    display: flex;
    gap: 4px;
    margin-bottom: 2px;
  }}
  .id-label {{
    font-weight: 600;
    font-size: 7.5pt;
    color: #444;
    min-width: 80px;
  }}
  .id-value {{
    font-size: 8.5pt;
  }}
  .periodo-box {{
    border: 1px solid #555;
    padding: 5px 8px;
    margin-bottom: 8px;
    display: flex;
    gap: 20px;
    font-size: 8.5pt;
  }}
  .periodo-box .id-label {{ min-width: 50px; }}

  /* Tables */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1px;
  }}
  th {{
    background: #e8e8e8;
    font-size: 8pt;
    text-transform: uppercase;
    padding: 4px 6px;
    text-align: left;
    border: 1px solid #555;
  }}
  td {{
    padding: 3px 6px;
    border: 1px solid #aaa;
    font-size: 8.5pt;
  }}
  td.concepto {{ text-align: left; }}
  td.pct {{ text-align: center; width: 60px; }}
  td.importe {{ text-align: right; width: 90px; font-variant-numeric: tabular-nums; }}

  .section-label {{
    font-size: 7.5pt;
    font-weight: 700;
    color: #333;
    background: #f0f0f0;
    padding: 3px 6px;
    border: 1px solid #aaa;
    text-transform: uppercase;
  }}

  .total-row td {{
    font-weight: 700;
    background: #f5f5f5;
    border-top: 2px solid #555;
  }}
  .liquido-row td {{
    font-weight: 700;
    font-size: 10pt;
    background: #e0eed0;
    border: 2px solid #333;
    padding: 5px 6px;
  }}

  .bases-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 8px;
  }}
  .bases-box {{
    border: 1px solid #555;
    padding: 4px;
  }}
  .bases-box h3 {{
    font-size: 7.5pt;
    text-transform: uppercase;
    color: #555;
    padding: 2px 4px;
    background: #f0f0f0;
    border-bottom: 1px solid #ccc;
    margin-bottom: 3px;
  }}
  .bases-box table td {{
    font-size: 8pt;
    padding: 2px 4px;
  }}

  .footer {{
    margin-top: 12px;
    display: flex;
    justify-content: space-between;
    font-size: 8pt;
    border-top: 1px solid #aaa;
    padding-top: 6px;
  }}
  .footer-sig {{
    text-align: center;
    min-width: 180px;
  }}
  .footer-sig .line {{
    border-top: 1px solid #333;
    margin-top: 30px;
    padding-top: 3px;
    font-size: 7.5pt;
    color: #555;
  }}
  .coste-nota {{
    margin-top: 8px;
    font-size: 7pt;
    color: #888;
    text-align: center;
    font-style: italic;
  }}
</style>
</head>
<body>
<div class="watermark">PRE-NÓMINA</div>

<div class="pre-nota">{convenio_nota}</div>

<div class="header-title">Recibo Individual Justificativo del Pago de Salarios</div>

<!-- IDENTIFICACIÓN -->
<div class="id-grid">
  <div class="id-box">
    <h3>Empresa</h3>
    <div class="id-row"><span class="id-label">Nombre:</span><span class="id-value">{r.empresa.nombre or "—"}</span></div>
    <div class="id-row"><span class="id-label">CIF:</span><span class="id-value">{r.empresa.cif or "—"}</span></div>
    <div class="id-row"><span class="id-label">Domicilio:</span><span class="id-value">{r.empresa.domicilio or "—"}</span></div>
    <div class="id-row"><span class="id-label">CCC:</span><span class="id-value">{r.empresa.ccc or "—"}</span></div>
  </div>
  <div class="id-box">
    <h3>Trabajador</h3>
    <div class="id-row"><span class="id-label">Nombre:</span><span class="id-value">{r.trabajador.nombre or "—"}</span></div>
    <div class="id-row"><span class="id-label">NIF:</span><span class="id-value">{r.trabajador.nif or "—"}</span></div>
    <div class="id-row"><span class="id-label">Nº Afil. SS:</span><span class="id-value">{r.trabajador.naf or "—"}</span></div>
    <div class="id-row"><span class="id-label">Categoría:</span><span class="id-value">{r.trabajador.categoria or "—"}</span></div>
    <div class="id-row"><span class="id-label">Grupo Cot.:</span><span class="id-value">{r.trabajador.grupo_cotizacion or "—"}</span></div>
    <div class="id-row"><span class="id-label">Antigüedad:</span><span class="id-value">{r.trabajador.antiguedad or "—"}</span></div>
  </div>
</div>

<!-- PERIODO -->
<div class="periodo-box">
  <div class="id-row"><span class="id-label">Periodo:</span><span class="id-value">Del {r.periodo.desde} al {r.periodo.hasta}</span></div>
  <div class="id-row"><span class="id-label">Total días:</span><span class="id-value">{r.periodo.total_dias}</span></div>
</div>

<!-- DEVENGOS -->
<table>
  <thead>
    <tr><th colspan="2">I. Devengos</th></tr>
  </thead>
  <tbody>
    <tr><td colspan="2" class="section-label">A. Percepciones salariales</td></tr>
    {devengos_sal_rows}
    {'<tr><td colspan="2" class="section-label">B. Percepciones no salariales</td></tr>' + devengos_nosal_rows if devengos_no_salariales else ""}
    <tr class="total-row"><td class="concepto">TOTAL DEVENGADO</td><td class="importe">{fmt(r.total_devengado)}</td></tr>
  </tbody>
</table>

<!-- DEDUCCIONES -->
<table>
  <thead>
    <tr><th>II. Deducciones</th><th style="width:60px;text-align:center">%</th><th style="width:90px;text-align:right">Importe</th></tr>
  </thead>
  <tbody>
    <tr><td colspan="3" class="section-label">A. Cotizaciones del trabajador a la SS</td></tr>
    {deduccion_rows}
    <tr class="total-row"><td class="concepto">TOTAL A DEDUCIR</td><td class="pct"></td><td class="importe">{fmt(r.total_deducciones)}</td></tr>
  </tbody>
</table>

<!-- LÍQUIDO -->
<table>
  <tbody>
    <tr class="liquido-row">
      <td class="concepto">LÍQUIDO TOTAL A PERCIBIR</td>
      <td class="importe">{fmt(r.liquido)} €</td>
    </tr>
  </tbody>
</table>

<!-- BASES DE COTIZACIÓN + APORTACIÓN EMPRESA -->
<div class="bases-grid">
  <div class="bases-box">
    <h3>Bases de cotización</h3>
    <table>
      <tr><td>Base CC</td><td class="importe">{fmt(r.base_cc)}</td></tr>
      <tr><td>Base CP (AT/EP, Desempleo, FP, FOGASA)</td><td class="importe">{fmt(r.base_cp)}</td></tr>
      <tr><td>Base IRPF (anual)</td><td class="importe">{fmt(r.base_irpf)}</td></tr>
    </table>
  </div>
  <div class="bases-box">
    <h3>Aportación de la empresa</h3>
    <table>
      {aportacion_rows}
      <tr class="total-row"><td>Total empresa</td><td class="importe">{fmt(r.total_empresa)}</td></tr>
      <tr style="background:#e8f5e9"><td><strong>Coste total empresa</strong></td><td class="importe"><strong>{fmt(r.coste_total_empresa)}</strong></td></tr>
    </table>
  </div>
</div>

<!-- PIE -->
<div class="footer">
  <div>
    <div>{today_str}</div>
  </div>
  <div class="footer-sig">
    <div class="line">Sello y firma de la empresa</div>
  </div>
  <div class="footer-sig">
    <div class="line">Recibí (firma del trabajador)</div>
  </div>
</div>

<div class="coste-nota">
  Documento generado por PGK Laboral Desk · Pre-nómina orientativa · Orden 27/12/1994 (BOE-A-1995-912) mod. Orden ESS/2098/2014
</div>

</body>
</html>"""
    return html


def generate_nomina_pdf(r: ResultadoNomina) -> bytes:
    """Genera el PDF de la pre-nómina. Requiere WeasyPrint."""
    if not _HAS_WEASYPRINT:
        raise RuntimeError("WeasyPrint no está instalado. Ejecuta: pip install weasyprint")
    html = render_nomina_html(r)
    return WeasyprintHTML(string=html).write_pdf()


def generate_nomina_html_string(r: ResultadoNomina) -> str:
    """Genera solo el HTML (para preview o descarga como .html)."""
    return render_nomina_html(r)
