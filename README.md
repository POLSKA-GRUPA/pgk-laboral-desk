# PGK Laboral Desk

> **Application server para agentes de IA en dominio laboral español.**
> Expone cálculo laboral determinista (Seguridad Social 2026, IRPF estatal +
> autonómico, convenios colectivos del BOE, despido/finiquito) como
> herramientas que un LLM puede invocar **sin alucinar números fiscales**.

Interno de PGK Asesoría Laboral. Producción: https://laboral.polskagrupakonsultingowa.com

---

## Qué es (y qué no)

- **Es** un servidor de tools + datos trazables al BOE, que cualquier host de IA
  puede consumir vía **MCP** (Claude Desktop, Cursor, Windsurf, ChatGPT Desktop…)
  o vía **HTTP/SSE** (PGK‑Despacho‑Desktop, agentes propios).
- **Es** un motor determinista que, dado un convenio colectivo y una consulta,
  devuelve una lectura estructurada del caso y una pre‑nómina orientativa.
- **No es** una nómina profesional. La salida es auxiliar a la validación
  humana/profesional final.
- **No es** "una app laboral con un chatbot encima". El producto son las tools
  y los datos. La UI web es un consumidor más, no el centro.

---

## Para agentes de IA (Claude / Cursor / Gemini / Devin)

Antes de modificar código, lee **[AGENTS.md](AGENTS.md)**. Resumen rápido:

- El LLM razona. El motor calcula. **Ningún número fiscal sale del LLM.**
- El repositorio está a medio migrar: backend **v2 Flask** (activo en capa IA)
  y **v3 FastAPI** (el que corre en producción) coexisten en `main`. Tócalos a
  la vez si el cambio es de dominio, o declara cuál es canónico en el PR.
- Sigue el **protocolo Engram** (`mem_context` al iniciar, `mem_save` tras cada
  acción significativa, `mem_session_summary` al cerrar).

---

## Arquitectura de alto nivel

```
HOSTS IA  ─────────────►  MCP (stdio/SSE)
                          │
                          ▼
  ┌───────────────────────────────────────────────┐
  │  pgk-laboral-desk                             │
  │                                               │
  │  mcp_server.py       → tools schema           │
  │  laboral_agent.py    → CodeAct (LLM+sandbox)  │
  │  chat_parser.py      → fallback determinista  │
  │  vgrag_search.py     → RAG (opcional)         │
  │                                               │
  │  engine · ss_calculator · irpf_estimator      │
  │  nomina_pdf · client_manager · database       │
  │                                               │
  │  data/convenio_*.json      (BOE)              │
  │  data/ss_config.json       (Orden ISM/31/2026)│
  │  data/knowledge_base/*.json                   │
  └───────────────────────────────────────────────┘

UI humana: static/ (vanilla, v2) · laboral-frontend/ (React, v3)
```

Diagramas y detalle: [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).
Alcance operativo y límites jurídicos: [docs/OPERACION_Y_LIMITES.md](docs/OPERACION_Y_LIMITES.md).
Estado del despliegue, bugs conocidos y roadmap: [HANDOFF.md](HANDOFF.md).

---

## Alcance actual (qué cubre el motor)

- Interpreta consultas en lenguaje natural (agente CodeAct con LLM, o parser
  determinista de reglas/keywords como fallback).
- Detecta categoría profesional, jornada, pagas extras, antigüedad, modalidad
  contractual y región IRPF.
- Calcula **Seguridad Social empresa + trabajador** con tasas 2026 (11 grupos
  de cotización, recargo de contratos ≤30 días, topes max/min).
- Estima **IRPF** con escala estatal + 4 escalas autonómicas (Madrid, Cataluña,
  Andalucía, Valencia).
- Calcula **coste de despido/extinción** y emite consejo estratégico (objetivo,
  improcedente, disciplinario, mutuo acuerdo, ERE, fin de temporal).
- Calcula **finiquito** (vacaciones pendientes, pagas extras prorrateadas,
  indemnización cuando aplique).
- Genera **pre‑nómina orientativa** en PDF/HTML (WeasyPrint).
- **Audita** nóminas ya emitidas (v3 sólo, `nomina_audit_engine.py`).
- Genera **XML SEPE/Sistema RED** para alta de trabajadores (v3 sólo).
- Gestión de **plantilla** (empleados, alertas, histórico).
- **Multi‑convenio**: acuáticas estatal 2025‑2027 (14 pagas, 24 categorías),
  oficinas y despachos Alicante 2024‑2026 (15 pagas, 22 categorías).

## Lo que NO cubre (por diseño)

- Emisión de nómina definitiva con cotización real firmada.
- Contratos internacionales, permisos de trabajo, fiscalidad transfronteriza.
- Todo lo que exija decisión jurídica cualificada.

---

## Requisitos

- Python ≥ 3.11
- Node ≥ 20 (para `laboral-frontend/`)
- Dependencias de sistema: `libpango`, `libpangoft2-1.0-0`, `libgdk-pixbuf2.0-0`,
  `libcairo2` (para WeasyPrint)
- Opcionales: `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` (agente), `ZAI_API_KEY`
  (RAG), `PERPLEXITY_API_KEY` (verificación BOE)

---

## Desarrollo

### Backend v2 (Flask, activo en capa IA)

```bash
pip install -r requirements.txt -r requirements-dev.txt
python app.py --debug        # http://127.0.0.1:8765
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
npm run dev                  # http://127.0.0.1:5173
```

### Tests

```bash
# v2
python -m pytest test_engine.py test_chat_parser.py test_client_manager.py test_boe_importer.py -v

# v3
cd laboral-backend && pytest -v
```

### Lint

```bash
ruff check .
ruff format --check .
```

### MCP server

> Estado: **en desarrollo.** `mcp_server.py` define las 4 tools
> (`laboral_calcular_nomina`, `laboral_consultar_convenio`, `laboral_calcular_ss`,
> `laboral_estimar_irpf`) pero aún no hay binding stdio/SSE activo. El PR
> `feat(mcp): serve tools as real MCP server` desbloquea Claude Desktop y
> resto de hosts. Ver `AGENTS.md §MCP` y `docs/MCP_INTEGRATION.md` (pendiente).

---

## API HTTP (v2 Flask)

### Health

```http
GET /api/health
```

```json
{
  "ok": true,
  "version": "0.2.0",
  "checks": {
    "convenios": {"ok": true, "count": 2},
    "database": {"ok": true}
  }
}
```

### Simulación de coste

```http
POST /api/simulate
Content-Type: application/json

{
  "category": "Nivel B.",
  "contract_type": "indefinido",
  "weekly_hours": 40,
  "region": "madrid"
}
```

### Chat conversacional (determinista + agente si hay LLM configurado)

```http
POST /api/chat
Content-Type: application/json

{"message": "Quiero contratar un socorrista nivel B fijo-discontinuo a 40 horas para verano."}
```

### Agente CodeAct

```http
GET  /api/agent/status
POST /api/agent/chat            # request/response
POST /api/agent/stream          # streaming (SSE)
```

### Despido

```http
POST /api/despido
Content-Type: application/json

{
  "tipo_despido": "improcedente",
  "fecha_inicio": "2023-01-15",
  "salario_bruto_mensual": 1500
}
```

---

## Datos y trazabilidad

- **Convenios** — `data/convenio_*.json`, derivados del BOE.
- **Tasas SS 2026** — `data/ss_config.json` (Orden ISM/31/2026 · BOE‑A‑2026‑1921
  y RDL 3/2026 · BOE‑A‑2026‑2548), verificadas con `rates_verifier.py` +
  Perplexity.
- **Knowledge base** — `data/knowledge_base/contract_types.json` (72 tipos de
  contrato con códigos SEPE y base legal: RDL 32/2021, RDL 1/2023, ET RDL
  2/2015), `seguridad_social_rules.json`, `sistema_red_procedures.json`.
- **Principio:** si el dato no existe en `data/`, la respuesta es *"faltan
  datos"*, **nunca** un número inventado por el LLM.

---

## Criterio jurídico‑operativo

Esta herramienta **no sustituye la validación profesional final**. La salida
debe leerse como:

- lectura preliminar del caso,
- pre‑dictamen laboral interno,
- pre‑nómina orientativa.

La decisión final sobre contrato, nómina, extranjería, Seguridad Social y
fiscalidad se cierra en expediente profesional separado.

---

## Hoja de ruta

La lista completa, priorizada por ROI, está en [AGENTS.md §Hoja de ruta](AGENTS.md#hoja-de-ruta-actualizada-orden-por-roi).
Resumen:

1. **Servir MCP real** (stdio + SSE) — desbloquea Claude Desktop / Cursor.
2. **Audit trail del agente** — tabla `agent_runs`, endpoint para reabrir
   conversaciones (exigencia de compliance fiscal).
3. **Cron mensual** de verificación de tasas SS/IRPF/SMI que abre PR automático
   si detecta drift respecto al BOE.
4. **Pipeline RAG** (`scripts/index_convenios.py` + lifespan) + **eval
   dataset** (`evals/laboral_golden_set.jsonl`) en CI.
5. **Cablear agente + MCP en v3** y consolidar v2/v3.
6. **Seguridad**: rotar creds seed, forzar `DEFAULT_ADMIN_PASSWORD`, SSH key
   + usuario no‑root para deploy.
7. **(Opcional)** Paquete PyPI `pgk-laboral-mcp` para que otros despachos
   laborales conecten sus Claude Desktop.
