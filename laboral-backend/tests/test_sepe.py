"""Tests for SEPE Contrat@ XML generation and validation."""

import pytest
from app.services.sepe_mapper import resolve_pgk_to_sepe, list_available_types
from app.services.sepe_xml_generator import contrato_xml_generator
from app.services.sepe_validator import validate_xml
from app.services.sepe_code_tables import get_table, list_tables, CONTRACT_TYPES


class TestSEPEMapper:
    def test_indefinido_tc_maps_to_100(self):
        m = resolve_pgk_to_sepe("indefinido", 40.0)
        assert m.sepe_code == "100"
        assert m.is_full_time is True
        assert m.is_indefinite is True

    def test_indefinido_parcial_maps_to_200(self):
        m = resolve_pgk_to_sepe("indefinido", 30.0)
        assert m.sepe_code == "200"
        assert m.is_full_time is False

    def test_temporal_maps_to_402(self):
        m = resolve_pgk_to_sepe("temporal", 40.0)
        assert m.sepe_code == "402"
        assert m.requires_end_date is True

    def test_temporal_parcial_maps_to_502(self):
        m = resolve_pgk_to_sepe("temporal", 25.0)
        assert m.sepe_code == "502"

    def test_fijo_discontinuo_maps_to_300(self):
        m = resolve_pgk_to_sepe("fijo-discontinuo", 40.0)
        assert m.sepe_code == "300"
        assert m.requires_partial_time_data is True

    def test_circunstancias_produccion(self):
        m = resolve_pgk_to_sepe("circunstancias-produccion", 40.0)
        assert m.sepe_code == "402"
        assert m.requires_end_date is True

    def test_sustitucion(self):
        m = resolve_pgk_to_sepe("sustitucion", 40.0)
        assert m.sepe_code == "410"

    def test_list_available_types_returns_all(self):
        types = list_available_types()
        assert len(types) >= 40
        codes = {t["sepe_code"] for t in types}
        assert "100" in codes
        assert "402" in codes
        assert "300" in codes

    def test_unknown_type_defaults_to_indefinido(self):
        m = resolve_pgk_to_sepe("unknown-type", 40.0)
        assert m.sepe_code == "100"

    def test_relevo_maps_to_441(self):
        m = resolve_pgk_to_sepe("relevo", 40.0)
        assert m.sepe_code == "441"
        assert m.requires_end_date is True

    def test_relevo_parcial_maps_to_541(self):
        m = resolve_pgk_to_sepe("relevo-parcial", 25.0)
        assert m.sepe_code == "541"

    def test_deportista_maps_to_413(self):
        m = resolve_pgk_to_sepe("deportista", 40.0)
        assert m.sepe_code == "413"

    def test_deportista_parcial_maps_to_513(self):
        m = resolve_pgk_to_sepe("deportista-parcial", 25.0)
        assert m.sepe_code == "513"

    def test_formacion_alternancia_maps_to_421(self):
        m = resolve_pgk_to_sepe("formacion-alternancia", 40.0)
        assert m.sepe_code == "421"

    def test_formacion_alternancia_parcial_maps_to_521(self):
        m = resolve_pgk_to_sepe("formacion-alternancia-parcial", 25.0)
        assert m.sepe_code == "521"


class TestSEPEXMLGenerator:
    def _make_indefinido_xml(self):
        return contrato_xml_generator.generate(
            empresa_cif="A12345678",
            empresa_ccc="011301234567890",
            trabajador_nif="12345678Z",
            trabajador_nombre="Garcia Lopez Juan",
            trabajador_sexo="M",
            trabajador_fecha_nacimiento="1990-01-15",
            contrato_tipo_pgk="indefinido",
            contrato_jornada=40.0,
            contrato_fecha_inicio="2024-03-01",
            contrato_nivel_formativo="40",
            contrato_ocupacion="5121",
            contrato_municipio_ct="28079",
        )

    def test_indefinido_generates_valid_xml(self):
        xml_bytes, mapping, warnings = self._make_indefinido_xml()
        assert mapping.sepe_code == "100"
        assert b"CONTRATO_100" in xml_bytes
        assert b"DATOS_EMPRESA" in xml_bytes
        assert b"DATOS_TRABAJADOR" in xml_bytes
        assert b"DATOS_GENERALES_CONTRATO" in xml_bytes
        assert b"<SEXO>1</SEXO>" in xml_bytes
        assert len(warnings) == 0

    def test_indefinido_has_no_fecha_fin(self):
        xml_bytes, _, _ = self._make_indefinido_xml()
        assert b"FECHA_TERMINO" not in xml_bytes

    def test_temporal_has_fecha_fin(self):
        xml_bytes, mapping, _ = contrato_xml_generator.generate(
            empresa_cif="B98765432",
            empresa_ccc="011301234567890",
            trabajador_nif="87654321X",
            trabajador_nombre="Martinez Maria",
            trabajador_sexo="2",
            trabajador_fecha_nacimiento="1995-03-22",
            contrato_tipo_pgk="circunstancias-produccion",
            contrato_jornada=40.0,
            contrato_fecha_inicio="2024-03-01",
            contrato_fecha_fin="2024-06-30",
            contrato_nivel_formativo="40",
            contrato_ocupacion="5121",
            contrato_municipio_ct="28079",
        )
        assert mapping.sepe_code == "402"
        assert b"FECHA_TERMINO" in xml_bytes
        assert b"20240630" in xml_bytes

    def test_parcial_includes_tiempo_parcial(self):
        xml_bytes, mapping, _ = contrato_xml_generator.generate(
            empresa_cif="A12345678",
            empresa_ccc="011301234567890",
            trabajador_nif="12345678Z",
            trabajador_nombre="Lopez Pedro",
            trabajador_sexo="M",
            trabajador_fecha_nacimiento="1988-07-10",
            contrato_tipo_pgk="indefinido",
            contrato_jornada=30.0,
            contrato_fecha_inicio="2024-06-01",
            contrato_nivel_formativo="22",
            contrato_ocupacion="7111",
            contrato_municipio_ct="04002",
            contrato_horas_jornada_parcial=1200.0,
        )
        assert mapping.sepe_code == "200"
        assert b"DATOS_CONTRATO_TIEMPO_PARCIAL" in xml_bytes
        assert b"HORAS_JORNADA" in xml_bytes

    def test_xml_encoding_is_iso_8859_1(self):
        xml_bytes, _, _ = self._make_indefinido_xml()
        assert b"encoding='ISO-8859-1'" in xml_bytes

    def test_occupation_code_padded_to_8(self):
        xml_bytes, _, _ = self._make_indefinido_xml()
        assert b"5121    " in xml_bytes

    def test_fecha_inicio_format_aaaammdd(self):
        xml_bytes, _, _ = self._make_indefinido_xml()
        assert b"<FECHA_INICIO>20240301</FECHA_INICIO>" in xml_bytes

    def test_missing_fecha_inicio_raises(self):
        with pytest.raises(ValueError, match="fecha_inicio"):
            contrato_xml_generator.generate(
                empresa_cif="A12345678",
                empresa_ccc="011301234567890",
                trabajador_nif="12345678Z",
                trabajador_nombre="Test",
                trabajador_sexo="M",
                trabajador_fecha_nacimiento="1990-01-01",
                contrato_tipo_pgk="indefinido",
                contrato_jornada=40.0,
                contrato_fecha_inicio="",
            )

    def test_missing_empresa_cif_raises(self):
        with pytest.raises(ValueError, match="empresa_cif"):
            contrato_xml_generator.generate(
                empresa_cif="",
                empresa_ccc="011301234567890",
                trabajador_nif="12345678Z",
                trabajador_nombre="Test",
                trabajador_sexo="M",
                trabajador_fecha_nacimiento="1990-01-01",
                contrato_tipo_pgk="indefinido",
                contrato_jornada=40.0,
                contrato_fecha_inicio="2024-01-01",
            )

    def test_temporal_without_end_date_warns(self):
        _, _, warnings = contrato_xml_generator.generate(
            empresa_cif="A12345678",
            empresa_ccc="011301234567890",
            trabajador_nif="12345678Z",
            trabajador_nombre="Test",
            trabajador_sexo="1",
            trabajador_fecha_nacimiento="1990-01-01",
            contrato_tipo_pgk="circunstancias-produccion",
            contrato_jornada=40.0,
            contrato_fecha_inicio="2024-01-01",
        )
        assert any("fecha_fin" in w for w in warnings)

    def test_gender_code_6_no_consta(self):
        xml_bytes, _, _ = contrato_xml_generator.generate(
            empresa_cif="A12345678",
            empresa_ccc="011301234567890",
            trabajador_nif="12345678Z",
            trabajador_nombre="Test",
            trabajador_sexo="6",
            trabajador_fecha_nacimiento="1990-01-01",
            contrato_tipo_pgk="indefinido",
            contrato_jornada=40.0,
            contrato_fecha_inicio="2024-01-01",
        )
        assert b"<SEXO>6</SEXO>" in xml_bytes

    def test_legacy_gender_M_maps_to_1(self):
        xml_bytes, _, _ = contrato_xml_generator.generate(
            empresa_cif="A12345678",
            empresa_ccc="011301234567890",
            trabajador_nif="12345678Z",
            trabajador_nombre="Test",
            trabajador_sexo="M",
            trabajador_fecha_nacimiento="1990-01-01",
            contrato_tipo_pgk="indefinido",
            contrato_jornada=40.0,
            contrato_fecha_inicio="2024-01-01",
        )
        assert b"<SEXO>1</SEXO>" in xml_bytes


class TestSEPEValidator:
    def test_valid_xml_passes(self):
        xml_bytes, _, _ = contrato_xml_generator.generate(
            empresa_cif="A12345678",
            empresa_ccc="011301234567890",
            trabajador_nif="12345678Z",
            trabajador_nombre="Test User",
            trabajador_sexo="M",
            trabajador_fecha_nacimiento="1990-01-01",
            contrato_tipo_pgk="indefinido",
            contrato_jornada=40.0,
            contrato_fecha_inicio="2024-01-01",
        )
        result = validate_xml(xml_bytes)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_invalid_xml_syntax_fails(self):
        result = validate_xml(b"<not-valid-xml>>>")
        assert result.valid is False
        assert any("syntax" in e.lower() for e in result.errors)

    def test_wrong_root_element_fails(self):
        result = validate_xml(b"<WRONG><CONTRATO_100/></WRONG>")
        assert result.valid is False

    def test_missing_datos_empresa_fails(self):
        from lxml import etree

        root = etree.Element("CONTRATOS")
        contrato = etree.SubElement(root, "CONTRATO_100")
        xml_bytes = etree.tostring(root)
        result = validate_xml(xml_bytes)
        assert result.valid is False
        assert any("DATOS_EMPRESA" in e for e in result.errors)


class TestSEPECodeTables:
    def test_list_tables_returns_all(self):
        tables = list_tables()
        assert "TNWTPCOM" in tables
        assert "TCHRGCOT" in tables
        assert "STDIDETC" in tables
        assert len(tables) >= 25

    def test_get_table_contract_types(self):
        ct = get_table("TNWTPCOM")
        assert "100" in ct
        assert "402" in ct

    def test_get_table_unknown_raises(self):
        with pytest.raises(KeyError):
            get_table("NONEXISTENT")

    def test_contract_types_has_description(self):
        assert "Indefinido" in CONTRACT_TYPES["100"]

    def test_contract_types_official_45_codes(self):
        assert len(CONTRACT_TYPES) == 45
        assert "130" in CONTRACT_TYPES
        assert "230" in CONTRACT_TYPES
        assert "413" in CONTRACT_TYPES
        assert "513" in CONTRACT_TYPES
        assert "541" in CONTRACT_TYPES
        assert "110" not in CONTRACT_TYPES
        assert "120" not in CONTRACT_TYPES
        assert "440" not in CONTRACT_TYPES

    def test_gender_codes_official(self):
        gender = get_table("TCMCSEXO")
        assert "1" in gender
        assert "2" in gender
        assert "6" in gender
        assert "M" not in gender
        assert "F" not in gender

    def test_province_codes(self):
        provinces = get_table("TCGPROVI")
        assert len(provinces) == 52
        assert provinces["28"] == "Madrid"
        assert provinces["08"] == "Barcelona"
        assert provinces["01"] == "Araba/Alava"
        assert provinces["52"] == "Melilla"

    def test_education_levels(self):
        edu = get_table("TBONVFOR")
        assert "40" in edu

    def test_document_types(self):
        docs = get_table("STDIDETC")
        assert "D" in docs
        assert "E" in docs
