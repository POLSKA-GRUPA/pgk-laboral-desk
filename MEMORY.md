# MEMORY.md — Memoria Persistente PGK Laboral Desk

> *Los agentes leen este archivo al arrancar para saber qué ha pasado antes.*
> *Actualizarlo al final de cada sesión larga o cuando haya decisiones importantes.*
> **NOTA:** Además de este archivo, usar **Engram** (`engram mcp`) para memoria
> persistente estructurada — ver `AGENTS.md §PROTOCOLO ENGRAM`.

---

## Resumen Ejecutivo

**Proyecto:** PGK Laboral Desk — **application server para agentes de IA en
dominio laboral español**. Motor determinista (SS 2026, IRPF estatal +
autonómico, convenios BOE, despido/finiquito) expuesto como tools MCP y
HTTP/SSE, consumido por Claude Desktop / Cursor / agentes PGK.

**Tesis:** el LLM razona y orquesta; el motor calcula. Ningún número fiscal
sale del LLM. Ver `README.md` y `AGENTS.md` para detalle.

---

## Decisiones Importantes

- [2026-04-14] **Engram configurado** como MCP para memoria persistente entre
  sesiones (Go + SQLite + FTS5).
- [2026-04-22] **Thesis IA-first declarada** en `AGENTS.md`, `README.md`,
  `docs/ARQUITECTURA.md`, `docs/OPERACION_Y_LIMITES.md` y este archivo. El
  repo deja atrás el mensaje *"motor determinista sin IA externa"* y asume su
  realidad: server MCP + agente CodeAct + motor determinista + RAG opcional.
- [2026-04-22] **Estado de los dos backends documentado**: v2 Flask (activo
  en capa IA) y v3 FastAPI (el que corre en producción, regresión en IA).
  Consolidación pospuesta hasta que v3 cablee agente + MCP.

---

## Lecciones Aprendidas

- Las "notas mentales" no sobreviven entre sesiones — escribir en archivos o
  usar Engram.
- **El contexto de LLM es limitado** — cargar sólo lo necesario.
- **Docs desactualizadas son un bug**: cualquier agente futuro que lea
  `README.md` o `AGENTS.md` asume que ese es el estado real. Si mentimos, el
  agente trabaja sobre código muerto.
- **La duplicación silenciosa mata**: `engine.py` en raíz y
  `laboral-backend/app/services/engine.py` divergen si sólo se toca uno. Si
  cambias lógica de dominio en un lado, tocarla en el otro **o** documentar
  en el PR que ese lado es canónico.
- **Ningún número fiscal en código Python fuera de `data/`.** Si ves
  `4.70`, `1424.50`, `5101.20` hardcodeados, sácalos a `ss_config.json`.

---

## Bucles Abiertos

- [ ] Servir MCP real (PR en curso) — SDK oficial `mcp>=1.0`, stdio + SSE,
  `docs/MCP_INTEGRATION.md` con snippet `claude_desktop_config.json`.
- [ ] Audit trail del agente — tabla `agent_runs`, endpoint
  `/api/agent/runs/<id>`.
- [ ] Cron mensual `verify-rates-monthly.yml` que abre PR automático al
  detectar drift en tasas SS/IRPF/SMI.
- [ ] Pipeline de indexación RAG (`scripts/index_convenios.py` en lifespan).
- [ ] Eval dataset `evals/laboral_golden_set.jsonl` + `evals/run_eval.py` en CI.
- [ ] Cablear agente + MCP en v3 FastAPI (`routes/agent.py`, `routes/mcp.py`).
- [ ] Consolidar v2/v3 (borrar el perdedor) — condición: v3 debe exponer
  toda la capa IA antes.
- [ ] Seguridad: rotar creds seed, forzar `DEFAULT_ADMIN_PASSWORD` y
  `SECRET_KEY`, migrar deploy a SSH key + usuario `deployer` no‑root.

---

## Última Sesión

**Fecha:** 2026-04-22
**Qué se hizo:**
- Auditoría v2 IA-first del repo (ver conversación con Devin).
- Reescritura completa de `README.md`, `AGENTS.md`, `HANDOFF.md`,
  `docs/ARQUITECTURA.md`, `docs/OPERACION_Y_LIMITES.md` y este archivo con
  la tesis real del proyecto (PR#1 docs IA-first).

**Qué quedó pendiente:**
- PR#4 `feat(mcp): serve tools as real MCP server (stdio + SSE)` — arranca
  inmediatamente después.
- Resto de bucles abiertos (ver arriba).
