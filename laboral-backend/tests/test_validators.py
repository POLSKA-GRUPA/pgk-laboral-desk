"""Tests unitarios de validadores NIF/NIE/CIF/NAF/CCC."""

from __future__ import annotations

from app.services.validators import (
    validate_ccc,
    validate_cif,
    validate_dni,
    validate_naf,
    validate_nie,
    validate_nif,
)


class TestDNI:
    def test_dni_valido(self):
        assert validate_dni("12345678Z")

    def test_dni_letra_incorrecta(self):
        assert not validate_dni("12345678A")

    def test_dni_con_guion(self):
        assert validate_dni("12345678-Z")

    def test_dni_minusculas(self):
        assert validate_dni("12345678z")

    def test_dni_sin_letra(self):
        assert not validate_dni("12345678")

    def test_dni_vacio(self):
        assert not validate_dni("")


class TestNIE:
    def test_nie_x(self):
        # X0000000T — X → 0 → 00000000 % 23 = 0 → T
        assert validate_nie("X0000000T")

    def test_nie_y(self):
        # Y0000000? — Y → 1 → 10000000 % 23 = 14 → _DNI_LETTERS[14] = "Z"
        assert validate_nie("Y0000000Z")

    def test_nie_z(self):
        # Z0000000? — Z → 2 → 20000000 % 23 = 5 → _DNI_LETTERS[5] = "M"
        assert validate_nie("Z0000000M")

    def test_nie_control_incorrecto(self):
        assert not validate_nie("Y0000000A")

    def test_nie_letra_inicial_invalida(self):
        assert not validate_nie("A0000000T")


class TestCIF:
    def test_cif_empresa_b_valido(self):
        # B97748248 calculado: para dígitos 9774824, control = 8 (B → dígito)
        assert validate_cif("B97748248")

    def test_cif_digito_control_incorrecto(self):
        assert not validate_cif("B97748240")

    def test_cif_organismo_p_letra(self):
        # Prefijo P admite letra de control (no dígito).
        # Para dígitos 9774824, control=8 → tabla "JABCDEFGHI"[8] = "H".
        assert validate_cif("P9774824H")

    def test_cif_letra_invalida(self):
        assert not validate_cif("I12345678")


class TestNIF:
    def test_nif_acepta_dni_nie_cif(self):
        assert validate_nif("12345678Z")
        assert validate_nif("X0000000T")
        assert validate_nif("B97748248")

    def test_nif_rechaza_basura(self):
        assert not validate_nif("XXXXXXXX")


class TestNAF:
    def test_naf_valido(self):
        # NAF sintético válido: base 28 1234567 8 → módulo 97
        # Calculamos: 2812345678 % 97 = ?
        base = 2812345678
        control = base % 97
        naf = f"{base}{control:02d}"
        assert len(naf) == 12
        assert validate_naf(naf)

    def test_naf_con_separadores(self):
        base = 2812345678
        control = base % 97
        raw = f"28/12345678/{control:02d}"
        assert validate_naf(raw)

    def test_naf_control_incorrecto(self):
        assert not validate_naf("281234567899")

    def test_naf_longitud_incorrecta(self):
        assert not validate_naf("28123456")
        assert not validate_naf("2812345678901234")

    def test_naf_no_numerico(self):
        assert not validate_naf("28123456789A")


class TestCCC:
    def test_ccc_valido(self):
        base = 281234567
        control = base % 97
        ccc = f"{base}{control:02d}"
        assert len(ccc) == 11
        assert validate_ccc(ccc)

    def test_ccc_con_separadores(self):
        base = 281234567
        control = base % 97
        raw = f"28/1234567/{control:02d}"
        assert validate_ccc(raw)

    def test_ccc_control_incorrecto(self):
        assert not validate_ccc("28123456799")

    def test_ccc_longitud_incorrecta(self):
        assert not validate_ccc("281234567")
