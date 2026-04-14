# AGENTS.md — PGK Laboral Desk

> Guia para agentes de IA y desarrolladores que trabajan en este repositorio.

---

## PROTOCOLO ENGRAM — OBLIGATORIO ANTES DE CUALQUIER ACCION

**AL INICIAR** → llama `mem_context` para cargar contexto previo de la sesion.

**DESPUES de CADA accion significativa** → llama `mem_save` INMEDIATAMENTE:
- Codigo modificado → `mem_save` ahora
- Bug corregido → `mem_save` ahora
- Decision tomada → `mem_save` ahora
- Patron establecido → `mem_save` ahora
- Descubrimiento no obvio → `mem_save` ahora

**NO esperes al final de la sesion.** Si el contexto explota antes, TODO se pierde.

**AL CERRAR** → llamar `mem_session_summary` con: Goal, Discoveries, Accomplished, Next Steps, Relevant Files.

> Esto aplica a Claude Code, OpenCode, Gemini, Cursor, Cline, Windsurf y cualquier agente con acceso a Engram MCP.

### Memoria (Engram + MEMORY.md)
Usar **Engram** para memoria persistente estructurada entre sesiones de desarrollo:
- `mem_save` → guardar decisiones, errores, patrones
- `mem_search` → buscar contexto de sesiones anteriores
- `mem_context` → recuperar contexto reciente
- `mem_session_summary` → cerrar sesion con resumen
- `MEMORY.md` → resumen ejecutivo para arranque rapido

---
## Estructura del proyecto

```
pgk-laboral-desk/
├── app.py                  # Flask server + API JSON (entry point)
├── engine.py               # Motor determinista de calculo laboral
├── ss_calculator.py        # Cotizaciones Seguridad Social 2026
├── irpf_estimator.py       # Estimacion IRPF estatal + autonomico
├── chat_parser.py          # Parser conversacional (reglas + keywords, sin IA)
├── database.py             # Gestion SQLite (users, employees, alerts)
├── nomina_pdf.py           # Generacion de pre-nomina PDF/HTML
├── client_manager.py       # Gestion multi-cliente/multi-convenio
├── convenio_verifier.py    # Verificacion de vigencia via Perplexity
├── rates_verifier.py       # Verificacion de tasas SS/IRPF/SMI
├── exceptions.py           # Jerarquia de excepciones del dominio
├── validation.py           # Validacion de entradas de la API
├── logging_config.py       # Logging estructurado (JSON/human)
├── boe_importer.py         # Importador de convenios desde BOE
├── data/
│   ├── convenio_*.json     # Convenios colectivos estructurados
│   ├── ss_config.json      # Configuracion tasas SS 2026
│   └── categorias_detalle.json
├── static/                 # Frontend (HTML/CSS/JS)
├── test_engine.py          # Tests del motor (30+ tests)
├── test_chat_parser.py     # Tests del parser
├── test_client_manager.py  # Tests multi-cliente
├── test_boe_importer.py    # Tests BOE importer
├── docs/
│   ├── ARQUITECTURA.md
│   └── OPERACION_Y_LIMITES.md
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── .github/workflows/
    ├── ci.yml              # Lint + tests (Python 3.11/3.12)
    └── deploy.yml          # Deploy via SSH
```

## Cadena de dependencias

```
data/convenio_*.json → engine.py → ss_calculator.py → irpf_estimator.py
                                         ↓
                          chat_parser.py → app.py → database.py
                                                       ↓
                                              nomina_pdf.py
```

## Principio fundamental

**Motor determinista, sin IA externa.** Todo calculo usa reglas + keywords + datos estructurados del BOE. No hay LLM. La precision es trazable al convenio colectivo.

## Reglas criticas

1. **Tasas SS 2026** — Las tasas de Seguridad Social estan en `data/ss_config.json`. Verificar anualmente con `rates_verifier.py`.
2. **Convenios** — Los datos de convenios vienen del BOE y estan en `data/convenio_*.json`. No inventar categorias ni importes.
3. **IRPF por comunidad autonoma** — El estimador soporta Madrid, Cataluna, Andalucia, Valencia. Cada una tiene escalas diferentes.
4. **Pre-nomina != nomina** — La salida es orientativa. No sustituye validacion profesional final.
5. **Tests son obligatorios** — 30+ tests deben pasar. CI los ejecuta en Python 3.11 y 3.12.

## Como anadir funcionalidad

### Nuevo convenio colectivo
1. Importar datos del BOE con `boe_importer.py` o crear JSON manual en `data/convenio_NOMBRE.json`
2. Seguir estructura de convenios existentes (categorias, jornada, pagas extra, etc.)
3. Registrar en `client_manager.py`
4. Anadir tests

### Nueva comunidad autonoma (IRPF)
1. Anadir escalas en `irpf_estimator.py`
2. Documentar fuente oficial de las escalas

### Nuevo calculo
1. Implementar en `engine.py` o modulo dedicado
2. Exponer en `app.py` como endpoint
3. Anadir tests

## Comandos

```bash
pip install -r requirements.txt -r requirements-dev.txt
python app.py --debug  # http://127.0.0.1:8765

# Tests
python -m pytest test_engine.py test_chat_parser.py test_client_manager.py -v

# Lint
ruff check .
ruff format --check .
```

## Known pitfalls

- **WeasyPrint** — Necesita dependencias de sistema (libpango, libgdk-pixbuf) para generar PDF. En Docker se instalan en Dockerfile.
- **SMI anual** — El Salario Minimo Interprofesional cambia anualmente. Actualizar en `data/ss_config.json`.
- **Perplexity API para verificacion** — `convenio_verifier.py` usa Perplexity para verificar vigencia. Es opcional, no rompe nada si no esta configurado.
