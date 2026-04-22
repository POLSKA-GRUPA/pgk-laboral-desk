# PGK Laboral Desk — Documento de Handoff

**Revisado**: 22 de abril de 2026
**Repo**: `POLSKA-GRUPA/pgk-laboral-desk` (privado)
**Producción**: https://laboral.polskagrupakonsultingowa.com
**Servidor**: 209.74.72.83 (Ubuntu 24.04, Docker Swarm + Traefik + Dokploy)

---

## Qué es esto (TL;DR)

**Application server para agentes de IA en dominio laboral español.** Expone
cálculo laboral determinista (SS 2026, IRPF estatal + autonómico, convenios
BOE, despido/finiquito) como tools que un LLM puede invocar vía **MCP** o
**HTTP/SSE** sin alucinar números fiscales.

- El LLM razona y orquesta. El motor determinista calcula. Ningún número
  fiscal sale del LLM.
- Uso interno de PGK Asesoría Laboral hoy. Potencial comercial como paquete
  para otros despachos laborales españoles.

Ver `README.md`, `AGENTS.md` y `docs/ARQUITECTURA.md` para detalle.

---

## Estado actual (22 abril 2026)

### Lo que funciona

- **Motor determinista completo** — engine, SS 2026, IRPF estatal + 4
  autonómicas, despido, finiquito, pre‑nómina PDF/HTML.
- **Agente CodeAct** (Gemini / Anthropic) expuesto en **v2 Flask** en
  `/api/agent/{status,chat,stream}`.
- **Multi‑convenio** — 2 convenios cargados (acuáticas estatal 2025‑2027,
  oficinas y despachos Alicante 2024‑2026), el engine auto-detecta pagas
  14/15 desde `resumen_operativo.pagas_extras`.
- **Gestión de plantilla** — CRUD empleados, alertas automáticas, histórico
  de consultas.
- **Auditoría de nóminas** (v3) — `nomina_audit_engine.py` + endpoint
  `POST /api/audit/nomina` con parser de PDF de nómina.
- **SEPE / Sistema RED** (v3) — generador XML para alta de trabajadores.
- **Finiquito / RETA** (v3) — calculadoras dedicadas.
- **Verificación BOE** — `convenio_verifier.py` + `rates_verifier.py`
  advisory vía Perplexity.
- **CI/CD** — ruff + pytest (Py 3.11 y 3.12) + build frontend React +
  build Docker + deploy automático SSH tras merge a `main`.
- **Tests** — 56+ tests pasando offline, integración BOE y Perplexity con
  flag.

### Lo que está a medias

- **Dos backends conviven en `main`**:
  - **v2 Flask (`app.py`)** — activo en capa IA (único que expone agente
    y MCP tools schema).
  - **v3 FastAPI (`laboral-backend/app/main.py`)** — lo que corre en
    producción vía Docker, pero **NO cablea el agente ni el MCP todavía**.
- **MCP server no se sirve aún**. `mcp_server.py` define el schema pero no
  hay binding stdio/SSE. PR en curso.
- **Dos frontends conviven**:
  - `static/` (vanilla, v2) — sirve el Flask.
  - `laboral-frontend/` (React 18 + TypeScript + AntD 5 + Vite 6, v3) — se
    construye a `laboral-backend/static/` en el Dockerfile.
- **Audit trail del agente** (tabla `agent_runs`) aún no persiste en BBDD.
- **Eval dataset del agente** no existe.
- **Pipeline de indexación RAG** (`vgrag_search.index_articulo_convenio`)
  no se llama desde ningún sitio.

### Problemas conocidos del frontend

- El panel vanilla (`static/panel.html`) no tiene UI para gestionar clientes.
- No hay selector de convenio — siempre carga el de acuáticas por defecto.
- No hay pantalla de verificación de convenio.
- El formulario tiene hardcodeado "14 pagas" en los radio buttons.
- `app.js` no envía `region` ni `contract_days` al backend (el backend sí
  los soporta).
- El frontend nuevo React cubre los casos pero la paridad con v2 está a
  medias.

---

## Convenios cargados

1. **Acuáticas** — `data/convenio_acuaticas_2025_2027.json`
   - Ámbito: estatal
   - Pagas: 14 (12 + 2 extras)
   - Categorías: 24
2. **Oficinas y Despachos Alicante** — `data/convenio_oficinas_despachos_alicante_2024_2026.json`
   - Ámbito: provincial (Alicante)
   - Pagas: 15 (12 + 3 extras: junio, diciembre, marzo)
   - Categorías: 22

## API endpoints (snapshot)

### v2 Flask (`app.py`) — activo en capa IA
- `POST /api/auth/login` · `POST /api/auth/logout` · `GET /api/auth/me`
- `GET /api/categories` · `GET /api/contract-types` · `GET /api/regions`
- `POST /api/simulate` · `GET /api/history` · `GET /api/convenio`
- `POST /api/chat` · `POST /api/chat/reset`
- `GET /api/agent/status` · `POST /api/agent/chat` · `POST /api/agent/stream`
- `GET /api/tipos-despido` · `POST /api/despido`
- `GET /api/employees` · `POST /api/employees` · `PUT /api/employees/<id>`
- `POST /api/employees/<id>/despido` · `GET /api/employees/<id>/nomina`
- `GET /api/alerts` · `POST /api/alerts` · `POST /api/alerts/<id>/dismiss`
- `GET /api/health`

### v3 FastAPI (`laboral-backend/app/main.py`) — producción
Routers: `health`, `auth`, `employees`, `chat`, `consultations`, `convenios`,
`dismissal`, `employee_dismissal`, `payroll`, `reference`, `sepe`,
`simulation`, `audit`, `alerts`.

**Missing** en v3: `agent`, `mcp`. Planeados.

---

## Cómo añadir un nuevo convenio

1. Crear `data/convenio_<nombre>_<vigencia>.json` siguiendo el schema de los
   existentes.
2. Campos obligatorios:
   - `convenio.nombre`, `convenio.codigo`, `convenio.vigencia_desde_ano`,
     `convenio.vigencia_hasta_ano`
   - `resumen_operativo.pagas_extras` (2 si junio+diciembre, 3 si también
     marzo)
   - `salarios_por_categoria[]` con `category`, `annual_eur` y opcionalmente
     `monthly_XX_payments_eur` donde `XX` es `14` o `15`
   - `sections[]` con items `{label, detail, source}`
3. El engine lo detecta automáticamente al listar convenios.
4. Registrar en `client_manager.py` si se asocia a un cliente concreto.
5. Añadir test en `test_engine.py` con al menos una categoría real.

---

## Deploy

### Infraestructura
- **Servidor**: 209.74.72.83 (root por ahora — pendiente migrar a usuario
  `deployer` no‑root con SSH key; ver hoja de ruta §Seguridad).
- **Stack**: Docker Swarm + Traefik (gestionado por Dokploy).
- **Servicio**: `laboral-pgk` en red `dokploy-network`.
- **Volumen**: `laboral-pgk-data` montado en `/data` (SQLite persistente).
- **Traefik config**: `/etc/dokploy/traefik/dynamic/laboral-pgk.yml`.
- **Código en servidor**: `/opt/laboral-pgk/` (git clone del repo).
- **Dominio**: `laboral.polskagrupakonsultingowa.com` (SSL Let's Encrypt).

### Imagen Docker (`Dockerfile`)
Multi-stage:
1. `frontend-builder` (Node 20) — `npm ci` + `npm run build` de
   `laboral-frontend/` → `/build/dist`.
2. `backend` (Python 3.12-slim) — instala deps de `laboral-backend/`,
   copia `laboral-backend/` → `/app`, copia `data/` → `/app/data`, copia
   `/build/dist` → `/app/static`. Corre `uvicorn app.main:app --host 0.0.0.0
   --port 8000` como usuario `appuser` no‑root.

> **Nota:** el Flask v2 de la raíz **NO se incluye en la imagen**. Para
> exponer el agente en producción hoy hay que cablearlo en v3 (pendiente).

### CI/CD
- `.github/workflows/ci.yml` — en push a `main` y PR a `main`:
  1. `lint-backend` — ruff sobre `laboral-backend/`.
  2. `test-backend` — pytest `laboral-backend/tests/` en Python 3.11 y 3.12.
  3. `build-frontend` — `npm ci && npm run build` en `laboral-frontend/`.
  4. `docker-build` — build de imagen (no la publica aún; pendiente GHCR).
- `.github/workflows/deploy.yml` — se dispara al terminar `ci` con éxito:
  1. SSH a `209.74.72.83`.
  2. `cd /opt/laboral-pgk && git pull origin main`.
  3. `docker build -t laboral-pgk:latest .`.
  4. `docker service update --image laboral-pgk:latest --force laboral-pgk`.

Secrets configurados en GitHub: `SERVER_HOST`, `SERVER_PASSWORD`
(**pendiente** migrar a `SSH_KEY` y usuario `deployer`).

### Deploy manual
```bash
ssh root@209.74.72.83
cd /opt/laboral-pgk
git pull origin main
docker build -t laboral-pgk:latest .
docker service update --image laboral-pgk:latest --force laboral-pgk
```

### Logs
```bash
docker service logs -f laboral-pgk
```

---

## Variables de entorno (producción)

| Variable | Uso | Obligatoria |
|---|---|---|
| `SECRET_KEY` | firmar JWT (v3) | **sí** (en prod) |
| `DEFAULT_ADMIN_PASSWORD` | password del seed `pgk` | **sí** (en prod) |
| `DATABASE_URL` | `sqlite:////data/laboral.db` en prod | sí |
| `ENVIRONMENT` | `production` | sí |
| `CORS_ORIGINS` | `https://laboral.polskagrupakonsultingowa.com` | sí |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | agente CodeAct (opcional pero recomendado) | no |
| `ANTHROPIC_API_KEY` | agente alternativo | no |
| `ANTHROPIC_BASE_URL` | proxy (p. ej. z.ai) | no |
| `ZAI_API_KEY` | RAG semántico `vgrag_search.py` | no |
| `LABORAL_VECTOR_GRAPH_RAG` | feature flag RAG | no (default `false`) |
| `PERPLEXITY_API_KEY` | verificación BOE advisory | no |
| `BOE_API_BASE_URL` | default `https://boe.es/datosabiertos/api` | no |

En v2 Flask: `FLASK_SECRET_KEY` en lugar de `SECRET_KEY`.

## Usuarios de prueba

> **Atención**: estos valores por defecto son sólo para dev. En producción,
> `DEFAULT_ADMIN_PASSWORD` debe ser obligatoria y los creds por defecto
> rotados (ver hoja de ruta §Seguridad).

- **Admin PGK**: `pgk` / `pgk2025` (role: admin)
- **Cliente MPC**: `mpc` / `mpc2025` (role: client)

Creados automáticamente por `database.py:init_db()` si no existen.

---

## Tests

```bash
# v2 — motor + parser + client_manager + boe_importer
python -m pytest test_engine.py test_chat_parser.py test_client_manager.py test_boe_importer.py -v

# v3 — calculators, nóminas reales, SEPE, auth, simulation
cd laboral-backend && pytest -v

# Todos offline
python -m pytest -v -m "not integration"

# Con integración (requiere red + keys)
PERPLEXITY_API_KEY=pplx-... GEMINI_API_KEY=... python -m pytest -v
```

---

## Hoja de ruta (prioridad ROI)

1. **Servir MCP real** (`feat(mcp): serve tools as real MCP server`) — SDK
   oficial `mcp>=1.0`, stdio + SSE, `docs/MCP_INTEGRATION.md` con snippet
   `claude_desktop_config.json`. Desbloquea Claude Desktop, Cursor y resto
   de hosts IA.
2. **Audit trail del agente** — tabla `agent_runs`, endpoint
   `/api/agent/runs/<id>` para reabrir cualquier conversación. Crítico
   para compliance fiscal.
3. **Cron mensual** `verify-rates-monthly.yml` — invoca `rates_verifier.py`
   + `convenio_verifier.py` y abre PR automático si detecta drift de
   tasas SS/IRPF/SMI respecto al BOE.
4. **Pipeline de indexación RAG** — `scripts/index_convenios.py` que carga
   `data/convenio_*.json` + `knowledge_base/*.json` y llama
   `vgrag_search.index_articulo_convenio` masivamente. Ejecutar en
   lifespan/startup.
5. **Eval dataset del agente** — `evals/laboral_golden_set.jsonl` con
   30‑50 consultas típicas + `evals/run_eval.py` corriendo varios modelos
   (Gemini, Claude, local). Job CI que corre eval en PR con tag `ai-change`.
6. **Cablear agente + MCP en v3 FastAPI** — crear `routes/agent.py` y
   `routes/mcp.py` que repliquen la funcionalidad del Flask v2.
7. **Consolidar v2 / v3** — cuando v3 cubra toda la capa IA, borrar v2
   Flask (raíz) + `static/` + tests v2. Elimina ~8.5k LOC duplicadas.
8. **Seguridad**:
   - rotar creds seed `pgk2025`/`mpc2025`,
   - forzar `DEFAULT_ADMIN_PASSWORD` y `SECRET_KEY` en
     `ENVIRONMENT=production` (fail fast),
   - migrar deploy de `SERVER_PASSWORD` a `SSH_KEY` + usuario `deployer`
     no‑root con sudo acotado.
9. **Operacional** — Gunicorn/Uvicorn con workers configurables, GHCR para
   publicar imagen desde CI, `concurrency: deploy-prod` en workflow,
   preparar Alembic para migraciones.
10. **(Opcional)** Publicar paquete PyPI `pgk-laboral-mcp` con licencia
    open-core + pro para que otros despachos laborales españoles conecten
    su Claude Desktop al motor.

## Bugs resueltos recientemente

- Audit bugs (PR #10, devin/1776261099) — filter None values, path-safe
  pattern en `UserUpdate.convenio_id`, parsing correcto de nóminas reales.
- Nomina audit engine D1-D7 con parser PDF + endpoints API.
- Parse correcto de "Total coste" cuando está en línea separada del label.
