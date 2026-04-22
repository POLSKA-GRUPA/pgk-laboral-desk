# Arquitectura

> Revisado: 2026‑04‑22. Este documento describe el estado actual del repositorio
> (v2 Flask + v3 FastAPI en paralelo, capa MCP en desarrollo).

## Visión general

`pgk-laboral-desk` es un **application server de dominio laboral español** que
expone:

- **Tools MCP** a agentes de IA (Claude Desktop, Cursor, Windsurf, ChatGPT
  Desktop) vía stdio/SSE.
- **API HTTP/JSON** a clientes propios (PGK‑Despacho‑Desktop, frontend web,
  automatizaciones internas).
- **Agente CodeAct** propio (`laboral_agent.py`) que usa un LLM externo
  (Gemini / Anthropic / z.ai) para razonar y orquestar llamadas al motor
  determinista.

El núcleo es un **motor determinista sin IA** (`engine.py` +
`ss_calculator.py` + `irpf_estimator.py`) alimentado por datos estructurados
en `data/` (convenios colectivos BOE, tasas SS 2026, knowledge base laboral).
El LLM **nunca** produce números fiscales: sólo interpreta, orquesta y redacta.

---

## Capas

### 1. Datos (fuente de verdad)

- `data/convenio_*.json` — convenios colectivos estructurados (acuáticas,
  oficinas y despachos Alicante, …). Metadatos + tablas salariales + secciones
  articuladas.
- `data/ss_config.json` — tasas de cotización 2026 (Orden ISM/31/2026 ·
  BOE‑A‑2026‑1921, RDL 3/2026 · BOE‑A‑2026‑2548), topes max/min, grupos de
  cotización, recargos para contratos ≤30 días, SMI anual, IPC.
- `data/knowledge_base/` — base normativa para RAG:
  - `contract_types.json` — 72 tipos de contrato con códigos SEPE (45 XSD) y
    base legal (RDL 32/2021, RDL 1/2023, ET RDL 2/2015).
  - `seguridad_social_rules.json` — reglas RETA, régimen general, bonificaciones,
    pluriactividad.
  - `sistema_red_procedures.json` — flujos Sistema RED para altas/bajas.
- `data/categorias_detalle.json` — detalle adicional por categoría.

Principio: **si un valor fiscal no está en `data/`, es un bug**. Nada
hardcodeado en Python.

### 2. Motor determinista

- `engine.py` — núcleo:
  - normaliza texto libre,
  - detecta categoría / jornada / modalidad / antigüedad / pagas,
  - carga convenio (auto-detecta 14 vs 15 pagas vía
    `resumen_operativo.pagas_extras`),
  - decide si hay datos suficientes para cerrar pre‑nómina,
  - orquesta SS + IRPF + pre‑nómina,
  - calcula despido/finiquito con consejo estratégico.
- `ss_calculator.py` — Seguridad Social 2026, 11 grupos de cotización,
  recargo contratos ≤30 días, topes.
- `irpf_estimator.py` — escala estatal + escalas autonómicas de Madrid,
  Cataluña, Andalucía, Valencia.
- `nomina_pdf.py` — genera pre‑nómina en PDF o HTML usando WeasyPrint.
- `client_manager.py` — multi‑cliente / multi‑convenio sobre SQLite,
  validación CIF/NIF/NIE.
- `database.py` — SQLite (`/data/laboral.db` en prod, `data/laboral.db` en
  dev): users, employees, consultations, alerts.
- `convenio_verifier.py` — advisory vía Perplexity, comprueba vigencia de
  convenios cargados.
- `rates_verifier.py` — comprueba drift de tasas SS/IRPF/SMI respecto a
  fuentes oficiales.
- `boe_importer.py` — descarga sumario BOE y parsea XML de convenios
  colectivos estatales.

### 3. Capa IA

- `chat_parser.py` — parser determinista (reglas + keywords) con `regex` y
  diccionarios. Funciona sin LLM. Se usa como **fallback** si no hay API key
  configurada.
- `vgrag_search.py` — RAG semántico opcional (feature flag
  `LABORAL_VECTOR_GRAPH_RAG=true`) sobre Z.ai + MiniLM + Milvus local.
  Indexa categorías y artículos de convenio, permite búsqueda multi‑hop.
- `laboral_agent.py` — **agente CodeAct**:
  - LLM (Gemini / Anthropic) recibe la consulta + prompt del sistema con las
    tools disponibles.
  - LLM escribe **código Python** dentro de bloques ```` ```python ... ``` ````.
  - Un **sandbox** (`_validate_code_safety` AST + `_SAFE_BUILTINS` + bloqueo
    de dunders) ejecuta el código y expone las tools (`simular_contrato`,
    `buscar_por_presupuesto`, `calcular_despido`, `listar_categorias`, …).
  - Hasta 5 iteraciones para converger en respuesta final.
  - Modo request/response (`chat`) y streaming SSE (`stream_chat`).
- `mcp_server.py` — schema de tools MCP:
  - `laboral_calcular_nomina`, `laboral_consultar_convenio`,
    `laboral_calcular_ss`, `laboral_estimar_irpf`.
  - Handler async `handle_mcp_request(method, params)` con soporte de
    `tools/list`, `tools/call`, `resources/list`.
  - **Estado:** pendiente de binding stdio/SSE y dep `mcp>=1.0` del SDK oficial
    de Anthropic. Ver `AGENTS.md §MCP`.

### 4. API HTTP

- `app.py` (v2 Flask) — activo en la capa IA:
  - `POST /api/auth/login` · `POST /api/auth/logout` · `GET /api/auth/me`
  - `GET /api/categories` · `GET /api/contract-types` · `GET /api/regions`
  - `POST /api/simulate` · `GET /api/history`
  - `GET /api/convenio` · `GET /api/tipos-despido` · `POST /api/despido`
  - `POST /api/chat` · `POST /api/chat/reset`
  - **`GET /api/agent/status` · `POST /api/agent/chat` · `POST /api/agent/stream`**
  - `GET /api/alerts` · `POST /api/alerts` · `POST /api/alerts/<id>/dismiss`
  - `GET /api/employees` · `POST /api/employees` · `PUT /api/employees/<id>`
  - `POST /api/employees/<id>/despido` · `GET /api/employees/<id>/nomina`
- `laboral-backend/app/main.py` (v3 FastAPI) — el que corre en producción:
  - Routers: `health`, `auth`, `employees`, `chat`, `consultations`,
    `convenios`, `dismissal`, `employee_dismissal`, `payroll`, `reference`,
    `sepe`, `simulation`, `audit`, `alerts`.
  - Middleware: `RequestIDMiddleware`, `SecurityHeadersMiddleware`,
    `TimingMiddleware`, CORS.
  - **Regresión conocida:** no cablea el agente CodeAct ni el MCP. Los archivos
    `laboral-backend/app/services/laboral_agent.py` y equivalentes existen
    pero ninguna ruta los expone.

### 5. Frontends

- `static/` (v2) — HTML/CSS/JS vanilla: `index.html` (login), `panel.html`
  (dashboard con chat + formulario + resultado), `app.js`, `styles.css`.
- `laboral-frontend/` (v3) — React 18 + TypeScript + Ant Design 5 + Vite 6 +
  Recharts: páginas Dashboard, Chat, Simulation, Payroll, Dismissal,
  Employees, Convenios, Alerts, Settings.

---

## Flujo de una consulta (modo agente)

```
usuario ──▶ UI (panel.html / Chat.tsx) ──▶ POST /api/agent/chat
                                                │
                                                ▼
                                         app.py (_get_agent)
                                                │
                                                ▼
                                       laboral_agent.py
                                                │
                                                ▼
                                   LLM (Gemini / Anthropic)
                                                │   "devuelve bloque python"
                                                ▼
                                  sandbox.execute(code)
                                    │
                                    ├─▶ simular_contrato() ─┐
                                    ├─▶ calcular_despido()  │
                                    └─▶ listar_categorias()  ├─▶ engine.py ─▶ ss/irpf
                                                            ─┘      │
                                                                    ▼
                                                              data/*.json
                                                │
                                                ▼
                                         output (stdout) ─▶ LLM
                                                │
                                                ▼
                                        respuesta final al usuario
```

## Flujo de una consulta (modo determinista / sin LLM)

```
usuario ──▶ POST /api/chat ──▶ chat_parser.ChatParser.parse()
                                   │
                                   ├─▶ regex + keywords
                                   ├─▶ (opcional) vgrag_search.search_categoria()
                                   ▼
                            action = "ready" / "clarify" / "need_params"
                                   │
                                   ▼
                            engine.simulate(...)  ──▶ ss + irpf + nomina
                                   │
                                   ▼
                                 respuesta
```

## Flujo de una tool MCP (cuando el PR esté mergeado)

```
Claude Desktop / Cursor ─── MCP (stdio) ──▶ mcp_server_main.py
                                                │
                                                ▼
                                     mcp_server.handle_mcp_request(
                                       method="tools/call",
                                       params={"name": "laboral_calcular_nomina",
                                               "arguments": {...}})
                                                │
                                                ▼
                                            _calcular_nomina(args)
                                                │
                                                ▼
                                         engine / ss / irpf
                                                │
                                                ▼
                                     respuesta JSON con deduces,
                                     referencias BOE, trazabilidad
```

---

## Criterios de cálculo

- **Jornada completa** de referencia: **40 h/semana**.
- **Cálculo económico** del motor:
  - salario base del convenio,
  - prorrata de pagas extras (si el convenio lo indica),
  - antigüedad por trienios (si aplica),
  - conceptos convencionales explícitamente incorporados.
- **Cuando aplica, encima se suma:**
  - cotización a la Seguridad Social (empresa + trabajador),
  - estimación de IRPF por comunidad autónoma,
  - bonificaciones de contrato y recargos por temporalidad ≤30 días.
- **Quedan fuera:**
  - incidencias de presencia real del mes (horas extras reales, ausencias),
  - MEI cuando no corresponde,
  - desempleo en contratos donde no proceda,
  - tributación internacional / convenios de doble imposición,
  - extranjería y permisos de trabajo.

---

## Persistencia

- **Dev:** SQLite local en `data/laboral.db`.
- **Prod:** SQLite en volumen Docker `laboral-pgk-data` montado en `/data`.
- Modelos v2 (`database.py`): `users`, `consultations`, `alerts`, `employees`.
- Modelos v3 (`laboral-backend/app/models/`): SQLAlchemy 2.0 con `user`,
  `employee`, `company`, `contract`, `dismissal`, `payroll`, `alert`,
  `consultation`, `convenio`.

## Despliegue

- Docker Swarm + Traefik + Dokploy en `209.74.72.83`.
- Imagen multi-stage: frontend-builder (Node 20) → backend (Python 3.12-slim).
- Runtime: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (usa
  `laboral-backend/`). **El Flask v2 de la raíz NO corre en producción**, pese
  a que mantiene las rutas `/api/agent/*` hoy únicas.
- Volumen persistente para SQLite y PDFs generados.
- Healthcheck: `GET /api/health` cada 30 s.

## CI/CD

- `.github/workflows/ci.yml`:
  - `lint-backend` — ruff sobre `laboral-backend/`
  - `test-backend` — pytest `laboral-backend/tests/` en Python 3.11 y 3.12
  - `build-frontend` — `npm ci && npm run build` en `laboral-frontend/`
  - `docker-build` — build de imagen (no la publica)
- `.github/workflows/deploy.yml`:
  - se dispara al terminar `ci` con éxito
  - SSH a servidor → `git pull` → `docker build` → `docker service update
    --force`

## Extensión futura

Prioridades, por orden (ver `AGENTS.md §Hoja de ruta`):

1. Servir MCP real (stdio + SSE, SDK oficial `mcp>=1.0`).
2. Audit trail persistente del agente (tabla `agent_runs`).
3. Cron mensual `verify-rates-monthly.yml` + PR automático.
4. Pipeline RAG (`scripts/index_convenios.py` en lifespan) + eval dataset en CI.
5. Cablear agente + MCP en v3 FastAPI (`routes/agent.py`, `routes/mcp.py`).
6. Consolidar v2/v3 cuando v3 ya exponga toda la capa IA.
7. Seguridad: rotar creds seed, `DEFAULT_ADMIN_PASSWORD` obligatoria, SSH key
   + usuario no‑root.
8. (Opcional) Publicar paquete PyPI `pgk-laboral-mcp` para que otros
   despachos laborales españoles conecten sus Claude Desktop al motor.
