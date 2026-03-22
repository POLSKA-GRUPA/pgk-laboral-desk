"""PGK Laboral Desk — servidor Flask."""

from __future__ import annotations

import os
import secrets
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    redirect,
    request,
    send_from_directory,
    session,
)

from database import (
    authenticate, dismiss_alert, get_alerts, get_consultations,
    init_db, save_alert, save_consultation,
)
from engine import LaboralEngine
from chat_parser import ChatParser

APP_ROOT = Path(__file__).resolve().parent
STATIC_DIR = APP_ROOT / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

# Inicializar DB y motor
init_db()
engine = LaboralEngine.from_json_file()
chat_parser = ChatParser()


# ------------------------------------------------------------------
# Auth helpers
# ------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "No autenticado"}), 401
            return redirect("/")
        return f(*args, **kwargs)
    return decorated


# ------------------------------------------------------------------
# Páginas
# ------------------------------------------------------------------

@app.route("/")
def index():
    if "user_id" in session:
        return redirect("/panel")
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/panel")
@login_required
def panel():
    return send_from_directory(str(STATIC_DIR), "panel.html")


# ------------------------------------------------------------------
# Auth API
# ------------------------------------------------------------------

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not username or not password:
        return jsonify({"error": "Usuario y contraseña requeridos"}), 400

    user = authenticate(username, password)
    if not user:
        return jsonify({"error": "Credenciales incorrectas"}), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["empresa_nombre"] = user["empresa_nombre"]
    session["convenio_id"] = user["convenio_id"]
    session["role"] = user["role"]

    return jsonify({
        "ok": True,
        "user": {
            "username": user["username"],
            "empresa_nombre": user["empresa_nombre"],
            "role": user["role"],
        },
    })


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me")
@login_required
def api_me():
    return jsonify({
        "username": session["username"],
        "empresa_nombre": session["empresa_nombre"],
        "convenio_id": session["convenio_id"],
        "role": session["role"],
    })


# ------------------------------------------------------------------
# Datos para el formulario
# ------------------------------------------------------------------

@app.route("/api/categories")
@login_required
def api_categories():
    return jsonify(engine.get_categories())


@app.route("/api/contract-types")
@login_required
def api_contract_types():
    return jsonify(engine.get_contract_types())


# ------------------------------------------------------------------
# Simulación
# ------------------------------------------------------------------

@app.route("/api/simulate", methods=["POST"])
@login_required
def api_simulate():
    data = request.get_json(silent=True) or {}
    category = str(data.get("category", "")).strip()
    if not category:
        return jsonify({"error": "Selecciona una categoría profesional"}), 400

    result = engine.simulate(
        category=category,
        contract_type=str(data.get("contract_type", "indefinido")),
        weekly_hours=float(data.get("weekly_hours", 40)),
        seniority_years=int(data.get("seniority_years", 0)),
        extras_prorated=bool(data.get("extras_prorated", False)),
        num_children=int(data.get("num_children", 0)),
        children_under_3=int(data.get("children_under_3", 0)),
    )

    if "error" in result:
        return jsonify(result), 400

    # Guardar en historial
    summary = f"{result['categoria']} · {result['contrato']} · {result['jornada_pct']}%"
    save_consultation(
        user_id=session["user_id"],
        query_summary=summary,
        request_data=data,
        result_data=result,
    )

    return jsonify(result)


# ------------------------------------------------------------------
# Historial
# ------------------------------------------------------------------

@app.route("/api/history")
@login_required
def api_history():
    consultations = get_consultations(user_id=session["user_id"])
    return jsonify(consultations)


# ------------------------------------------------------------------
# Convenio
# ------------------------------------------------------------------

@app.route("/api/convenio")
@login_required
def api_convenio():
    return jsonify({
        "convenio": engine.data["convenio"],
        "sections": engine.data["sections"],
    })


# ------------------------------------------------------------------
# Alertas / Caducidad
# ------------------------------------------------------------------

@app.route("/api/alerts")
@login_required
def api_alerts():
    alerts = get_alerts(user_id=session["user_id"])
    return jsonify(alerts)


@app.route("/api/alerts", methods=["POST"])
@login_required
def api_create_alert():
    data = request.get_json(silent=True) or {}
    required = ["alert_type", "title", "due_date"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400
    alert_id = save_alert(
        user_id=session["user_id"],
        alert_type=data["alert_type"],
        title=data["title"],
        description=data.get("description", ""),
        due_date=data["due_date"],
        worker_name=data.get("worker_name", ""),
        category=data.get("category", ""),
    )
    return jsonify({"ok": True, "id": alert_id})


@app.route("/api/alerts/<int:alert_id>/dismiss", methods=["POST"])
@login_required
def api_dismiss_alert(alert_id: int):
    dismiss_alert(alert_id)
    return jsonify({"ok": True})


# ------------------------------------------------------------------
# Chat conversacional
# ------------------------------------------------------------------

@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"error": "Escribe algo"}), 400

    # Contexto de conversación en sesión
    ctx = session.get("chat_context", {})

    # Parsear mensaje
    result = chat_parser.parse(message, ctx)
    action = result.get("action")

    # Guardar contexto actualizado
    session["chat_context"] = result.get("context", {})

    if action == "ready":
        sim_result = engine.simulate(**result["params"])
        if "error" in sim_result:
            return jsonify({"type": "error", "message": sim_result["error"]})

        # Añadir extras del contrato y avisos al resultado
        sim_result["contract_extras"] = result.get("contract_extras", {})
        sim_result["contract_warnings"] = result.get("contract_warnings", [])

        summary = f"{sim_result['categoria']} · {sim_result['contrato']} · {sim_result['jornada_pct']}%"
        save_consultation(
            user_id=session["user_id"],
            query_summary=summary,
            request_data=result["params"],
            result_data=sim_result,
        )

        session.pop("chat_context", None)
        return jsonify({"type": "result", "data": sim_result})

    if action in ("clarify_category", "need_params"):
        return jsonify({
            "type": "question",
            "message": result["message"],
            "options": result.get("options", []),
        })

    if action == "not_found":
        session.pop("chat_context", None)
        return jsonify({"type": "not_found", "message": result["message"]})

    return jsonify({"type": "error", "message": "Error interno"}), 500


@app.route("/api/chat/reset", methods=["POST"])
@login_required
def api_chat_reset():
    session.pop("chat_context", None)
    return jsonify({"ok": True})


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@app.route("/api/health")
def api_health():
    return jsonify({"ok": True, "convenio": engine.data["convenio"]["nombre"]})


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PGK Laboral Desk")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"PGK Laboral Desk → http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
