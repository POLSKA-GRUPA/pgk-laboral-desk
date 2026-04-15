"""SEPE Contrat@ XML validator against the official XSD schema.

Validates generated XML to ensure it will be accepted by SEPE.
Falls back to structural validation if XSD file is not available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

logger = logging.getLogger(__name__)

XSD_FILENAME = "EsquemaContratos50.xsd"
_XSD_SEARCH_PATHS = [
    Path(__file__).parent.parent.parent.parent / "data" / XSD_FILENAME,
    Path(__file__).parent.parent.parent / "data" / XSD_FILENAME,
    Path("/tmp/pgk-laboral-desk/data") / XSD_FILENAME,
]


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


def _find_xsd() -> Path | None:
    for p in _XSD_SEARCH_PATHS:
        if p.exists():
            return p
    return None


def _download_xsd() -> bytes | None:
    """Attempt to download the XSD from SEPE servers."""
    try:
        from urllib.request import urlopen

        url = f"https://www.sepe.es/DocumComunicacto/xml/14/{XSD_FILENAME}"
        with urlopen(url, timeout=10) as resp:
            return resp.read()
    except Exception:
        logger.warning("Could not download SEPE XSD schema")
        return None


def validate_xml(xml_bytes: bytes) -> ValidationResult:
    """Validate Contrat@ XML against the official XSD schema."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        xml_doc = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        return ValidationResult(False, [f"XML syntax error: {e}"], warnings)

    root_tag = xml_doc.tag
    if root_tag != "CONTRATOS":
        errors.append(f"Root element must be 'CONTRATOS', got '{root_tag}'")

    contrato_elements = list(xml_doc)
    if not contrato_elements:
        errors.append("No contract elements found inside CONTRATOS")

    for contrato_el in contrato_elements:
        tag = contrato_el.tag
        if not tag.startswith("CONTRATO_"):
            errors.append(f"Unexpected element '{tag}', expected CONTRATO_XXX")

        datos_empresa = contrato_el.find("DATOS_EMPRESA")
        if datos_empresa is None:
            errors.append(f"{tag}: Missing DATOS_EMPRESA")
        else:
            cif = datos_empresa.findtext("CIF_NIF_EMPRESA", "")
            ccc = datos_empresa.findtext("CODIGO_CUENTA_COTIZACION", "")
            if not cif:
                errors.append(f"{tag}: Missing CIF_NIF_EMPRESA")
            if not ccc:
                errors.append(f"{tag}: Missing CODIGO_CUENTA_COTIZACION")
            elif len(ccc) != 15 or not ccc.isdigit():
                errors.append(f"{tag}: CODIGO_CUENTA_COTIZACION must be 15 digits, got '{ccc}'")

        datos_trabajador = contrato_el.find("DATOS_TRABAJADOR")
        if datos_trabajador is None:
            errors.append(f"{tag}: Missing DATOS_TRABAJADOR")
        else:
            nif = datos_trabajador.findtext("IDENTIFICADORPFISICA", "")
            nombre = datos_trabajador.findtext("NOMBRE_APELLIDOS", "")
            sexo = datos_trabajador.findtext("SEXO", "")
            fecha_nac = datos_trabajador.findtext("FECHA_NACIMIENTO", "")
            if not nif:
                errors.append(f"{tag}: Missing IDENTIFICADORPFISICA")
            if not nombre:
                errors.append(f"{tag}: Missing NOMBRE_APELLIDOS")
            if sexo not in ("1", "2", "6"):
                warnings.append(f"{tag}: SEXO should be 1, 2 or 6, got '{sexo}'")
            if fecha_nac and (len(fecha_nac) != 8 or not fecha_nac.isdigit()):
                errors.append(f"{tag}: FECHA_NACIMIENTO must be AAAAMMDD (8 digits)")

        datos_generales = contrato_el.find("DATOS_GENERALES_CONTRATO")
        if datos_generales is None:
            errors.append(f"{tag}: Missing DATOS_GENERALES_CONTRATO")
        else:
            fecha_inicio = datos_generales.findtext("FECHA_INICIO", "")
            if not fecha_inicio:
                errors.append(f"{tag}: Missing FECHA_INICIO")
            elif len(fecha_inicio) != 8 or not fecha_inicio.isdigit():
                errors.append(f"{tag}: FECHA_INICIO must be AAAAMMDD")

            nivel = datos_generales.findtext("NIVEL_FORMATIVO", "")
            if not nivel:
                warnings.append(f"{tag}: NIVEL_FORMATIVO recommended")

            ocupacion = datos_generales.findtext("CODIGO_OCUPACION", "")
            if not ocupacion or ocupacion.strip() == "":
                warnings.append(f"{tag}: CODIGO_OCUPACION recommended")

    xsd_path = _find_xsd()
    if xsd_path:
        try:
            xsd_doc = etree.parse(str(xsd_path))
            schema = etree.XMLSchema(xsd_doc)
            schema.assertValid(xml_doc)
            logger.info("XSD validation passed")
        except etree.DocumentInvalid as e:
            for error in schema.error_log:
                errors.append(f"XSD line {error.line}: {error.message}")
        except Exception as e:
            warnings.append(f"XSD validation skipped: {e}")
            logger.warning("XSD validation error: %s", e)
    else:
        warnings.append("XSD file not found - structural validation only")
        logger.info("No XSD file found, performed structural validation only")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def download_and_save_xsd(target_dir: Path | None = None) -> bool:
    """Download the XSD schema and save it locally."""
    xsd_bytes = _download_xsd()
    if not xsd_bytes:
        return False

    save_dir = target_dir or Path("/tmp/pgk-laboral-desk/data")
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / XSD_FILENAME
    save_path.write_bytes(xsd_bytes)
    logger.info("XSD saved to %s", save_path)
    return True
