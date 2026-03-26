"""Gestión de base de datos SQLite para PGK Laboral Desk."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

_DB_PATH = Path(__file__).resolve().parent / "db" / "pgk_laboral.db"


def _get_db(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or _DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Aplica migraciones de esquema de forma segura (ALTER TABLE)."""
    migrations = [
        # Users: empresa fields
        ("users", "empresa_domicilio", "TEXT NOT NULL DEFAULT ''"),
        ("users", "empresa_ccc", "TEXT NOT NULL DEFAULT ''"),
        # Employees: identification fields
        ("employees", "nif", "TEXT NOT NULL DEFAULT ''"),
        ("employees", "naf", "TEXT NOT NULL DEFAULT ''"),
        ("employees", "domicilio", "TEXT NOT NULL DEFAULT ''"),
        ("employees", "email", "TEXT NOT NULL DEFAULT ''"),
        ("employees", "telefono", "TEXT NOT NULL DEFAULT ''"),
        ("employees", "region", "TEXT NOT NULL DEFAULT 'generica'"),
    ]
    import contextlib

    for table, column, col_type in migrations:
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_db(db_path: Path | None = None) -> None:
    """Crea las tablas si no existen y siembra usuario por defecto."""
    conn = _get_db(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                empresa_nombre TEXT NOT NULL DEFAULT '',
                empresa_cif TEXT NOT NULL DEFAULT '',
                convenio_id TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'client',
                empresa_domicilio TEXT NOT NULL DEFAULT '',
                empresa_ccc TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                query_summary TEXT NOT NULL DEFAULT '',
                request_data TEXT NOT NULL DEFAULT '{}',
                result_data TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_consultations_user
                ON consultations(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                alert_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                due_date TEXT NOT NULL,
                worker_name TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_alerts_user
                ON alerts(user_id, due_date);

            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                nombre TEXT NOT NULL,
                categoria TEXT NOT NULL,
                contrato_tipo TEXT NOT NULL DEFAULT 'indefinido',
                jornada_horas REAL NOT NULL DEFAULT 40.0,
                fecha_inicio TEXT NOT NULL,
                fecha_fin TEXT,
                salario_bruto_mensual REAL,
                num_hijos INTEGER NOT NULL DEFAULT 0,
                notas TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'activo',
                nif TEXT NOT NULL DEFAULT '',
                naf TEXT NOT NULL DEFAULT '',
                domicilio TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                telefono TEXT NOT NULL DEFAULT '',
                region TEXT NOT NULL DEFAULT 'generica',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_employees_user
                ON employees(user_id, status);
        """)

        # Sembrar usuario MPC si no existe (cliente acuáticas)
        existing = conn.execute("SELECT id FROM users WHERE username = ?", ("mpc",)).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO users (username, password_hash, empresa_nombre,
                   empresa_cif, convenio_id, role)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    "mpc",
                    generate_password_hash("mpc2025"),
                    "Mantenimiento Piscinas Comunidad S.L.",
                    "",
                    "convenio_acuaticas_2025_2027",
                    "client",
                ),
            )
        # Sembrar usuario admin PGK (oficinas y despachos Alicante)
        existing_admin = conn.execute(
            "SELECT id FROM users WHERE username = ?", ("pgk",)
        ).fetchone()
        if not existing_admin:
            conn.execute(
                """INSERT INTO users (username, password_hash, empresa_nombre,
                   empresa_cif, convenio_id, role)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    "pgk",
                    generate_password_hash("pgk2025"),
                    "PGK Hispania",
                    "",
                    "convenio_oficinas_despachos_alicante_2024_2026",
                    "admin",
                ),
            )
        else:
            # Actualizar convenio de pgk si ya existe con el viejo
            conn.execute(
                "UPDATE users SET convenio_id = ? WHERE username = ?",
                ("convenio_oficinas_despachos_alicante_2024_2026", "pgk"),
            )
        # Apply schema migrations for existing databases
        _migrate_schema(conn)

        conn.commit()
    finally:
        conn.close()


def authenticate(
    username: str, password: str, db_path: Path | None = None
) -> dict[str, Any] | None:
    """Autentica un usuario.  Devuelve dict con datos o None."""
    conn = _get_db(db_path)
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            return {
                "id": row["id"],
                "username": row["username"],
                "empresa_nombre": row["empresa_nombre"],
                "empresa_cif": row["empresa_cif"],
                "convenio_id": row["convenio_id"],
                "role": row["role"],
                "empresa_domicilio": row.get("empresa_domicilio", ""),
                "empresa_ccc": row.get("empresa_ccc", ""),
            }
        return None
    finally:
        conn.close()


def save_consultation(
    user_id: int,
    query_summary: str,
    request_data: dict[str, Any],
    result_data: dict[str, Any],
    db_path: Path | None = None,
) -> int:
    """Guarda una consulta y devuelve su ID."""
    conn = _get_db(db_path)
    try:
        cursor = conn.execute(
            """INSERT INTO consultations (user_id, query_summary, request_data, result_data)
               VALUES (?, ?, ?, ?)""",
            (
                user_id,
                query_summary,
                json.dumps(request_data, ensure_ascii=False),
                json.dumps(result_data, ensure_ascii=False),
            ),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


# ------------------------------------------------------------------
# Alertas / Caducidad
# ------------------------------------------------------------------


def save_alert(
    user_id: int,
    alert_type: str,
    title: str,
    description: str,
    due_date: str,
    worker_name: str = "",
    category: str = "",
    db_path: Path | None = None,
) -> int:
    """Crea una alerta. due_date en formato YYYY-MM-DD."""
    conn = _get_db(db_path)
    try:
        cursor = conn.execute(
            """INSERT INTO alerts (user_id, alert_type, title, description,
               due_date, worker_name, category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, alert_type, title, description, due_date, worker_name, category),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


def get_alerts(
    user_id: int,
    status: str = "pending",
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Devuelve las alertas de un usuario."""
    conn = _get_db(db_path)
    try:
        rows = conn.execute(
            """SELECT id, alert_type, title, description, due_date,
               worker_name, category, status, created_at
               FROM alerts WHERE user_id = ? AND status = ?
               ORDER BY due_date ASC""",
            (user_id, status),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def dismiss_alert(alert_id: int, user_id: int | None = None, db_path: Path | None = None) -> bool:
    """Marca una alerta como resuelta. Si user_id se pasa, verifica propiedad."""
    conn = _get_db(db_path)
    try:
        if user_id is not None:
            row = conn.execute("SELECT user_id FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            if row is None or row["user_id"] != user_id:
                return False
        conn.execute("UPDATE alerts SET status = 'resolved' WHERE id = ?", (alert_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# ------------------------------------------------------------------
# Consultas
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Plantilla de trabajadores
# ------------------------------------------------------------------


def add_employee(
    user_id: int,
    nombre: str,
    categoria: str,
    contrato_tipo: str = "indefinido",
    jornada_horas: float = 40.0,
    fecha_inicio: str = "",
    fecha_fin: str | None = None,
    salario_bruto_mensual: float | None = None,
    num_hijos: int = 0,
    notas: str = "",
    nif: str = "",
    naf: str = "",
    domicilio: str = "",
    email: str = "",
    telefono: str = "",
    region: str = "generica",
    db_path: Path | None = None,
) -> int:
    conn = _get_db(db_path)
    try:
        cursor = conn.execute(
            """INSERT INTO employees (user_id, nombre, categoria, contrato_tipo,
               jornada_horas, fecha_inicio, fecha_fin, salario_bruto_mensual,
               num_hijos, notas, nif, naf, domicilio, email, telefono, region)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                nombre,
                categoria,
                contrato_tipo,
                jornada_horas,
                fecha_inicio,
                fecha_fin,
                salario_bruto_mensual,
                num_hijos,
                notas,
                nif,
                naf,
                domicilio,
                email,
                telefono,
                region,
            ),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


def get_employees(
    user_id: int,
    status: str = "activo",
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    conn = _get_db(db_path)
    try:
        rows = conn.execute(
            """SELECT id, nombre, categoria, contrato_tipo, jornada_horas,
               fecha_inicio, fecha_fin, salario_bruto_mensual, num_hijos,
               notas, status, nif, naf, domicilio, email, telefono, region,
               created_at
               FROM employees WHERE user_id = ? AND status = ?
               ORDER BY nombre ASC""",
            (user_id, status),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_employee(employee_id: int, db_path: Path | None = None) -> dict[str, Any] | None:
    conn = _get_db(db_path)
    try:
        row = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_employee(
    employee_id: int,
    fields: dict[str, Any],
    db_path: Path | None = None,
) -> None:
    allowed = {
        "nombre",
        "categoria",
        "contrato_tipo",
        "jornada_horas",
        "fecha_inicio",
        "fecha_fin",
        "salario_bruto_mensual",
        "num_hijos",
        "notas",
        "status",
        "nif",
        "naf",
        "domicilio",
        "email",
        "telefono",
        "region",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    conn = _get_db(db_path)
    try:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE employees SET {set_clause} WHERE id = ?",
            [*updates.values(), employee_id],
        )
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------
# Consultas
# ------------------------------------------------------------------


def get_consultations(
    user_id: int,
    limit: int = 20,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Devuelve las últimas consultas de un usuario."""
    conn = _get_db(db_path)
    try:
        rows = conn.execute(
            """SELECT id, query_summary, result_data, created_at
               FROM consultations WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        results = []
        for row in rows:
            result_data = json.loads(row["result_data"]) if row["result_data"] else {}
            coste = result_data.get("coste_total_empresa_mes_eur", "—")
            results.append(
                {
                    "id": row["id"],
                    "query_summary": row["query_summary"],
                    "coste_empresa": coste,
                    "created_at": row["created_at"],
                }
            )
        return results
    finally:
        conn.close()
