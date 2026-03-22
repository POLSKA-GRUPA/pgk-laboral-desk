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
        """)

        # Sembrar usuario MPC si no existe
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", ("mpc",)
        ).fetchone()
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
        # Sembrar usuario admin PGK
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
                    "convenio_acuaticas_2025_2027",
                    "admin",
                ),
            )
        conn.commit()
    finally:
        conn.close()


def authenticate(username: str, password: str, db_path: Path | None = None) -> dict[str, Any] | None:
    """Autentica un usuario.  Devuelve dict con datos o None."""
    conn = _get_db(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            return {
                "id": row["id"],
                "username": row["username"],
                "empresa_nombre": row["empresa_nombre"],
                "empresa_cif": row["empresa_cif"],
                "convenio_id": row["convenio_id"],
                "role": row["role"],
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
    user_id: int, status: str = "pending", db_path: Path | None = None,
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


def dismiss_alert(alert_id: int, db_path: Path | None = None) -> None:
    """Marca una alerta como resuelta."""
    conn = _get_db(db_path)
    try:
        conn.execute(
            "UPDATE alerts SET status = 'resolved' WHERE id = ?", (alert_id,)
        )
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------
# Consultas
# ------------------------------------------------------------------

def get_consultations(
    user_id: int, limit: int = 20, db_path: Path | None = None,
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
            results.append({
                "id": row["id"],
                "query_summary": row["query_summary"],
                "coste_empresa": coste,
                "created_at": row["created_at"],
            })
        return results
    finally:
        conn.close()
