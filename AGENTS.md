# AGENTS.md — PGK Laboral Desk

> Guía para agentes de IA (Claude Code, OpenCode, Gemini, Cursor, Cline, Windsurf, Devin) y
> desarrolladores humanos que trabajan en este repositorio.

---

## PROTOCOLO ENGRAM — OBLIGATORIO ANTES DE CUALQUIER ACCIÓN

**AL INICIAR** → llama `mem_context` para cargar contexto previo de la sesión.

**DESPUÉS de CADA acción significativa** → llama `mem_save` INMEDIATAMENTE:
- Código modificado → `mem_save` ahora
- Bug corregido → `mem_save` ahora
- Decisión tomada → `mem_save` ahora
- Patrón establecido → `mem_save` ahora
- Descubrimiento no obvio → `mem_save` ahora

**NO esperes al final de la sesión.** Si el contexto explota antes, TODO se pierde.

**AL CERRAR** → llama `mem_session_summary` con: Goal, Discoveries, Accomplished, Next Steps,
Relevant Files.

Esto aplica a Claude Code, OpenCode, Gemini, Cursor, Cline, Windsurf, Devin y cualquier agente
con acceso a Engram MCP.

### Memoria (Engram + MEMORY.md)
Usar **Engram** para memoria persistente estructurada entre sesiones:
- `mem_save` → guardar decisiones, errores, patrones
- `mem_search` → buscar contexto de sesiones anteriores
- `mem_context` → recuperar contexto reciente
- `mem_session_summary` → cerrar sesión con resumen
- `MEMORY.md` → resumen ejecutivo para arranque rápido

---

## Tesis del proyecto (léelo antes de tocar nada)

`pgk-laboral-desk` **no es una app laboral con IA encima**. Es lo contrario:

> un **application server para agentes de IA** en dominio **laboral español**, cuyo
> producto central son **herramientas (tools MCP) + datos estructurados trazables al
> BOE** que la IA puede invocar sin alucinar.

Hosts que se conectan:

- Claude Desktop, Cursor, Windsurf, ChatGPT Desktop vía **MCP (Model Context Protocol)**.
- PGK‑Despacho‑Desktop y otros clientes internos vía **HTTP/SSE**.
- Agente CodeAct propio (`laboral_agent.py`) que corre dentro de este mismo server.

```
┌───────────────────────────────────────────────────┐
│  HOSTS IA                                         │
│  Claude Desktop · Cursor · ChatGPT · Agentes PGK  │
└─────────────────▲─────────────────────────────────┘
                  │  MCP (stdio / SSE)
┌─────────────────┴─────────────────────────────────┐
│  pgk-laboral-desk                                 │
│                                                   │
│  mcp_server.py           — MCP tools schema       │
│  laboral_agent.py        — CodeAct (LLM + sandbox)│
│  chat_parser.py          — fallback determinista  │
│  vgrag_search.py         — RAG semántico opcional │
│                                                   │
│  engine.py  ss_calculator.py  irpf_estimator.py   │
│  nomina_pdf.py  client_manager.py  database.py    │
│                                                   │
│  data/                                            │
│    convenio_*.json        — tablas BOE            │
│    ss_config.json         — tasas SS 2026         │
│    knowledge_base/*.json  — reglas laborales      │
└───────────────────────────────────────────────────┘
```

### Principio fundamental (actualizado)

> **El LLM razona y orquesta. El engine calcula. Ningún número fiscal sale del LLM;
> todos salen de `data/` o del motor determinista.**

El motor (`engine.py` + `ss_calculator.py` + `irpf_estimator.py`) es **determinista y
trazable al convenio colectivo cargado y al BOE**. El agente IA sólo interpreta la
consulta, decide qué tools llamar, encadena cálculos y redacta la respuesta. Si el
cliente pregunta *"¿cómo calculó esto?"*, se reconstruye paso a paso.

Modelos soportados hoy (en orden de preferencia):
1. **Google Gemini** (`GEMINI_API_KEY` / `GOOGLE_API_KEY`, default `gemini-2.5-flash`)
2. **Anthropic Claude** (`ANTHROPIC_API_KEY`, default `claude-sonnet-4-20250514`;
   soporta proxy vía `ANTHROPIC_BASE_URL`)
3. **z.ai GLM-4.5** (`ZAI_API_KEY`) para el RAG semántico (`vgrag_search.py`)

Si no hay ninguna API key configurada, el sistema **degrada con gracia** al parser
determinista (`chat_parser.py`). Nunca se cae.

---

## Dos backends conviven hoy (importante)

El repositorio está **a medio migrar**. Ambos backends existen en `main`:

### Backend v2 — Flask (activo en capa IA, **NO en producción**)
- Entry point: `app.py` (raíz)
- Servicios: módulos planos en raíz (`engine.py`, `chat_parser.py`, `ss_calculator.py`,
  `irpf_estimator.py`, `nomina_pdf.py`, `client_manager.py`, `database.py`, etc.)
- **Único backend que expone la capa IA hoy** en `/api/agent/status`,
  `/api/agent/chat`, `/api/agent/stream`. Útil en desarrollo para probar agente.
- Lo arranca `python app.py --debug` (dev) o `gunicorn app:app` (prod, pendiente)
- **El Dockerfile NO lo empaqueta.** No corre en producción.
- Tests: `test_engine.py`, `test_chat_parser.py`, `test_client_manager.py`,
  `test_boe_importer.py`

### Backend v3 — FastAPI (en `laboral-backend/`, **el que corre en producción**, incompleto en capa IA)
- Entry point: `laboral-backend/app/main.py`
- Estructura modular: `routes/`, `models/`, `schemas/`, `services/`, `core/`
- **Lo que monta el Dockerfile y lo que corre en producción** (`uvicorn app.main:app`)
- **Regresión conocida:** no cablea ni `laboral_agent` ni el servidor MCP.
  `routes/chat.py` sólo usa `ChatParser` determinista. Los archivos
  `laboral-backend/app/services/laboral_agent.py` y equivalentes existen pero
  ninguna ruta los expone.
- Tests: `laboral-backend/tests/` (`test_calculators.py`, `test_real_nominas.py`,
  `test_sepe.py`, `test_auth.py`, etc.)

### ¿Qué toca si vas a modificar código?
- **Cambios en lógica de negocio (engine, SS, IRPF, chat_parser, nomina_pdf):**
  replicar en ambos lados hasta que la consolidación termine. Si sólo cambias un
  lado, el otro se desincroniza en silencio.
- **Cambios en la capa IA (agente, MCP, RAG):** hoy sólo están cableados en v2
  Flask. Para v3 hace falta crear `routes/agent.py` y `routes/mcp.py` antes.
- **Cambios de ruta nueva HTTP:** preferir v3 (FastAPI + pydantic) y dejar v2 como
  está; documentar en el PR qué endpoint es canónico.

### Frontends
- `static/` — HTML/CSS/JS vanilla. Sirve `index.html` (login) y `panel.html`
  (dashboard post-login). Consumido por v2 Flask.
- `laboral-frontend/` — React 18 + TypeScript + Ant Design 5 + Vite 6. Se construye
  a `laboral-backend/static/` durante el build Docker. Consumido por v3 FastAPI.

---

## Estructura real del repositorio

```
pgk-laboral-desk/
├── README.md
├── AGENTS.md                       ← este archivo
├── HANDOFF.md
├── MEMORY.md
├── pyproject.toml                  ← declara Flask + WeasyPrint (backend v2)
├── requirements.txt                ← runtime v2 (flask, weasyprint, …)
├── requirements-dev.txt            ← pytest, ruff
├── Dockerfile                      ← monta laboral-backend/ + laboral-frontend/
├── start.command                   ← launcher macOS para Flask dev
│
│  ── Backend v2 (raíz, Flask) ─────────────────────────
├── app.py                          Flask server, entry point
├── engine.py                       Motor determinista de cálculo
├── ss_calculator.py                Cotizaciones SS 2026
├── irpf_estimator.py               IRPF estatal + autonómico
├── chat_parser.py                  Parser conversacional (reglas + keywords)
├── nomina_pdf.py                   Generación pre-nómina PDF/HTML
├── database.py                     SQLite (users, employees, alerts)
├── client_manager.py               Multi-cliente / multi-convenio
├── convenio_verifier.py            Verificación vigencia vía Perplexity
├── rates_verifier.py               Verificación tasas SS/IRPF/SMI
├── boe_importer.py                 Importador de convenios desde BOE
├── exceptions.py                   Jerarquía de excepciones del dominio
├── validation.py                   Validación de entradas API
├── logging_config.py               Logging estructurado
├── mcp_server.py                   MCP tools schema (no servido aún, ver §MCP)
├── laboral_agent.py                Agente CodeAct (LLM + sandbox Python)
├── vgrag_search.py                 RAG semántico opcional (feature flag)
├── test_*.py                       Tests v2 (motor, parser, client, BOE)
│
│  ── Backend v3 (FastAPI, producción) ─────────────────
├── laboral-backend/
│   ├── app/
│   │   ├── main.py                 FastAPI entry, lifespan, routers
│   │   ├── core/                   config, deps, security, middleware, metrics…
│   │   ├── models/                 SQLAlchemy 2.0 (user, employee, company, …)
│   │   ├── schemas/                Pydantic (chat, payroll, dismissal, …)
│   │   ├── routes/                 health, auth, employees, chat, audit, sepe, …
│   │   ├── services/               engine, ss_calculator, irpf_estimator,
│   │   │                           nomina_audit_engine, nomina_audit_parser,
│   │   │                           sepe_xml_generator, reta_calculator, …
│   │   └── database.py             SQLAlchemy engine + init_db()
│   ├── tests/                      test_calculators, test_real_nominas, test_sepe…
│   ├── pyproject.toml              declara FastAPI + uvicorn + SQLAlchemy
│   └── requirements.txt
│
│  ── Frontend nuevo (React) ───────────────────────────
├── laboral-frontend/
│   ├── src/
│   │   ├── main.tsx  App.tsx
│   │   ├── pages/    Dashboard, Chat, Simulation, Payroll, Dismissal,
│   │   │             Employees, Convenios, Alerts, Settings
│   │   ├── components/  Sidebar, TopBar, LoginForm, ErrorBoundary
│   │   ├── services/api.ts
│   │   ├── hooks/useAuth.ts useApiCall.ts
│   │   └── styles/
│   └── package.json                React 18 + TS + AntD 5 + Vite 6
│
│  ── Frontend viejo (vanilla) ─────────────────────────
├── static/
│   ├── index.html                  login
│   ├── panel.html                  dashboard
│   ├── app.js                      lógica frontend
│   └── styles.css
│
│  ── Datos ─────────────────────────────────────────────
├── data/
│   ├── convenio_*.json             Convenios colectivos (BOE)
│   ├── ss_config.json              Tasas SS 2026 (Orden ISM/31/2026)
│   ├── categorias_detalle.json
│   └── knowledge_base/
│       ├── contract_types.json         72 tipos SEPE codes, RDLs
│       ├── seguridad_social_rules.json reglas autónomos, régimen general
│       └── sistema_red_procedures.json flujos Sistema RED/CEPE
│
│  ── Docs ──────────────────────────────────────────────
├── docs/
│   ├── ARQUITECTURA.md
│   ├── OPERACION_Y_LIMITES.md
│   └── (MCP_INTEGRATION.md — pendiente)
│
│  ── CI/CD ─────────────────────────────────────────────
└── .github/workflows/
    ├── ci.yml                      ruff + pytest (Py 3.11/3.12) + npm build + docker build
    └── deploy.yml                  SSH a 209.74.72.83 + docker service update
```

---

## Cadena de dependencias (nivel lógico)

```
data/convenio_*.json                 ─┐
data/ss_config.json                   ├─▶ engine.py ─▶ ss_calculator.py
data/knowledge_base/*.json           ─┘                │
                                                       ▼
                                                 irpf_estimator.py
                                                       │
chat_parser.py ◀───────── vgrag_search.py              │
    │                         (RAG opcional)           │
    │                                                  ▼
    │                                            nomina_pdf.py
    ▼
laboral_agent.py (CodeAct)
    │
    ▼
mcp_server.py (schema)  ◀── MCP host (Claude, Cursor, …)
    │
    ▼
app.py  (Flask v2, expone agente)   ◀─── static/ (panel viejo)
laboral-backend/app/main.py  (v3)   ◀─── laboral-frontend/ (React)
    │
    ▼
database.py (SQLite, /data/laboral.db)
```

---

## Reglas críticas (leer antes de tocar código fiscal)

1. **Tasas SS 2026** están en `data/ss_config.json` con referencia a Orden ISM/31/2026
   (BOE‑A‑2026‑1921) y RDL 3/2026 (BOE‑A‑2026‑2548). Verificar anualmente con
   `rates_verifier.py`. **No hardcodear tasas fuera de `ss_config.json`.**
2. **Convenios** están en `data/convenio_*.json` y provienen del BOE. No inventar
   categorías ni importes; si el convenio real no los tiene, la respuesta debe ser
   *"faltan datos"*, no un número inventado.
3. **IRPF autonómico**: el estimador soporta Madrid, Cataluña, Andalucía y Valencia.
   Cada una tiene escalas diferentes. Añadir comunidades nuevas implica tocar
   `irpf_estimator.py` y documentar la fuente (BOCM, DOGC, BOJA, DOGV).
4. **Pre‑nómina ≠ nómina**. La salida es orientativa. No sustituye validación
   profesional final. Así debe figurar en todo PDF/HTML generado.
5. **El LLM no calcula**. Si detectas un PR donde el agente devuelve una cifra fiscal
   sin pasar por una tool del motor, es un bug de seguridad fiscal. Rechazar.
6. **Audit trail**: toda ejecución del agente (input del usuario, código sandboxed que
   el LLM generó, output de cada tool, respuesta final, modelo, tokens, coste
   estimado) debe persistirse. (Pendiente: tabla `agent_runs`, ver hoja de ruta.)
7. **Tests son obligatorios**. CI los ejecuta en Python 3.11 y 3.12. No se mergea con
   tests rojos.
8. **Ningún número fiscal en código Python fuera de `data/`**. Si ves `4.70`,
   `1424.50`, `5101.20` hardcodeado, sácalos a `ss_config.json`.

---

## MCP — estado actual y plan

`mcp_server.py` define **4 tools** con schema JSON Schema:

| Tool | Qué hace |
|---|---|
| `laboral_calcular_nomina` | Desglose bruto → SS trabajador (aplica topes de cotización) |
| `laboral_consultar_convenio` | Tablas salariales del convenio cargado |
| `laboral_calcular_ss` | Cuotas SS empresa + trabajador por tipo de contrato |
| `laboral_estimar_irpf` | Retención IRPF por situación familiar y autonomía |

Y expone 3 resources: `laboral://nominas`, `laboral://convenios`,
`laboral://seguridad-social`.

**Estado:** el schema está definido y `handle_mcp_request(method, params)` implementa
`tools/list`, `tools/call`, `resources/list`. Pero **ningún archivo lo sirve** como
servidor MCP real — no hay stdio binding ni SSE ni HTTP endpoint, y el SDK oficial
`mcp` (Anthropic) no está en las dependencias. Hasta que se añada, **ningún host MCP
puede conectarse al sistema**.

**Plan (PR #TBD `feat(mcp): serve tools as real MCP server`):**
1. Añadir `mcp>=1.0` a `requirements.txt` y `pyproject.toml`.
2. Crear `mcp_server_main.py` con `mcp.server.stdio` + `mcp.server.sse`.
3. Entry point `[project.scripts] pgk-laboral-mcp = "mcp_server_main:run"`.
4. `docs/MCP_INTEGRATION.md` con el snippet `claude_desktop_config.json` listo para
   pegar y probar.

Cuando esto esté hecho, cualquier usuario de Claude Desktop podrá llamar a las tools
laborales españolas directamente desde su chat.

---

## Cómo añadir funcionalidad

### Nuevo convenio colectivo
1. Importar del BOE con `boe_importer.py` o crear JSON manual en
   `data/convenio_NOMBRE.json`.
2. Respetar el schema de los existentes (ver `HANDOFF.md §Cómo añadir un nuevo convenio`).
3. Registrar en `client_manager.py` si aplica a un cliente concreto.
4. Añadir un test en `test_engine.py` que ejercite al menos una categoría.
5. Si el convenio cambia las pagas (2 vs 3 extras), verificar que `engine.py` lo
   detecta automáticamente vía `resumen_operativo.pagas_extras`.

### Nueva comunidad autónoma (IRPF)
1. Añadir escalas en `irpf_estimator.py` (estatal + autonómica).
2. Documentar fuente oficial (link al boletín autonómico).
3. Añadir test con un caso conocido (nómina real de esa región).

### Nuevo cálculo
1. Implementar en `engine.py` o crear módulo nuevo (si es cross-cutting, ej:
   `finiquito_calculator.py`).
2. Exponer en `app.py` como endpoint Flask y en `laboral-backend/app/routes/` como
   endpoint FastAPI.
3. Añadir tests unitarios y, si es numérico, un test de regresión con una nómina real.
4. Si el cálculo lo puede llamar un agente IA, **añadirlo también como tool MCP** en
   `mcp_server.py` con su schema JSON Schema.

### Nueva tool MCP
1. Añadir definición al array `MCP_TOOLS` en `mcp_server.py`.
2. Implementar la función privada `_nombre_tool(arguments)` que valida entrada y
   llama al motor determinista.
3. Despachar en `_call_tool(name, arguments)`.
4. Añadir test en `test_mcp_server.py` (pendiente crear).
5. Documentar en `docs/MCP_INTEGRATION.md` (pendiente crear).

---

## Comandos

### Backend v2 (Flask, activo en capa IA)
```bash
pip install -r requirements.txt -r requirements-dev.txt
python app.py --debug                 # http://127.0.0.1:8765
```

### Backend v3 (FastAPI, el que corre en producción)
```bash
cd laboral-backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

### Frontend (React)
```bash
cd laboral-frontend
npm ci
npm run dev                           # http://127.0.0.1:5173
npm run build                         # genera dist/ para producción
```

### Tests
```bash
# v2
python -m pytest test_engine.py test_chat_parser.py test_client_manager.py test_boe_importer.py -v

# v3
cd laboral-backend && pytest -v

# Offline solamente (sin BOE ni Perplexity ni LLM):
python -m pytest -v -m "not integration"

# Con integración (necesita keys):
PERPLEXITY_API_KEY=pplx-... GEMINI_API_KEY=... python -m pytest -v
```

### Lint
```bash
ruff check .
ruff format --check .
# Dentro de laboral-backend:
cd laboral-backend && ruff check app/ tests/
```

### MCP server (cuando el PR esté mergeado)
```bash
pgk-laboral-mcp                        # stdio, para Claude Desktop
pgk-laboral-mcp --transport sse --port 8001   # SSE, para hosts remotos
```

---

## Variables de entorno

| Variable | Uso | Backend |
|---|---|---|
| `FLASK_SECRET_KEY` | firmar sesión Flask | v2 |
| `SECRET_KEY` | firmar JWT | v3 |
| `DEFAULT_ADMIN_PASSWORD` | password del usuario seed `pgk` (obligatoria en prod) | ambos |
| `DATABASE_URL` | conexión DB (default SQLite) | v3 |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | modelo LLM principal | agente |
| `ANTHROPIC_API_KEY` | LLM alternativo | agente |
| `ANTHROPIC_BASE_URL` | proxy (p. ej. z.ai) | agente |
| `ZAI_API_KEY` | RAG semántico `vgrag_search.py` | RAG |
| `LABORAL_VECTOR_GRAPH_RAG` | feature flag RAG (default `false`) | RAG |
| `PERPLEXITY_API_KEY` | verificación vigencia convenios / tasas | verificación |
| `BOE_API_BASE_URL` | BOE sumarios (default `https://boe.es/datosabiertos/api`) | importador |
| `CORS_ORIGINS` | origins permitidos en v3 | v3 |
| `ENVIRONMENT` | `development` / `production` | v3 |

---

## Known pitfalls

- **WeasyPrint** necesita `libpango`, `libgdk-pixbuf`, `libcairo2` del sistema para
  generar PDF. Ya se instalan en el Dockerfile. Fuera de Docker, `apt install
  libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0 libcairo2`.
- **SMI anual** cambia cada enero. Actualizar `data/ss_config.json` y re-ejecutar
  `rates_verifier.py`.
- **Perplexity API** es **advisory**; si no hay `PERPLEXITY_API_KEY`, las
  verificaciones devuelven `unknown` y el resto del sistema sigue funcionando.
- **Sandbox del agente** (`laboral_agent.py` `_validate_code_safety`): bloquea
  `__class__`, `__import__`, dunders. No añadir builtins a `_SAFE_BUILTINS` sin
  revisar si abren un sandbox escape.
- **Dos apps en un repo:** si tocas `engine.py`, toca también
  `laboral-backend/app/services/engine.py` (divergencia silenciosa). Mismo para
  `ss_calculator.py`, `chat_parser.py`, `irpf_estimator.py`, etc.
- **`/api/agent/*` sólo existe en v2**. v3 FastAPI no cablea el agente aún.
- **`mcp_server.py` no se sirve como MCP aún**. Ver §MCP.
- **Credenciales seed** (`pgk2025`, `mpc2025`) son valores por defecto para dev.
  En producción, `DEFAULT_ADMIN_PASSWORD` debe ser obligatoria (pendiente forzarlo
  en `config.py`).

---

## Hoja de ruta (actualizada, orden por ROI)

1. ~~Documentación IA‑first~~ ← **este PR**.
2. Servir MCP real (`feat(mcp): serve tools as MCP server`) — desbloquea Claude
   Desktop, Cursor y otros hosts.
3. Audit trail del agente (tabla `agent_runs`, endpoint `/api/agent/runs/<id>`).
4. Cron mensual `verify-rates-monthly.yml` que abre PR automático si `rates_verifier`
   detecta drift.
5. Pipeline de indexación RAG (`scripts/index_convenios.py` + `lifespan`) y eval
   dataset (`evals/laboral_golden_set.jsonl`) en CI.
6. Cablear agente + MCP en v3 FastAPI (`routes/agent.py`, `routes/mcp.py`).
7. Consolidar v2/v3: borrar el backend que pierda.
8. Seguridad: rotar creds seed, forzar `DEFAULT_ADMIN_PASSWORD`, migrar deploy a SSH
   key + usuario no‑root.
9. (Opcional) Publicar como paquete PyPI para que otros despachos laborales
   conecten sus Claude Desktop.
