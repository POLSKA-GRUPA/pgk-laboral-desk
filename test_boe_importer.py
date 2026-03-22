"""Tests para el importador BOE."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from boe_importer import BOEImporter, BOEDocument


# ======================================================================
# XML de prueba (fragmento mínimo)
# ======================================================================

_SAMPLE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<documento fecha_actualizacion="20260320085601">
  <metadatos>
    <identificador>BOE-A-2026-9999</identificador>
    <titulo>Resolución de prueba para test unitario.</titulo>
    <departamento>Ministerio de Trabajo</departamento>
    <rango>Resolución</rango>
    <fecha_disposicion>20260301</fecha_disposicion>
    <fecha_publicacion>20260310</fecha_publicacion>
    <diario_numero>60</diario_numero>
    <pagina_inicial>10000</pagina_inicial>
    <pagina_final>10020</pagina_final>
    <url_pdf>/boe/dias/2026/03/10/pdfs/BOE-A-2026-9999.pdf</url_pdf>
    <url_eli>https://www.boe.es/eli/es/res/2026/03/01/(99)</url_eli>
    <origen_legislativo>Estatal</origen_legislativo>
    <estatus_derogacion>N</estatus_derogacion>
  </metadatos>
  <analisis>
    <materias>
      <materia codigo="1684" orden="1">Convenios colectivos</materia>
      <materia codigo="9999" orden="2">Sector test</materia>
    </materias>
    <notas>
      <nota codigo="38" orden="1">Efectos desde el 1 de enero de 2025.</nota>
    </notas>
  </analisis>
  <texto>
    <p class="capitulo_num">CAPÍTULO I</p>
    <p class="capitulo_tit">Disposiciones generales</p>
    <p class="articulo">Artículo 1. Partes signatarias.</p>
    <p class="parrafo">El presente convenio es firmado por las partes.</p>
    <p class="parrafo">Ambas partes se reconocen legitimación.</p>
    <p class="articulo">Artículo 2. Ámbito territorial.</p>
    <p class="parrafo">Este convenio será de aplicación en todo el territorio nacional.</p>
    <p class="capitulo_num">CAPÍTULO II</p>
    <p class="capitulo_tit">Retribución</p>
    <p class="articulo">Artículo 30. Salario base.</p>
    <p class="parrafo">El salario base se fija según las tablas del Anexo I.</p>
    <p class="anexo">ANEXO I — TABLAS SALARIALES 2025</p>
    <p class="parrafo">Las tablas se detallan a continuación.</p>
  </texto>
</documento>"""


# ======================================================================
# Tests offline (sin red)
# ======================================================================

def _mock_fetch(boe_id: str) -> BOEDocument:
    """Crea un BOEDocument parseando el XML de prueba sin red."""
    imp = BOEImporter()
    with patch.object(imp, "_download", return_value=_SAMPLE_XML):
        return imp.fetch(boe_id)


def test_parse_metadata():
    doc = _mock_fetch("BOE-A-2026-9999")
    m = doc.metadata
    assert m["identificador"] == "BOE-A-2026-9999"
    assert "prueba" in m["titulo"].lower()
    assert m["departamento"] == "Ministerio de Trabajo"
    assert m["fecha_publicacion"] == "20260310"
    assert m["url_pdf_completa"].startswith("https://www.boe.es/")
    assert m["estatus_derogacion"] == "N"


def test_parse_materias():
    doc = _mock_fetch("BOE-A-2026-9999")
    assert "materias" in doc.metadata
    assert len(doc.metadata["materias"]) == 2
    assert "Convenios colectivos" in doc.metadata["materias"]


def test_parse_notas():
    doc = _mock_fetch("BOE-A-2026-9999")
    assert "notas" in doc.metadata
    assert any("2025" in n for n in doc.metadata["notas"])


def test_parse_chapters():
    doc = _mock_fetch("BOE-A-2026-9999")
    assert len(doc.chapters) >= 2
    assert doc.chapters[0]["titulo"] == "CAPÍTULO I"
    assert doc.chapters[0]["subtitulo"] == "Disposiciones generales"
    assert doc.chapters[1]["subtitulo"] == "Retribución"


def test_parse_articles():
    doc = _mock_fetch("BOE-A-2026-9999")
    assert len(doc.articles) >= 3  # Art 1, 2, 30 + Anexo
    art1 = doc.articles[0]
    assert art1["numero"] == "Artículo 1"
    assert "Partes" in art1["titulo"]
    assert len(art1["parrafos"]) == 2


def test_parse_annexes():
    doc = _mock_fetch("BOE-A-2026-9999")
    anexos = [a for a in doc.articles if a["numero"] == "Anexo"]
    assert len(anexos) >= 1
    assert "TABLAS SALARIALES" in anexos[0]["titulo"]


def test_articles_have_chapter():
    doc = _mock_fetch("BOE-A-2026-9999")
    art30 = next(a for a in doc.articles if "30" in a["numero"])
    assert "Retribución" in art30["capitulo"]


def test_raw_text():
    doc = _mock_fetch("BOE-A-2026-9999")
    assert len(doc.raw_text) > 100
    assert "Artículo 1" in doc.raw_text
    assert "territorio nacional" in doc.raw_text


def test_to_dict():
    doc = _mock_fetch("BOE-A-2026-9999")
    d = doc.to_dict()
    assert d["boe_id"] == "BOE-A-2026-9999"
    assert "metadata" in d
    assert "articles" in d
    assert d["raw_text_length"] > 0


# ======================================================================
# Validación de entradas
# ======================================================================

def test_invalid_boe_id_raises():
    imp = BOEImporter()
    with pytest.raises(ValueError, match="no válido"):
        imp.fetch("INVALID-ID")


def test_invalid_boe_id_format():
    imp = BOEImporter()
    with pytest.raises(ValueError):
        imp.fetch("BOE-2026-5849")  # Falta la letra


def test_whitespace_stripped():
    doc = _mock_fetch("BOE-A-2026-9999")
    assert doc.boe_id == "BOE-A-2026-9999"


# ======================================================================
# Test de integración real (requiere red)
# ======================================================================

@pytest.mark.integration
def test_fetch_real_boe_acuaticas():
    """Descarga el convenio de acuáticas real desde el BOE."""
    imp = BOEImporter()
    doc = imp.fetch("BOE-A-2026-5849")

    # Metadatos
    assert doc.metadata["identificador"] == "BOE-A-2026-5849"
    assert "acuáticas" in doc.metadata["titulo"].lower()
    assert doc.metadata["fecha_publicacion"] == "20260312"

    # Estructura
    assert len(doc.chapters) > 5
    assert len(doc.articles) > 20

    # Artículo conocido
    art1 = next(a for a in doc.articles if "1" in a["numero"] and "Partes" in a.get("titulo", ""))
    assert len(art1["parrafos"]) > 0

    # Texto plano
    assert len(doc.raw_text) > 5000


@pytest.mark.integration
def test_fetch_metadata_only():
    imp = BOEImporter()
    meta = imp.fetch_metadata_only("BOE-A-2026-5849")
    assert meta["identificador"] == "BOE-A-2026-5849"
    assert "materias" in meta
