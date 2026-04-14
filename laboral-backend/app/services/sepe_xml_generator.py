"""SEPE Contrat@ XML generator.

Generates valid XML from Employee + Company + Contract data
following the official EsquemaContratos50.xsd schema.

Reference: https://www.sepe.es/DocumComunicacto/xml/14/EsquemaContratos50.xsd
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from lxml import etree

from app.services.sepe_mapper import SEPEContractMapping, resolve_pgk_to_sepe

logger = logging.getLogger(__name__)

XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
XSD_FILENAME = "EsquemaContratos50.xsd"


def _date_to_sepe(date_str: str) -> str:
    """Convert YYYY-MM-DD to SEPE AAAAMMDD format."""
    return date_str.replace("-", "")


def _hours_to_sepe(total_hours: float) -> str:
    """Convert hours decimal to SEPE HHHHMM format."""
    hours = int(total_hours)
    minutes = int(round((total_hours - hours) * 60))
    return f"{hours:04d}{minutes:02d}"


def _pad_occupation(code: str) -> str:
    """Pad 4-digit occupation code to 8 chars (4 trailing spaces per SEPE spec)."""
    return f"{code[:4]:<8}"


def _build_datos_empresa(
    cif_nif: str,
    codigo_cuenta_cotizacion: str,
) -> etree._Element:
    empresa = etree.SubElement(etree.Element("_placeholder"), "DATOS_EMPRESA")
    etree.SubElement(empresa, "CIF_NIF_EMPRESA").text = cif_nif.upper().strip()
    etree.SubElement(empresa, "CODIGO_CUENTA_COTIZACION").text = codigo_cuenta_cotizacion.strip()
    return empresa


def _build_datos_trabajador(
    nif: str,
    nombre_apellidos: str,
    sexo: str,
    fecha_nacimiento: str,
    nacionalidad: str = "724",
    municipio_residencia: str = "",
    pais_residencia: str = "724",
    num_afiliacion_ss: str = "",
    domicilio: str = "",
) -> etree._Element:
    trabajador = etree.Element("DATOS_TRABAJADOR")

    doc_type_prefix = nif[0].upper() if nif else "D"

    etree.SubElement(trabajador, "IDENTIFICADORPFISICA").text = nif.upper().strip()
    etree.SubElement(trabajador, "NOMBRE_APELLIDOS").text = nombre_apellidos.upper().strip()

    sexo_map = {"M": "1", "F": "2", "H": "1", "V": "2", "1": "1", "2": "2", "6": "6"}
    sexo_val = sexo_map.get(sexo.upper() if len(sexo) == 1 else sexo, "1")
    etree.SubElement(trabajador, "SEXO").text = sexo_val

    etree.SubElement(trabajador, "FECHA_NACIMIENTO").text = (
        fecha_nacimiento.replace("-", "") if "-" in fecha_nacimiento else fecha_nacimiento
    )
    etree.SubElement(trabajador, "NACIONALIDAD").text = nacionalidad

    if pais_residencia == "724" and municipio_residencia:
        etree.SubElement(trabajador, "MUNICIPIO_RESIDENCIA").text = municipio_residencia

    etree.SubElement(trabajador, "PAIS_RESIDENCIA").text = pais_residencia

    if num_afiliacion_ss and doc_type_prefix not in ("D", "E"):
        etree.SubElement(trabajador, "NUM_AFILIACION_SS").text = num_afiliacion_ss.replace(" ", "")

    if domicilio:
        etree.SubElement(trabajador, "DOMICILIO_RESIDENCIA").text = domicilio.upper().strip()

    return trabajador


def _build_datos_generales_contrato(
    mapping: SEPEContractMapping,
    fecha_inicio: str,
    fecha_fin: Optional[str] = None,
    nivel_formativo: str = "40",
    codigo_ocupacion: str = "0000",
    nacionalidad_ct: str = "724",
    municipio_ct: str = "",
    ind_discapacidad: str = "",
    codigo_programa_empleo: str = "",
    ind_ere_vigente: str = "N",
    causa_sustitucion: str = "",
    horas_jornada: float = 0.0,
    horas_convenio: float = 0.0,
    tipo_jornada: str = "A",
    actividad_sin_fecha_cierta: bool = False,
) -> tuple[etree._Element, etree._Element | None, etree._Element | None, etree._Element | None]:
    """Build DATOS_GENERALES_CONTRATO + optional sections.

    Returns (datos_generales, datos_prestaciones, datos_parcial, datos_sustitucion).
    """
    datos = etree.Element("DATOS_GENERALES_CONTRATO")

    etree.SubElement(datos, "FECHA_INICIO").text = _date_to_sepe(fecha_inicio)

    if fecha_fin and not mapping.is_indefinite:
        etree.SubElement(datos, "FECHA_TERMINO").text = _date_to_sepe(fecha_fin)

    etree.SubElement(datos, "NIVEL_FORMATIVO").text = nivel_formativo

    if ind_discapacidad:
        etree.SubElement(datos, "IND_DISCAPACIDAD").text = ind_discapacidad

    etree.SubElement(datos, "CODIGO_OCUPACION").text = _pad_occupation(codigo_ocupacion)

    if codigo_programa_empleo:
        etree.SubElement(datos, "CODIGOPROGRAMAEMPLEO").text = codigo_programa_empleo

    etree.SubElement(datos, "NACIONALIDAD_CT").text = nacionalidad_ct

    if nacionalidad_ct == "724" and municipio_ct:
        etree.SubElement(datos, "MUNICIPIO_CT").text = municipio_ct

    etree.SubElement(datos, "INDICATIVO_PRTR").text = "N"

    datos_prestaciones = etree.Element("DATOS_PRESTACIONES")
    etree.SubElement(datos_prestaciones, "IND_ERE_VIGENTE").text = ind_ere_vigente

    datos_parcial = None
    if mapping.requires_partial_time_data:
        datos_parcial = etree.Element("DATOS_CONTRATO_TIEMPO_PARCIAL")
        etree.SubElement(datos_parcial, "TIPO_JORNADA").text = tipo_jornada

        if horas_jornada > 0:
            etree.SubElement(datos_parcial, "HORAS_JORNADA").text = _hours_to_sepe(horas_jornada)
        elif actividad_sin_fecha_cierta:
            etree.SubElement(datos_parcial, "ACTIVIDAD_SIN_FECHACIERTA").text = "S"

        if horas_convenio > 0:
            etree.SubElement(datos_parcial, "HORAS_CONVENIO").text = _hours_to_sepe(horas_convenio)

    datos_sustitucion = None
    if mapping.sepe_code in ("410", "510") and causa_sustitucion:
        datos_sustitucion = etree.Element("DATOS_CONTRATO_SUSTITUCION")
        etree.SubElement(datos_sustitucion, "CAUSA_SUSTITUCION").text = causa_sustitucion

    return datos, datos_prestaciones, datos_parcial, datos_sustitucion


class ContratoXMLGenerator:
    """Generate SEPE Contrat@ XML files from PGK data models."""

    def generate(
        self,
        *,
        empresa_cif: str,
        empresa_ccc: str,
        trabajador_nif: str,
        trabajador_nombre: str,
        trabajador_sexo: str,
        trabajador_fecha_nacimiento: str,
        trabajador_nacionalidad: str = "724",
        trabajador_municipio: str = "",
        trabajador_pais_residencia: str = "724",
        trabajador_naf: str = "",
        trabajador_domicilio: str = "",
        contrato_tipo_pgk: str = "indefinido",
        contrato_jornada: float = 40.0,
        contrato_fecha_inicio: str = "",
        contrato_fecha_fin: Optional[str] = None,
        contrato_nivel_formativo: str = "40",
        contrato_ocupacion: str = "0000",
        contrato_nacionalidad_ct: str = "724",
        contrato_municipio_ct: str = "",
        contrato_ind_discapacidad: str = "",
        contrato_codigo_programa_empleo: str = "",
        contrato_ind_ere_vigente: str = "N",
        contrato_causa_sustitucion: str = "",
        contrato_horas_jornada_parcial: float = 0.0,
        contrato_horas_convenio: float = 0.0,
        contrato_tipo_jornada: str = "A",
        contrato_actividad_sin_fecha_cierta: bool = False,
    ) -> tuple[bytes, SEPEContractMapping, list[str]]:
        """Generate a Contrat@ XML file.

        Returns:
            Tuple of (xml_bytes, mapping, warnings)
        """
        warnings: list[str] = []

        mapping = resolve_pgk_to_sepe(contrato_tipo_pgk, contrato_jornada)

        if not contrato_fecha_inicio:
            raise ValueError("contrato_fecha_inicio is required")
        if not empresa_cif:
            raise ValueError("empresa_cif is required")
        if not trabajador_nif:
            raise ValueError("trabajador_nif is required")

        if mapping.requires_end_date and not contrato_fecha_fin:
            warnings.append(
                f"Contract type {mapping.sepe_code} ({mapping.pgk_type}) requires fecha_fin"
            )

        if mapping.is_indefinite and contrato_fecha_fin:
            warnings.append(
                f"Indefinite contract type {mapping.sepe_code} should not have fecha_fin - ignoring"
            )

        root = etree.Element(
            "CONTRATOS",
            attrib={
                f"{{{XSI_NS}}}noNamespaceSchemaLocation": XSD_FILENAME,
            },
            nsmap={"xsi": XSI_NS},
        )

        contrato_el = etree.SubElement(root, mapping.sepe_element)

        datos_empresa = _build_datos_empresa(empresa_cif, empresa_ccc)
        contrato_el.append(datos_empresa)

        datos_trabajador = _build_datos_trabajador(
            nif=trabajador_nif,
            nombre_apellidos=trabajador_nombre,
            sexo=trabajador_sexo,
            fecha_nacimiento=trabajador_fecha_nacimiento,
            nacionalidad=trabajador_nacionalidad,
            municipio_residencia=trabajador_municipio,
            pais_residencia=trabajador_pais_residencia,
            num_afiliacion_ss=trabajador_naf,
            domicilio=trabajador_domicilio,
        )
        contrato_el.append(datos_trabajador)

        datos_generales, datos_prestaciones, datos_parcial, datos_sustitucion = (
            _build_datos_generales_contrato(
                mapping=mapping,
                fecha_inicio=contrato_fecha_inicio,
                fecha_fin=contrato_fecha_fin,
                nivel_formativo=contrato_nivel_formativo,
                codigo_ocupacion=contrato_ocupacion,
                nacionalidad_ct=contrato_nacionalidad_ct,
                municipio_ct=contrato_municipio_ct,
                ind_discapacidad=contrato_ind_discapacidad,
                codigo_programa_empleo=contrato_codigo_programa_empleo,
                ind_ere_vigente=contrato_ind_ere_vigente,
                causa_sustitucion=contrato_causa_sustitucion,
                horas_jornada=contrato_horas_jornada_parcial,
                horas_convenio=contrato_horas_convenio,
                tipo_jornada=contrato_tipo_jornada,
                actividad_sin_fecha_cierta=contrato_actividad_sin_fecha_cierta,
            )
        )
        contrato_el.append(datos_generales)

        if datos_prestaciones is not None:
            contrato_el.append(datos_prestaciones)

        if datos_parcial is not None:
            contrato_el.append(datos_parcial)

        if datos_sustitucion is not None:
            contrato_el.append(datos_sustitucion)

        xml_bytes = etree.tostring(
            root,
            xml_declaration=True,
            encoding="ISO-8859-1",
            pretty_print=True,
        )

        logger.info(
            "Generated Contrat@ XML: code=%s element=%s size=%d bytes",
            mapping.sepe_code,
            mapping.sepe_element,
            len(xml_bytes),
        )

        return xml_bytes, mapping, warnings


contrato_xml_generator = ContratoXMLGenerator()
