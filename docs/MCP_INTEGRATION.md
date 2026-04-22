# MCP Integration

`pgk-laboral-desk` se sirve como un **servidor MCP** (Model Context Protocol).
Permite que hosts como **Claude Desktop**, **Cursor**, **Windsurf** o **ChatGPT
Desktop** consuman sus herramientas laborales directamente, sin tener que
construir un cliente HTTP a medida.

El servidor expone:

| Tool                          | Devuelve                                                          |
|-------------------------------|-------------------------------------------------------------------|
| `laboral_calcular_nomina`     | Bruto mensual, deducciones SS, referencia legal                  |
| `laboral_consultar_convenio`  | Tablas salariales de convenio colectivo cargado                  |
| `laboral_calcular_ss`         | Cuotas empresa con topes aplicados (Orden ISM/31/2026)            |
| `laboral_estimar_irpf`        | Estimacion de retencion IRPF por situacion familiar                |

Y los siguientes recursos (`resources/list`):

- `laboral://nominas`
- `laboral://convenios`
- `laboral://seguridad-social`

> **Principio:** el LLM razona y orquesta; el motor calcula. Ningun numero
> fiscal sale del LLM. Todas las tasas se leen de `data/ss_config.json`,
> trazable a BOE‑A‑2026‑1921 y BOE‑A‑2026‑2548.

---

## Instalacion

```bash
pip install -e .
```

Esto registra el entry-point `pgk-laboral-mcp` (definido en `pyproject.toml`).

> La dependencia `mcp>=1.0` (SDK oficial de Anthropic) ya esta en
> `requirements.txt` y en `pyproject.toml`.

---

## Modo stdio (Claude Desktop · Cursor · Windsurf)

### Claude Desktop

Edita `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) o `%APPDATA%\Claude\claude_desktop_config.json` (Windows) y anade:

```json
{
  "mcpServers": {
    "pgk-laboral-desk": {
      "command": "pgk-laboral-mcp",
      "args": []
    }
  }
}
```

Reinicia Claude Desktop. Las cuatro herramientas `laboral_*` apareceran
disponibles automaticamente en el chat.

> Si instalaste en un virtualenv y `pgk-laboral-mcp` no esta en `PATH`, usa
> la ruta absoluta al binario:
>
> ```json
> "command": "/ruta/a/.venv/bin/pgk-laboral-mcp"
> ```
>
> o invocalo como modulo de Python:
>
> ```json
> "command": "python",
> "args": ["-m", "mcp_server_main"]
> ```

### Cursor / Windsurf

Ambos soportan el mismo schema de `mcpServers`. Configura en
`~/.cursor/mcp.json` (Cursor) o en la UI de Settings → MCP (Windsurf):

```json
{
  "mcpServers": {
    "pgk-laboral-desk": {
      "command": "pgk-laboral-mcp"
    }
  }
}
```

---

## Modo SSE (ChatGPT Desktop · integraciones HTTP)

Levanta el servidor en SSE:

```bash
pgk-laboral-mcp --transport sse --host 127.0.0.1 --port 8765
```

El endpoint SSE queda en `http://127.0.0.1:8765/sse`. En hosts que configuran
MCP remoto, apunta a esa URL.

> Para exponerlo a otros equipos de la red local, pasa
> `--host 0.0.0.0`. Para exposicion publica, pon un reverse proxy con auth
> por delante — **este servidor no implementa autenticacion todavia**.

---

## Probar sin host (smoke test)

```bash
pgk-laboral-mcp &
# Lee/escribe por stdio siguiendo el protocolo MCP: conviene usar el
# Inspector oficial: https://github.com/modelcontextprotocol/inspector

# Tambien puedes usar los tests unitarios incluidos
python -m pytest test_mcp_server_main.py -v
```

---

## Variables de entorno relevantes

| Variable         | Por defecto           | Para que sirve                                  |
|------------------|-----------------------|-------------------------------------------------|
| (ninguna)        | —                     | El servidor MCP es determinista: no necesita LLM. |

> Las herramientas pueden usar `LABORAL_VECTOR_GRAPH_RAG=true` en el futuro
> para enrutar consultas de convenio via el pipeline RAG de `vgrag_search.py`,
> pero hoy las respuestas de `laboral_consultar_convenio` son deterministas
> sobre `data/convenio_*.json`.

---

## Limites actuales

- **Convenios cargados**: 2 (acuaticas estatal 2025‑2027; oficinas y despachos
  Alicante 2024‑2026). Indexar el resto requiere el pipeline de PR #N.
- **IRPF**: estatal + 4 comunidades autonomas (Madrid, Cataluna, Andalucia,
  Valencia).
- **Sin autenticacion**: el modo SSE esta pensado para localhost o red
  privada. Autenticacion queda como siguiente iteracion.
- **Sin rate-limit**: ponlo por delante (nginx / traefik) si expones SSE
  publicamente.
- **Audit trail de llamadas MCP**: todavia no persiste. La traza detallada
  del agente y su sandbox se anadira en otro PR.

---

## Arquitectura

```
Host IA (Claude Desktop / Cursor / ChatGPT)
        │   MCP (stdio o SSE)
        ▼
mcp_server_main.py            ← servidor MCP real (este PR)
        │
        ▼
mcp_server.py                 ← schemas + handlers (tool logic)
        │
        ▼
engine.py · ss_calculator.py · irpf_estimator.py
        │
        ▼
data/ss_config.json · data/convenio_*.json
(Orden ISM/31/2026 · BOE-A-2026-1921)
```

El fichero `mcp_server.py` se mantiene intacto: solo define `MCP_TOOLS` y
`_call_tool`. `mcp_server_main.py` los envuelve en un servidor funcional
usando el SDK `mcp` de Anthropic.
