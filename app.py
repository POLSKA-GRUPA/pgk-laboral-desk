"""PGK Laboral Desk — servidor Flask."""

from __future__ import annotations

import os
import secrets
import time
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

from chat_parser import ChatParser
from client_manager import ClientManager
from convenio_verifier import ConvenioVerifier
from database import (
    add_employee,
    authenticate,
    dismiss_alert,
    get_alerts,
    get_consultations,
    get_employee,
    get_employees,
    init_db,
    save_alert,
    save_consultation,
    update_employee,
)
from engine import LaboralEngine
from exceptions import AuthenticationError, LaboralBaseError, ValidationError
from logging_config import get_logger, setup_logging
from nomina_pdf import (
    DatosEmpresa,
    build_nomina_from_simulation,
    generate_nomina_html_string,
    generate_nomina_pdf,
)
from rates_verifier import RatesVerifier

APP_ROOT = Path(__file__).resolve().parent
STATIC_DIR = APP_ROOT / "static"

log = setup_logging()
logger = get_logger("app")

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

# Inicializar DB y motor
init_db()
logger.info("Database initialized")
chat_parser = ChatParser()
client_mgr = ClientManager()
client_mgr.init_tables()
convenio_verifier = ConvenioVerifier()
rates_verifier = RatesVerifier()

# Cache de engines por convenio (evita recargar JSON en cada request)
_engine_cache: dict[str, LaboralEngine] = {}


def _get_engine(convenio_id: str | None = None) -> LaboralEngine:
    """Devuelve el engine del convenio indicado (o el del usuario en sesión)."""
    cid = convenio_id or session.get("convenio_id", "")
    if not cid:
        cid = "convenio_acuaticas_2025_2027"  # fallback
    if cid not in _engine_cache:
        try:
            _engine_cache[cid] = LaboralEngine.from_convenio_id(cid)
        except FileNotFoundError:
            _engine_cache[cid] = LaboralEngine.from_json_file()  # fallback
    return _engine_cache[cid]


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

    return jsonify(
        {
            "ok": True,
            "user": {
                "username": user["username"],
                "empresa_nombre": user["empresa_nombre"],
                "role": user["role"],
            },
        }
    )


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me")
@login_required
def api_me():
    return jsonify(
        {
            "username": session["username"],
            "empresa_nombre": session["empresa_nombre"],
            "convenio_id": session["convenio_id"],
            "role": session["role"],
        }
    )


# ------------------------------------------------------------------
# Datos para el formulario
# ------------------------------------------------------------------


@app.route("/api/categories")
@login_required
def api_categories():
    return jsonify(_get_engine().get_categories())


@app.route("/api/contract-types")
@login_required
def api_contract_types():
    return jsonify(_get_engine().get_contract_types())


@app.route("/api/regions")
@login_required
def api_regions():
    return jsonify(_get_engine().get_regions())


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

    eng = _get_engine()
    try:
        result = eng.simulate(
            category=category,
            contract_type=str(data.get("contract_type", "indefinido")),
            weekly_hours=float(data.get("weekly_hours", 40)),
            seniority_years=int(data.get("seniority_years", 0)),
            extras_prorated=bool(data.get("extras_prorated", False)),
            num_children=int(data.get("num_children", 0)),
            children_under_3=int(data.get("children_under_3", 0)),
            region=str(data.get("region", "generica")),
            contract_days=data.get("contract_days"),
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"error": f"Datos inválidos: {exc}"}), 400

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
    eng = _get_engine()
    return jsonify(
        {
            "convenio": eng.data["convenio"],
            "sections": eng.data["sections"],
        }
    )


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
    ok = dismiss_alert(alert_id, user_id=session["user_id"])
    if not ok:
        return jsonify({"error": "Alerta no encontrada"}), 404
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
        sim_result = _get_engine().simulate(**result["params"])
        if "error" in sim_result:
            return jsonify({"type": "error", "message": sim_result["error"]})

        # Añadir extras del contrato y avisos al resultado
        sim_result["contract_extras"] = result.get("contract_extras", {})
        sim_result["contract_warnings"] = result.get("contract_warnings", [])

        summary = (
            f"{sim_result['categoria']} · {sim_result['contrato']} · {sim_result['jornada_pct']}%"
        )
        save_consultation(
            user_id=session["user_id"],
            query_summary=summary,
            request_data=result["params"],
            result_data=sim_result,
        )

        session.pop("chat_context", None)
        return jsonify({"type": "result", "data": sim_result})

    if action in ("clarify_category", "need_params"):
        return jsonify(
            {
                "type": "question",
                "message": result["message"],
                "options": result.get("options", []),
            }
        )

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
# Tipos de despido
# ------------------------------------------------------------------


@app.route("/api/tipos-despido")
@login_required
def api_tipos_despido():
    return jsonify(_get_engine().get_tipos_despido())


# ------------------------------------------------------------------
# Despido / extinción laboral
# ------------------------------------------------------------------


@app.route("/api/despido", methods=["POST"])
@login_required
def api_despido():
    data = request.get_json(silent=True) or {}
    required = ["tipo_despido", "fecha_inicio", "salario_bruto_mensual"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    eng = _get_engine()
    try:
        result = eng.calcular_despido(
            tipo_despido=str(data["tipo_despido"]),
            fecha_inicio=str(data["fecha_inicio"]),
            salario_bruto_mensual=float(data["salario_bruto_mensual"]),
            fecha_despido=data.get("fecha_despido") or None,
            dias_vacaciones_pendientes=int(data.get("dias_vacaciones_pendientes", 0)),
            dias_preaviso_empresa=int(data.get("dias_preaviso_empresa", 0)),
            weekly_hours=float(data.get("weekly_hours", 40)),
            nombre_trabajador=str(data.get("nombre_trabajador", "")),
            categoria=str(data.get("categoria", "")),
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"error": f"Datos inválidos: {exc}"}), 400

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


# ------------------------------------------------------------------
# Plantilla de trabajadores
# ------------------------------------------------------------------


@app.route("/api/employees")
@login_required
def api_employees_list():
    status = request.args.get("status", "activo")
    employees = get_employees(user_id=session["user_id"], status=status)
    return jsonify(employees)


@app.route("/api/employees", methods=["POST"])
@login_required
def api_employees_create():
    data = request.get_json(silent=True) or {}
    required = ["nombre", "categoria", "fecha_inicio"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400

    # Calcular salario desde el motor si no se especifica
    salario = data.get("salario_bruto_mensual")
    if not salario:
        eng = _get_engine()
        sim = eng.simulate(
            category=str(data["categoria"]),
            contract_type=str(data.get("contrato_tipo", "indefinido")),
            weekly_hours=float(data.get("jornada_horas", 40)),
            seniority_years=0,
        )
        if "error" not in sim:
            salario = sim["bruto_mensual_eur"]

    try:
        emp_id = add_employee(
            user_id=session["user_id"],
            nombre=str(data["nombre"]),
            categoria=str(data["categoria"]),
            contrato_tipo=str(data.get("contrato_tipo", "indefinido")),
            jornada_horas=float(data.get("jornada_horas", 40)),
            fecha_inicio=str(data["fecha_inicio"]),
            fecha_fin=data.get("fecha_fin") or None,
            salario_bruto_mensual=float(salario) if salario else None,
            num_hijos=int(data.get("num_hijos", 0)),
            notas=str(data.get("notas", "")),
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"error": f"Datos inválidos: {exc}"}), 400

    # Crear alertas automáticas
    emp = get_employee(emp_id)
    if emp:
        _auto_alerts_for_employee(emp)

    return jsonify({"ok": True, "id": emp_id}), 201


@app.route("/api/employees/<int:emp_id>", methods=["PUT"])
@login_required
def api_employees_update(emp_id: int):
    emp = get_employee(emp_id)
    if not emp or emp["user_id"] != session["user_id"]:
        return jsonify({"error": "No encontrado"}), 404
    data = request.get_json(silent=True) or {}
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
    }
    fields = {k: v for k, v in data.items() if k in allowed}
    update_employee(emp_id, fields)
    return jsonify({"ok": True})


@app.route("/api/employees/<int:emp_id>/despido", methods=["POST"])
@login_required
def api_employees_despido(emp_id: int):
    """Calcula el coste de despedir a un trabajador concreto de la plantilla."""
    emp = get_employee(emp_id)
    if not emp or emp["user_id"] != session["user_id"]:
        return jsonify({"error": "Trabajador no encontrado"}), 404

    data = request.get_json(silent=True) or {}
    tipo = str(data.get("tipo_despido", "improcedente"))

    salario = emp.get("salario_bruto_mensual")
    if not salario:
        eng = _get_engine()
        sim = eng.simulate(
            category=str(emp["categoria"]),
            contract_type=str(emp["contrato_tipo"]),
            weekly_hours=float(emp["jornada_horas"]),
        )
        salario = sim.get("bruto_mensual_eur", 1000.0) if "error" not in sim else 1000.0

    eng = _get_engine()
    result = eng.calcular_despido(
        tipo_despido=tipo,
        fecha_inicio=str(emp["fecha_inicio"]),
        salario_bruto_mensual=float(salario),
        fecha_despido=data.get("fecha_despido") or None,
        dias_vacaciones_pendientes=int(data.get("dias_vacaciones_pendientes", 0)),
        dias_preaviso_empresa=int(data.get("dias_preaviso_empresa", 0)),
        weekly_hours=float(emp["jornada_horas"]),
        nombre_trabajador=str(emp["nombre"]),
        categoria=str(emp["categoria"]),
    )

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


def _auto_alerts_for_employee(emp: dict) -> None:
    """Crea alertas automáticas para un nuevo empleado."""
    from datetime import date, timedelta

    try:
        inicio = date.fromisoformat(emp["fecha_inicio"])
        contrato = emp.get("contrato_tipo", "indefinido")

        # Fin de período de prueba
        prueba_dias = {
            "indefinido": 90,
            "temporal": 30,
            "fijo-discontinuo": 90,
        }.get(contrato, 30)
        fin_prueba = inicio + timedelta(days=prueba_dias)
        if fin_prueba >= date.today():
            save_alert(
                user_id=emp["user_id"],
                alert_type="fin_prueba",
                title=f"Fin período de prueba — {emp['nombre']}",
                description=f"Categoría: {emp['categoria']}. Revisa si continúa.",
                due_date=fin_prueba.isoformat(),
                worker_name=emp["nombre"],
                category=emp["categoria"],
            )

        # Fin de contrato (si es temporal con fecha fin)
        if emp.get("fecha_fin"):
            fin = date.fromisoformat(emp["fecha_fin"])
            aviso = fin - timedelta(days=15)
            if aviso >= date.today():
                save_alert(
                    user_id=emp["user_id"],
                    alert_type="fin_contrato",
                    title=f"Vencimiento contrato — {emp['nombre']}",
                    description=f"El contrato temporal vence el {emp['fecha_fin']}. Decide si renovar o finalizar.",
                    due_date=aviso.isoformat(),
                    worker_name=emp["nombre"],
                    category=emp["categoria"],
                )
    except (ValueError, KeyError):
        pass


# ------------------------------------------------------------------
# Pre-nómina PDF
# ------------------------------------------------------------------


def _empresa_from_session() -> DatosEmpresa:
    return DatosEmpresa(
        nombre=session.get("empresa_nombre", ""),
        cif="",
    )


@app.route("/api/employees/<int:emp_id>/nomina")
@login_required
def api_employee_nomina(emp_id: int):
    """Genera pre-nómina PDF para un empleado de la plantilla."""
    from flask import Response

    emp = get_employee(emp_id)
    if not emp or emp["user_id"] != session["user_id"]:
        return jsonify({"error": "Trabajador no encontrado"}), 404

    eng = _get_engine()
    sim = eng.simulate(
        category=str(emp["categoria"]),
        contract_type=str(emp["contrato_tipo"]),
        weekly_hours=float(emp["jornada_horas"]),
        seniority_years=0,
        num_children=int(emp.get("num_hijos", 0)),
    )
    if "error" in sim:
        return jsonify({"error": sim["error"]}), 400

    periodo = request.args.get("periodo")  # YYYY-MM
    fmt_type = request.args.get("format", "pdf")  # pdf | html

    try:
        nomina = build_nomina_from_simulation(
            sim,
            empresa=_empresa_from_session(),
            trabajador_extra={
                "nombre": emp["nombre"],
                "nif": "",
                "naf": "",
                "puesto": emp["categoria"],
                "antiguedad": f"{emp.get('fecha_inicio', '')}",
            },
            periodo_str=periodo,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if fmt_type == "html":
        html = generate_nomina_html_string(nomina)
        return Response(html, mimetype="text/html")

    try:
        pdf_bytes = generate_nomina_pdf(nomina)
    except RuntimeError:
        # WeasyPrint not installed — fall back to HTML
        html = generate_nomina_html_string(nomina)
        return Response(html, mimetype="text/html")

    nombre_safe = emp["nombre"].replace(" ", "_")[:30]
    filename = f"pre_nomina_{nombre_safe}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/api/nomina", methods=["POST"])
@login_required
def api_nomina_from_simulation():
    """Genera pre-nómina PDF a partir de datos de simulación directa."""
    from flask import Response

    data = request.get_json(silent=True) or {}
    category = str(data.get("category", "")).strip()
    if not category:
        return jsonify({"error": "Categoría requerida"}), 400

    eng = _get_engine()
    try:
        sim = eng.simulate(
            category=category,
            contract_type=str(data.get("contract_type", "indefinido")),
            weekly_hours=float(data.get("weekly_hours", 40)),
            seniority_years=int(data.get("seniority_years", 0)),
            extras_prorated=bool(data.get("extras_prorated", False)),
            num_children=int(data.get("num_children", 0)),
            children_under_3=int(data.get("children_under_3", 0)),
            region=str(data.get("region", "generica")),
            contract_days=data.get("contract_days"),
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"error": f"Datos inválidos: {exc}"}), 400

    if "error" in sim:
        return jsonify({"error": sim["error"]}), 400

    nombre = str(data.get("nombre_trabajador", "Trabajador"))
    periodo = data.get("periodo")
    fmt_type = str(data.get("format", "pdf"))

    try:
        nomina = build_nomina_from_simulation(
            sim,
            empresa=_empresa_from_session(),
            trabajador_extra={
                "nombre": nombre,
                "nif": "",
                "naf": "",
                "puesto": category,
            },
            periodo_str=periodo,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if fmt_type == "html":
        html = generate_nomina_html_string(nomina)
        return Response(html, mimetype="text/html")

    try:
        pdf_bytes = generate_nomina_pdf(nomina)
    except RuntimeError:
        html = generate_nomina_html_string(nomina)
        return Response(html, mimetype="text/html")

    nombre_safe = nombre.replace(" ", "_")[:30]
    filename = f"pre_nomina_{nombre_safe}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ------------------------------------------------------------------
# Clientes (multi-convenio)
# ------------------------------------------------------------------


@app.route("/api/convenios")
@login_required
def api_convenios_list():
    """Lista convenios disponibles."""
    return jsonify(LaboralEngine.list_available_convenios())


@app.route("/api/clients", methods=["GET"])
@login_required
def api_clients_list():
    if session.get("role") != "admin":
        return jsonify({"error": "Solo administradores"}), 403
    return jsonify(client_mgr.list_clients())


@app.route("/api/clients", methods=["POST"])
@login_required
def api_clients_register():
    if session.get("role") != "admin":
        return jsonify({"error": "Solo administradores"}), 403
    data = request.get_json(silent=True) or {}
    required = ["empresa", "cif", "convenio_id"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo requerido: {field}"}), 400
    try:
        client_id = client_mgr.register_client(
            empresa=data["empresa"],
            cif=data["cif"],
            convenio_id=data["convenio_id"],
            provincia=data.get("provincia", ""),
            comunidad_autonoma=data.get("comunidad_autonoma", ""),
            cnae=data.get("cnae", ""),
        )
        client = client_mgr.get_client(client_id)
        return jsonify({"ok": True, "client": client.to_dict()}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/clients/<int:client_id>/simulate", methods=["POST"])
@login_required
def api_client_simulate(client_id: int):
    """Simula usando el convenio del cliente."""
    client = client_mgr.get_client(client_id)
    if not client:
        return jsonify({"error": "Cliente no encontrado"}), 404
    try:
        client_engine = LaboralEngine.from_convenio_id(client.convenio_id)
    except FileNotFoundError:
        return jsonify({"error": f"Convenio no encontrado: {client.convenio_id}"}), 404

    data = request.get_json(silent=True) or {}
    category = str(data.get("category", "")).strip()
    if not category:
        return jsonify({"error": "Selecciona una categoría profesional"}), 400

    result = client_engine.simulate(
        category=category,
        contract_type=str(data.get("contract_type", "indefinido")),
        weekly_hours=float(data.get("weekly_hours", 40)),
        seniority_years=int(data.get("seniority_years", 0)),
        extras_prorated=bool(data.get("extras_prorated", False)),
        num_children=int(data.get("num_children", 0)),
        children_under_3=int(data.get("children_under_3", 0)),
        region=str(data.get("region", "generica")),
        contract_days=data.get("contract_days"),
    )
    if "error" in result:
        return jsonify(result), 400

    result["cliente"] = {"empresa": client.empresa, "cif": client.cif}
    return jsonify(result)


@app.route("/api/verify-rates")
@login_required
def api_verify_rates():
    """Verificación completa: SS, IRPF, SMI y revisión de convenios vía Perplexity.

    ?force=1 salta la caché de 24h y fuerza nueva consulta.
    """
    force = request.args.get("force", "0") == "1"
    result = rates_verifier.verify_all(force=force)
    return jsonify(result.to_dict())


@app.route("/api/verify-convenio", methods=["POST"])
@login_required
def api_verify_convenio():
    """Verificación orientativa de vigencia vía Perplexity."""
    data = request.get_json(silent=True) or {}
    sector = str(data.get("sector", "")).strip()
    provincia = str(data.get("provincia", "Estatal")).strip()
    if not sector:
        return jsonify({"error": "Campo requerido: sector"}), 400

    result = convenio_verifier.verify(
        sector=sector,
        provincia=provincia,
        codigo_convenio=str(data.get("codigo_convenio", "")),
        vigencia_hasta=data.get("vigencia_hasta"),
    )
    return jsonify(result.to_dict())


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------


@app.route("/api/health")
def api_health():
    """Health check with dependency status."""
    checks: dict[str, object] = {}

    # Check convenios
    try:
        convenios = LaboralEngine.list_available_convenios()
        checks["convenios"] = {"ok": True, "count": len(convenios)}
    except Exception as exc:
        checks["convenios"] = {"ok": False, "error": str(exc)}

    # Check database
    try:
        from database import _get_db

        conn = _get_db()
        conn.execute("SELECT 1")
        conn.close()
        checks["database"] = {"ok": True}
    except Exception as exc:
        checks["database"] = {"ok": False, "error": str(exc)}

    all_ok = all(isinstance(v, dict) and v.get("ok", False) for v in checks.values())
    return jsonify({"ok": all_ok, "checks": checks, "version": "0.2.0"}), 200 if all_ok else 503


# ------------------------------------------------------------------
# Error handlers
# ------------------------------------------------------------------


@app.errorhandler(ValidationError)
def handle_validation_error(exc: ValidationError):
    logger.warning("Validation error: %s (field=%s)", exc, exc.field)
    return jsonify({"error": str(exc), "code": exc.code, "field": exc.field}), 400


@app.errorhandler(AuthenticationError)
def handle_auth_error(exc: AuthenticationError):
    return jsonify({"error": str(exc), "code": exc.code}), 401


@app.errorhandler(LaboralBaseError)
def handle_laboral_error(exc: LaboralBaseError):
    logger.error("Laboral error: %s [%s]", exc, exc.code)
    return jsonify({"error": str(exc), "code": exc.code}), 500


@app.before_request
def log_request_start():
    request._start_time = time.monotonic()  # type: ignore[attr-defined]


@app.after_request
def log_request_end(response):
    start = getattr(request, "_start_time", None)
    duration = round((time.monotonic() - start) * 1000, 1) if start else 0
    if request.path != "/api/health":
        logger.info(
            "%s %s %s %.1fms",
            request.method,
            request.path,
            response.status_code,
            duration,
        )
    return response


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

    logger.info("PGK Laboral Desk starting on http://%s:%s", args.host, args.port)
    app.run(host=args.host, port=args.port, debug=args.debug)
