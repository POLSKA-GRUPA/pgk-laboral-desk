"""Map PGK contract types to SEPE Contrat@ codes.

PGK uses human-readable types (indefinido, temporal, etc.)
SEPE uses numeric codes (100, 200, 300, 401, 402, etc.)
This mapper bridges both worlds.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SEPEContractMapping:
    pgk_type: str
    sepe_code: str
    sepe_element: str
    is_full_time: bool
    is_indefinite: bool
    requires_end_date: bool
    requires_partial_time_data: bool


_MAPPINGS: tuple[SEPEContractMapping, ...] = (
    # Indefinidos tiempo completo
    SEPEContractMapping("indefinido", "100", "CONTRATO_100", True, True, False, False),
    SEPEContractMapping("indefinido-minusvalido", "130", "CONTRATO_130", True, True, False, False),
    SEPEContractMapping("indefinido-bonificado", "150", "CONTRATO_150", True, True, False, False),
    # Indefinidos tiempo parcial
    SEPEContractMapping("indefinido-parcial", "200", "CONTRATO_200", False, True, False, True),
    SEPEContractMapping(
        "indefinido-parcial-minusvalido", "230", "CONTRATO_230", False, True, False, True
    ),
    SEPEContractMapping(
        "indefinido-parcial-bonificado", "250", "CONTRATO_250", False, True, False, True
    ),
    # Fijo discontinuo
    SEPEContractMapping("fijo-discontinuo", "300", "CONTRATO_300", False, True, False, True),
    SEPEContractMapping(
        "fijo-discontinuo-minusvalido", "330", "CONTRATO_330", False, True, False, True
    ),
    SEPEContractMapping(
        "fijo-discontinuo-bonificado", "350", "CONTRATO_350", False, True, False, True
    ),
    # Temporales tiempo completo
    SEPEContractMapping("obra-servicio", "401", "CONTRATO_401", True, False, False, False),
    SEPEContractMapping(
        "circunstancias-produccion", "402", "CONTRATO_402", True, False, True, False
    ),
    SEPEContractMapping("insercion", "403", "CONTRATO_403", True, False, True, False),
    SEPEContractMapping("predoctoral", "404", "CONTRATO_404", True, False, False, False),
    SEPEContractMapping("politicas-activas", "405", "CONTRATO_405", True, False, True, False),
    SEPEContractMapping("fondos-europeos", "406", "CONTRATO_406", True, False, False, False),
    SEPEContractMapping("artistico", "407", "CONTRATO_407", True, False, False, False),
    SEPEContractMapping("universidades", "409", "CONTRATO_409", True, False, False, False),
    SEPEContractMapping("sustitucion", "410", "CONTRATO_410", True, False, False, False),
    SEPEContractMapping("investigador-doctor", "412", "CONTRATO_412", True, False, True, False),
    SEPEContractMapping("deportista", "413", "CONTRATO_413", True, False, False, False),
    SEPEContractMapping("formativo-practicas", "420", "CONTRATO_420", True, False, True, False),
    SEPEContractMapping("formacion-alternancia", "421", "CONTRATO_421", True, False, True, False),
    SEPEContractMapping("temporal-minusvalido", "430", "CONTRATO_430", True, False, True, False),
    SEPEContractMapping("relevo", "441", "CONTRATO_441", True, False, True, False),
    SEPEContractMapping("exclusion-social", "450", "CONTRATO_450", True, False, False, False),
    SEPEContractMapping("empresa-insercion", "452", "CONTRATO_452", True, False, True, False),
    # Temporales tiempo parcial
    SEPEContractMapping("obra-servicio-parcial", "501", "CONTRATO_501", False, False, False, True),
    SEPEContractMapping(
        "circunstancias-produccion-parcial", "502", "CONTRATO_502", False, False, True, True
    ),
    SEPEContractMapping("insercion-parcial", "503", "CONTRATO_503", False, False, True, True),
    SEPEContractMapping(
        "politicas-activas-parcial", "505", "CONTRATO_505", False, False, True, True
    ),
    SEPEContractMapping(
        "fondos-europeos-parcial", "506", "CONTRATO_506", False, False, False, True
    ),
    SEPEContractMapping("artistico-parcial", "507", "CONTRATO_507", False, False, False, True),
    SEPEContractMapping("universidades-parcial", "509", "CONTRATO_509", False, False, False, True),
    SEPEContractMapping("sustitucion-parcial", "510", "CONTRATO_510", False, False, False, True),
    SEPEContractMapping("deportista-parcial", "513", "CONTRATO_513", False, False, False, True),
    SEPEContractMapping(
        "formativo-practicas-parcial", "520", "CONTRATO_520", False, False, True, True
    ),
    SEPEContractMapping(
        "formacion-alternancia-parcial", "521", "CONTRATO_521", False, False, True, True
    ),
    SEPEContractMapping(
        "temporal-minusvalido-parcial", "530", "CONTRATO_530", False, False, True, True
    ),
    SEPEContractMapping("jubilacion-parcial", "540", "CONTRATO_540", False, False, False, True),
    SEPEContractMapping("relevo-parcial", "541", "CONTRATO_541", False, False, True, True),
    SEPEContractMapping(
        "exclusion-social-parcial", "550", "CONTRATO_550", False, False, False, True
    ),
    SEPEContractMapping(
        "empresa-insercion-parcial", "552", "CONTRATO_552", False, False, True, True
    ),
    # Otros
    SEPEContractMapping("colaboracion-social", "970", "CONTRATO_970", True, False, True, False),
    SEPEContractMapping("jubilacion-64", "980", "CONTRATO_980", True, False, False, False),
    SEPEContractMapping("otro", "990", "CONTRATO_990", True, False, False, False),
)

_BY_PGK_TYPE: dict[str, SEPEContractMapping] = {m.pgk_type: m for m in _MAPPINGS}
_BY_SEPE_CODE: dict[str, SEPEContractMapping] = {m.sepe_code: m for m in _MAPPINGS}


def resolve_pgk_to_sepe(pgk_tipo: str, jornada_horas: float = 40.0) -> SEPEContractMapping:
    """Resolve a PGK contract type + jornada to the correct SEPE code.

    Handles smart defaults:
    - "indefinido" with jornada < 40 -> 200 (indefinido-parcial)
    - "temporal" -> 402 (circunstancias-produccion) by default
    - "temporal" with jornada < 40 -> 502
    """
    jornada_is_partial = jornada_horas < 40.0

    if pgk_tipo in _BY_PGK_TYPE and jornada_is_partial:
        partial_variant = f"{pgk_tipo}-parcial"
        if partial_variant in _BY_PGK_TYPE:
            return _BY_PGK_TYPE[partial_variant]

    if pgk_tipo in _BY_PGK_TYPE:
        return _BY_PGK_TYPE[pgk_tipo]

    smart_defaults: dict[str, tuple[str, str]] = {
        "indefinido": ("indefinido-parcial" if jornada_is_partial else "indefinido", "100"),
        "temporal": (
            "circunstancias-produccion-parcial"
            if jornada_is_partial
            else "circunstancias-produccion",
            "402",
        ),
        "obra": ("obra-servicio-parcial" if jornada_is_partial else "obra-servicio", "401"),
        "formacion": (
            "formacion-alternancia-parcial" if jornada_is_partial else "formacion-alternancia",
            "421",
        ),
        "practicas": (
            "formativo-practicas-parcial" if jornada_is_partial else "formativo-practicas",
            "420",
        ),
        "interinidad": ("sustitucion-parcial" if jornada_is_partial else "sustitucion", "410"),
    }

    if pgk_tipo in smart_defaults:
        mapped_key, _ = smart_defaults[pgk_tipo]
        return _BY_PGK_TYPE.get(mapped_key, _BY_PGK_TYPE["indefinido"])

    return _BY_PGK_TYPE["indefinido"]


def resolve_sepe_code(code: str) -> SEPEContractMapping | None:
    """Look up a mapping by SEPE numeric code."""
    return _BY_SEPE_CODE.get(code)


def list_available_types() -> list[dict]:
    """Return all available PGK types with their SEPE mappings."""
    return [
        {
            "pgk_type": m.pgk_type,
            "sepe_code": m.sepe_code,
            "sepe_element": m.sepe_element,
            "is_full_time": m.is_full_time,
            "is_indefinite": m.is_indefinite,
        }
        for m in _MAPPINGS
    ]
