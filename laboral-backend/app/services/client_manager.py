"""Gestión de clientes (empresas) para PGK Laboral Desk.

PGK es la asesoría. Cada cliente es una empresa a la que PGK gestiona
su nómina/laboral. Cada cliente tiene asociado un convenio colectivo.

Uso:
    from client_manager import ClientManager
    cm = ClientManager()
    cm.init_tables()
    client_id = cm.register_client(
        empresa="Despacho Ejemplo S.L.",
        cif="B12345678",
        provincia="Alicante",
        comunidad_autonoma="Comunitat Valenciana",
        cnae="6910",
        convenio_id="convenio_oficinas_despachos_alicante_2024_2026",
    )
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DB_PATH = _REPO_ROOT / "db" / "pgk_laboral.db"
_DATA_DIR = _REPO_ROOT / "data"

# Provincias españolas (código INE)
PROVINCIAS_ES = [
    "Álava",
    "Albacete",
    "Alicante",
    "Almería",
    "Ávila",
    "Badajoz",
    "Baleares",
    "Barcelona",
    "Burgos",
    "Cáceres",
    "Cádiz",
    "Castellón",
    "Ciudad Real",
    "Córdoba",
    "Coruña (A)",
    "Cuenca",
    "Girona",
    "Granada",
    "Guadalajara",
    "Guipúzcoa",
    "Huelva",
    "Huesca",
    "Jaén",
    "León",
    "Lleida",
    "La Rioja",
    "Lugo",
    "Madrid",
    "Málaga",
    "Murcia",
    "Navarra",
    "Ourense",
    "Asturias",
    "Palencia",
    "Las Palmas",
    "Pontevedra",
    "Salamanca",
    "Santa Cruz de Tenerife",
    "Cantabria",
    "Segovia",
    "Sevilla",
    "Soria",
    "Tarragona",
    "Teruel",
    "Toledo",
    "Valencia",
    "Valladolid",
    "Vizcaya",
    "Zamora",
    "Zaragoza",
    "Ceuta",
    "Melilla",
]

CCAA_ES = [
    "Andalucía",
    "Aragón",
    "Asturias",
    "Baleares",
    "Canarias",
    "Cantabria",
    "Castilla-La Mancha",
    "Castilla y León",
    "Cataluña",
    "Ceuta",
    "Comunitat Valenciana",
    "Extremadura",
    "Galicia",
    "La Rioja",
    "Madrid",
    "Melilla",
    "Murcia",
    "Navarra",
    "País Vasco",
]


@dataclass
class Client:
    id: int
    empresa: str
    cif: str
    provincia: str
    comunidad_autonoma: str
    cnae: str
    convenio_id: str
    convenio_nombre: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "empresa": self.empresa,
            "cif": self.cif,
            "provincia": self.provincia,
            "comunidad_autonoma": self.comunidad_autonoma,
            "cnae": self.cnae,
            "convenio_id": self.convenio_id,
            "convenio_nombre": self.convenio_nombre,
            "created_at": self.created_at,
        }


class ClientManager:
    """CRUD de clientes empresariales."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or _DB_PATH

    def _get_db(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_tables(self) -> None:
        conn = self._get_db()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    empresa TEXT NOT NULL,
                    cif TEXT NOT NULL,
                    provincia TEXT NOT NULL DEFAULT '',
                    comunidad_autonoma TEXT NOT NULL DEFAULT '',
                    cnae TEXT NOT NULL DEFAULT '',
                    convenio_id TEXT NOT NULL,
                    convenio_nombre TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_cif
                    ON clients(cif);
            """)
            conn.commit()
        finally:
            conn.close()

    def register_client(
        self,
        empresa: str,
        cif: str,
        convenio_id: str,
        provincia: str = "",
        comunidad_autonoma: str = "",
        cnae: str = "",
    ) -> int:
        """Registra un nuevo cliente. Devuelve el ID.

        Args:
            empresa: Razón social.
            cif: NIF/CIF de la empresa (se valida formato).
            convenio_id: ID del convenio (nombre del JSON sin extensión).
            provincia: Provincia española.
            comunidad_autonoma: CC.AA.
            cnae: Código CNAE (opcional).

        Raises:
            ValueError: Si el CIF no es válido o el convenio no existe.
        """
        cif = cif.strip().upper()
        if not self.validate_cif(cif):
            raise ValueError(
                f"CIF/NIF no válido: {cif}. "
                "Formato esperado: letra + 8 dígitos o dígito + 7 dígitos + letra."
            )

        # Verificar convenio existe
        convenios = self.list_convenios()
        convenio_match = next((c for c in convenios if c["id"] == convenio_id), None)
        if not convenio_match:
            ids = [c["id"] for c in convenios]
            raise ValueError(f"Convenio no encontrado: {convenio_id}. Disponibles: {ids}")

        conn = self._get_db()
        try:
            cursor = conn.execute(
                """INSERT INTO clients
                   (empresa, cif, provincia, comunidad_autonoma, cnae,
                    convenio_id, convenio_nombre)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    empresa.strip(),
                    cif,
                    provincia,
                    comunidad_autonoma,
                    cnae,
                    convenio_id,
                    convenio_match["nombre"],
                ),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]
        finally:
            conn.close()

    def get_client(self, client_id: int) -> Client | None:
        conn = self._get_db()
        try:
            row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
            if row:
                return Client(**dict(row))
            return None
        finally:
            conn.close()

    def get_client_by_cif(self, cif: str) -> Client | None:
        conn = self._get_db()
        try:
            row = conn.execute(
                "SELECT * FROM clients WHERE cif = ?", (cif.strip().upper(),)
            ).fetchone()
            if row:
                return Client(**dict(row))
            return None
        finally:
            conn.close()

    def list_clients(self) -> list[dict[str, Any]]:
        conn = self._get_db()
        try:
            rows = conn.execute("SELECT * FROM clients ORDER BY empresa").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def update_convenio(self, client_id: int, convenio_id: str) -> None:
        """Cambia el convenio de un cliente."""
        convenios = self.list_convenios()
        match = next((c for c in convenios if c["id"] == convenio_id), None)
        if not match:
            raise ValueError(f"Convenio no encontrado: {convenio_id}")

        conn = self._get_db()
        try:
            conn.execute(
                "UPDATE clients SET convenio_id = ?, convenio_nombre = ? WHERE id = ?",
                (convenio_id, match["nombre"], client_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Convenios disponibles
    # ------------------------------------------------------------------

    @staticmethod
    def list_convenios(data_dir: Path | None = None) -> list[dict[str, Any]]:
        """Lista los convenios disponibles (JSONs en data/)."""
        d = data_dir or _DATA_DIR
        convenios: list[dict[str, Any]] = []
        for f in sorted(d.glob("convenio_*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                conv = data.get("convenio", {})
                convenios.append(
                    {
                        "id": f.stem,
                        "nombre": conv.get("nombre", f.stem),
                        "codigo": conv.get("codigo", ""),
                        "ambito": conv.get("ambito", "estatal"),
                        "vigencia_desde": conv.get("vigencia_desde_ano"),
                        "vigencia_hasta": conv.get("vigencia_hasta_ano"),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return convenios

    # ------------------------------------------------------------------
    # Validación CIF/NIF
    # ------------------------------------------------------------------

    @staticmethod
    def validate_cif(cif: str) -> bool:
        """Valida formato NIF/CIF español (no verifica dígito de control)."""
        cif = cif.strip().upper()
        # NIF: 8 dígitos + letra
        if re.match(r"^\d{8}[A-Z]$", cif):
            return True
        # CIF: letra + 7 dígitos + dígito/letra
        if re.match(r"^[ABCDEFGHJKLMNPQRSUVW]\d{7}[0-9A-J]$", cif):
            return True
        # NIE: X/Y/Z + 7 dígitos + letra
        if re.match(r"^[XYZ]\d{7}[A-Z]$", cif):
            return True
        return False
