"""Importador de convenios colectivos desde el BOE.

Descarga el XML oficial del BOE y extrae:
  - Metadatos (título, fechas, identificador, departamento, vigencia)
  - Texto estructurado por capítulos y artículos
  - Tablas salariales en bruto (para post-proceso con LLM o parser)

Uso:
    from boe_importer import BOEImporter
    imp = BOEImporter()
    doc = imp.fetch("BOE-A-2026-5849")
    print(doc.metadata["titulo"])
    for art in doc.articles:
        print(art["numero"], art["titulo"])

Fuente: https://boe.es/diario_boe/xml.php?id=<ID>
"""

from __future__ import annotations

import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET


_BOE_XML_URL = "https://boe.es/diario_boe/xml.php?id={boe_id}"
_BOE_PDF_BASE = "https://www.boe.es"
_REQUEST_TIMEOUT = 30


@dataclass
class BOEDocument:
    """Documento BOE parseado."""

    boe_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chapters: list[dict[str, Any]] = field(default_factory=list)
    articles: list[dict[str, Any]] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    raw_text: str = ""
    xml_raw: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "boe_id": self.boe_id,
            "metadata": self.metadata,
            "chapters": self.chapters,
            "articles": self.articles,
            "tables": self.tables,
            "raw_text_length": len(self.raw_text),
        }


class BOEImporter:
    """Descarga y parsea documentos del BOE."""

    def __init__(self, timeout: int = _REQUEST_TIMEOUT) -> None:
        self.timeout = timeout

    def fetch(self, boe_id: str) -> BOEDocument:
        """Descarga y parsea un documento del BOE por su identificador.

        Args:
            boe_id: Identificador BOE (ej. 'BOE-A-2026-5849').

        Returns:
            BOEDocument con metadatos y texto estructurado.

        Raises:
            ValueError: Si el ID no tiene formato válido.
            ConnectionError: Si no se puede descargar el documento.
        """
        boe_id = boe_id.strip()
        if not re.match(r"^BOE-[A-Z]-\d{4}-\d+$", boe_id):
            raise ValueError(
                f"Formato de ID BOE no válido: {boe_id}. "
                "Esperado: BOE-X-YYYY-NNNNN (ej. BOE-A-2026-5849)"
            )

        xml_str = self._download(boe_id)
        root = ET.fromstring(xml_str)

        doc = BOEDocument(boe_id=boe_id, xml_raw=xml_str)
        doc.metadata = self._parse_metadata(root)
        doc.chapters, doc.articles = self._parse_text(root)
        doc.tables = self._parse_tables(root)
        doc.raw_text = self._extract_plain_text(root)
        return doc

    def fetch_metadata_only(self, boe_id: str) -> dict[str, Any]:
        """Descarga solo los metadatos sin parsear el texto completo."""
        boe_id = boe_id.strip()
        if not re.match(r"^BOE-[A-Z]-\d{4}-\d+$", boe_id):
            raise ValueError(f"Formato de ID BOE no válido: {boe_id}")

        xml_str = self._download(boe_id)
        root = ET.fromstring(xml_str)
        return self._parse_metadata(root)

    # ------------------------------------------------------------------
    # Descarga
    # ------------------------------------------------------------------

    def _download(self, boe_id: str) -> str:
        url = _BOE_XML_URL.format(boe_id=boe_id)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "PGK-Laboral-Desk/1.0 (+https://pgk.es)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise ConnectionError(
                f"Error HTTP {exc.code} al descargar {url}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"No se pudo conectar al BOE: {exc.reason}"
            ) from exc

    # ------------------------------------------------------------------
    # Parsing de metadatos
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_metadata(root: ET.Element) -> dict[str, Any]:
        meta_el = root.find("metadatos")
        if meta_el is None:
            return {}

        def _text(tag: str) -> str:
            el = meta_el.find(tag)
            return (el.text or "").strip() if el is not None else ""

        def _attr(tag: str, attr: str) -> str:
            el = meta_el.find(tag)
            return el.get(attr, "") if el is not None else ""

        metadata: dict[str, Any] = {
            "identificador": _text("identificador"),
            "titulo": _text("titulo"),
            "departamento": _text("departamento"),
            "rango": _text("rango"),
            "fecha_disposicion": _text("fecha_disposicion"),
            "fecha_publicacion": _text("fecha_publicacion"),
            "diario_numero": _text("diario_numero"),
            "pagina_inicial": _text("pagina_inicial"),
            "pagina_final": _text("pagina_final"),
            "url_pdf": _text("url_pdf"),
            "url_eli": _text("url_eli"),
            "origen_legislativo": _text("origen_legislativo"),
            "estatus_derogacion": _text("estatus_derogacion"),
        }

        # URL completa del PDF
        if metadata["url_pdf"]:
            metadata["url_pdf_completa"] = _BOE_PDF_BASE + metadata["url_pdf"]

        # Materias
        analisis = root.find("analisis")
        if analisis is not None:
            materias_el = analisis.find("materias")
            if materias_el is not None:
                metadata["materias"] = [
                    m.text.strip()
                    for m in materias_el.findall("materia")
                    if m.text
                ]
            # Notas (vigencia, etc.)
            notas_el = analisis.find("notas")
            if notas_el is not None:
                metadata["notas"] = [
                    n.text.strip()
                    for n in notas_el.findall("nota")
                    if n.text
                ]

        return metadata

    # ------------------------------------------------------------------
    # Parsing de texto estructurado
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_text(
        root: ET.Element,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extrae capítulos y artículos del bloque <texto>."""
        texto_el = root.find("texto")
        if texto_el is None:
            return [], []

        chapters: list[dict[str, Any]] = []
        articles: list[dict[str, Any]] = []
        current_chapter: str = ""
        current_article: dict[str, Any] | None = None

        for p in texto_el:
            css_class = p.get("class", "")
            text = "".join(p.itertext()).strip()

            if not text:
                continue

            # Capítulo
            if css_class in ("capitulo", "capitulo_num"):
                current_chapter = text
                chapters.append({"titulo": text, "subtitulo": ""})

            elif css_class == "capitulo_tit":
                if chapters:
                    chapters[-1]["subtitulo"] = text
                current_chapter = f"{chapters[-1]['titulo']} — {text}" if chapters else text

            # Artículo
            elif css_class == "articulo":
                if current_article is not None:
                    articles.append(current_article)
                # Extraer número y título
                match = re.match(r"(Art[ií]culo\s+\d+[a-z]?\.?)\s*(.*)", text)
                if match:
                    current_article = {
                        "numero": match.group(1).rstrip("."),
                        "titulo": match.group(2).rstrip("."),
                        "capitulo": current_chapter,
                        "parrafos": [],
                    }
                else:
                    current_article = {
                        "numero": text.rstrip("."),
                        "titulo": "",
                        "capitulo": current_chapter,
                        "parrafos": [],
                    }

            # Anexo
            elif css_class == "anexo":
                if current_article is not None:
                    articles.append(current_article)
                current_article = {
                    "numero": "Anexo",
                    "titulo": text,
                    "capitulo": "Anexos",
                    "parrafos": [],
                }

            # Párrafo (contenido)
            elif css_class in ("parrafo", "parrafo_2") and current_article is not None:
                current_article["parrafos"].append(text)

        # Último artículo
        if current_article is not None:
            articles.append(current_article)

        return chapters, articles

    # ------------------------------------------------------------------
    # Parsing de tablas
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_tables(root: ET.Element) -> list[list[list[str]]]:
        """Extrae tablas HTML embebidas en el XML del BOE."""
        tables: list[list[list[str]]] = []
        texto_el = root.find("texto")
        if texto_el is None:
            return tables

        for table in texto_el.iter("table"):
            rows: list[list[str]] = []
            for tr in table.iter("tr"):
                cells: list[str] = []
                for cell in tr:
                    if cell.tag in ("td", "th"):
                        cells.append("".join(cell.itertext()).strip())
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)

        return tables

    # ------------------------------------------------------------------
    # Texto plano
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_plain_text(root: ET.Element) -> str:
        """Extrae todo el texto del bloque <texto> como string plano."""
        texto_el = root.find("texto")
        if texto_el is None:
            return ""
        parts: list[str] = []
        for p in texto_el:
            text = "".join(p.itertext()).strip()
            if text:
                parts.append(text)
        return "\n\n".join(parts)
