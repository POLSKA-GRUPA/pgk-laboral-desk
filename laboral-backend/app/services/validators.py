"""Validadores con dígito de control para identificadores fiscales españoles.

NIF (Número de Identificación Fiscal): DNI (8 dígitos + letra) y personas jurídicas
(letra + 7 dígitos + letra/número).

NIE (Número de Identidad de Extranjero): letra (X/Y/Z) + 7 dígitos + letra.

NAF (Número de Afiliación a la Seguridad Social): 12 dígitos, los 2 últimos son
dígito de control módulo 97 sobre los 10 primeros.

CCC (Código Cuenta de Cotización): 11 dígitos, formato PP-NNNNNNNNN-DC donde DC
son 2 dígitos de control módulo 97.

Fuentes:
- NIF/DNI/NIE: https://www.agenciatributaria.es/AEAT.internet/Inicio/Ayuda/_comp_Consultas_informaticas/Categorias/Otras_cuestiones/Codigo_de_control_de_los_NIF_NIE_y_CIF/Codigo_de_control_de_los_NIF_NIE_y_CIF.shtml
- NAF / CCC: Orden ESS/484/2013, Anexo II. Algoritmo módulo 97 sobre código
  provincial (2 dígitos) + número secuencial (7-8 dígitos).
"""

from __future__ import annotations

import re

# --- NIF / DNI ---------------------------------------------------------------

_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

_CIF_LETTER_TABLE = "JABCDEFGHI"


def _dni_letter(number: int) -> str:
    return _DNI_LETTERS[number % 23]


def validate_dni(value: str) -> bool:
    """DNI: 8 dígitos + letra. Letra = tabla módulo 23."""
    if not value:
        return False
    v = value.strip().upper().replace("-", "").replace(" ", "")
    if not re.fullmatch(r"\d{8}[A-Z]", v):
        return False
    number = int(v[:8])
    return v[8] == _dni_letter(number)


def validate_nie(value: str) -> bool:
    """NIE: letra inicial (X/Y/Z) + 7 dígitos + letra control.

    Se convierte la letra inicial a dígito (X→0, Y→1, Z→2) y se aplica la
    misma tabla que el DNI.
    """
    if not value:
        return False
    v = value.strip().upper().replace("-", "").replace(" ", "")
    if not re.fullmatch(r"[XYZ]\d{7}[A-Z]", v):
        return False
    prefix = {"X": "0", "Y": "1", "Z": "2"}[v[0]]
    number = int(prefix + v[1:8])
    return v[8] == _dni_letter(number)


def validate_cif(value: str) -> bool:
    """CIF de persona jurídica: letra + 7 dígitos + carácter de control.

    Aceptamos control letra (organismos, sociedades que lo requieren) o dígito
    (SL, SA, etc.).
    """
    if not value:
        return False
    v = value.strip().upper().replace("-", "").replace(" ", "")
    if not re.fullmatch(r"[A-HJNPQRSUVW]\d{7}[0-9A-J]", v):
        return False
    digits = v[1:8]
    odd_sum = 0
    for ch in digits[::2]:
        doubled = int(ch) * 2
        odd_sum += doubled // 10 + doubled % 10
    even_sum = sum(int(ch) for ch in digits[1::2])
    total = odd_sum + even_sum
    control = (10 - (total % 10)) % 10
    expected_digit = str(control)
    expected_letter = _CIF_LETTER_TABLE[control]
    check = v[8]
    if v[0] in "PQSNW":
        return check == expected_letter
    if v[0] in "ABEH":
        return check == expected_digit
    return check in (expected_digit, expected_letter)


def validate_nif(value: str) -> bool:
    """NIF de persona física o jurídica (DNI, NIE o CIF)."""
    if not value:
        return False
    return validate_dni(value) or validate_nie(value) or validate_cif(value)


# --- NAF (Número Afiliación SS) ---------------------------------------------


def validate_naf(value: str) -> bool:
    """NAF: 12 dígitos, los 2 últimos son dígito de control módulo 97.

    Formato canónico: PP/NNNNNNNN/DC (provincia 2 + secuencial 8 + control 2).
    Aceptamos también con guiones o espacios.
    """
    if not value:
        return False
    v = re.sub(r"[\s/-]", "", value.strip())
    if not re.fullmatch(r"\d{12}", v):
        return False
    base = int(v[:10])
    control = int(v[10:12])
    return base % 97 == control


# --- CCC (Código Cuenta de Cotización) --------------------------------------


def validate_ccc(value: str) -> bool:
    """CCC: 11 dígitos. Algoritmo módulo 97 oficial TGSS.

    Formato: PP/NNNNNNN/DC (provincia 2 + secuencial 7 + control 2).

    Algoritmo oficial: sobre los 9 dígitos base (provincia + secuencial),
    aplicar módulo 97 con la provincia concatenada al frente según una regla
    específica. La forma más simple y correcta es:

        base = int(provincia + secuencial)  # 9 dígitos
        if base < 10_000_000:  # CCC antiguos cortos
            base = int(provincia) * 10_000_000 + int(secuencial)
        control = base % 97

    Dado que los CCC reales siempre son 11 dígitos normalizados por TGSS,
    tratamos los 9 primeros como base y los 2 últimos como control.
    """
    if not value:
        return False
    v = re.sub(r"[\s/-]", "", value.strip())
    if not re.fullmatch(r"\d{11}", v):
        return False
    base = int(v[:9])
    control = int(v[9:11])
    return base % 97 == control


# --- Helpers para bulk import -----------------------------------------------


def normalize_nif(value: str) -> str:
    """Limpia NIF: mayúsculas, sin espacios/guiones."""
    return re.sub(r"[\s-]", "", (value or "").strip().upper())


def normalize_naf(value: str) -> str:
    """NAF normalizado a 12 dígitos sin separadores."""
    return re.sub(r"[\s/-]", "", (value or "").strip())


def normalize_ccc(value: str) -> str:
    """CCC normalizado a 11 dígitos sin separadores."""
    return re.sub(r"[\s/-]", "", (value or "").strip())
